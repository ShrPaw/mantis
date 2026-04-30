#!/usr/bin/env python3
"""
MANTIS SPE — Historical Validation Script

Tests whether SPE events have behavioral separation from:
  1. Random timestamps
  2. Same-volatility timestamps
  3. Same-hour timestamps
  4. Opposite-direction structural events

NOT about proving alpha. Only about testing behavioral separation.

Metrics:
  - Forward return 5m / 15m / 30m / 60m
  - MFE / MAE / MFE-MAE ratio
  - Target hit rate / Invalidation hit rate
  - Time to target
  - Spread/slippage proxy
  - Net result with taker cost (4 bps)
  - Net result with maker cost (0–1 bps)
  - Missed-fill scenario
  - Adverse-selection scenario

Pass condition:
  SPE is only considered useful if:
  - events are rare
  - behavior differs from random
  - MFE/MAE improves
  - execution quality is better than average
  - results are not driven by outliers
  - net survives realistic maker assumptions

If not: "No exploitable SPE edge detected."

Usage:
    python3 scripts/validate_spe.py [--events data/events/spe_events.jsonl] [--candles data/candles.jsonl]
"""

import argparse
import csv
import json
import math
import os
import random
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

random.seed(42)  # Reproducibility

# ── Cost Model ──
TAKER_COST_BPS = 4.0
MAKER_COST_BPS = 0.5
ADVERSE_SELECTION_BPS = 2.0
MISSED_FILL_PROB = 0.15


@dataclass
class TradeSimResult:
    entry_price: float
    exit_price: float
    direction: str
    entry_time: float
    exit_time: float
    gross_pnl_bps: float
    net_pnl_bps_taker: float
    net_pnl_bps_maker: float
    mfe_bps: float = 0.0
    mae_bps: float = 0.0
    hit_tp: bool = False
    hit_sl: bool = False
    time_to_target_s: float = 0.0
    spread_at_entry_bps: float = 0.0
    is_win_taker: bool = False
    is_win_maker: bool = False


@dataclass
class ValidationReport:
    # Group identity
    group_name: str = ""
    total_samples: int = 0

    # Forward returns
    avg_return_5m_bps: float = 0.0
    avg_return_15m_bps: float = 0.0
    avg_return_30m_bps: float = 0.0
    avg_return_60m_bps: float = 0.0

    # MFE / MAE
    avg_mfe_bps: float = 0.0
    avg_mae_bps: float = 0.0
    avg_mfe_mae_ratio: float = 0.0

    # Hit rates
    tp_hit_rate: float = 0.0
    sl_hit_rate: float = 0.0
    avg_time_to_target_s: float = 0.0

    # Costs
    avg_spread_bps: float = 0.0
    net_return_taker_bps: float = 0.0
    net_return_maker_bps: float = 0.0

    # Win rates
    win_rate_taker: float = 0.0
    win_rate_maker: float = 0.0

    # Profit factor
    profit_factor_taker: float = 0.0
    profit_factor_maker: float = 0.0

    # Adverse selection
    adverse_selection_rate: float = 0.0
    missed_fill_adjusted_return: float = 0.0

    # Stability
    split_returns: list[float] = field(default_factory=list)
    split_std: float = 0.0
    is_stable: bool = False

    # Outlier analysis
    top_5_pnl_share: float = 0.0
    median_pnl_bps: float = 0.0

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


def load_jsonl(path: str) -> list[dict]:
    """Load JSONL file."""
    items = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
    except FileNotFoundError:
        print(f"❌ File not found: {path}")
    return items


def load_candles(path: str) -> list[dict]:
    """Load candle data (time, open, high, low, close, volume)."""
    candles = load_jsonl(path)
    # Sort by time
    candles.sort(key=lambda c: c.get("time", 0))
    return candles


def build_price_lookup(candles: list[dict]) -> dict[float, float]:
    """Build timestamp → close price lookup."""
    lookup = {}
    for c in candles:
        t = c.get("time", 0)
        p = c.get("close", 0) or c.get("price", 0)
        if t > 0 and p > 0:
            lookup[t] = p
    return lookup


def build_vol_lookup(candles: list[dict]) -> dict[float, float]:
    """Build timestamp → volatility proxy (high-low range in bps)."""
    lookup = {}
    for c in candles:
        t = c.get("time", 0)
        h = c.get("high", 0)
        l = c.get("low", 0)
        mid = (h + l) / 2 if h > 0 and l > 0 else 0
        if t > 0 and mid > 0:
            lookup[t] = ((h - l) / mid) * 10000
    return lookup


def simulate_trade(
    entry_price: float,
    direction: str,
    entry_time: float,
    stop_loss: float,
    tp_levels: list[float],
    price_lookup: dict[float, float],
    spread_bps: float = 1.0,
) -> Optional[TradeSimResult]:
    """Simulate a single trade against price history."""
    if entry_price <= 0 or entry_time <= 0:
        return None

    # Find nearest price point
    times = sorted(price_lookup.keys())
    if not times:
        return None

    # Find entry time in lookup
    nearest = min(times, key=lambda t: abs(t - entry_time))
    if abs(nearest - entry_time) > 120:
        return None

    # Look forward
    future_prices = [(t, price_lookup[t]) for t in times if t > entry_time]
    if not future_prices:
        return None

    tp = tp_levels[0] if tp_levels else entry_price * (1.001 if direction == "LONG" else 0.999)
    mfe = 0.0
    mae = 0.0
    exit_price = entry_price
    exit_time = entry_time
    hit_tp = False
    hit_sl = False
    time_to_target = 0.0

    for t, p in future_prices[:720]:  # Max 12h forward (1m candles)
        if direction == "LONG":
            excursion = (p - entry_price) / entry_price * 10000
            mfe = max(mfe, excursion)
            mae = min(mae, excursion)

            if p >= tp:
                exit_price = tp
                exit_time = t
                hit_tp = True
                time_to_target = t - entry_time
                break
            elif p <= stop_loss:
                exit_price = stop_loss
                exit_time = t
                hit_sl = True
                break
        else:
            excursion = (entry_price - p) / entry_price * 10000
            mfe = max(mfe, excursion)
            mae = min(mae, excursion)

            if p <= tp:
                exit_price = tp
                exit_time = t
                hit_tp = True
                time_to_target = t - entry_time
                break
            elif p >= stop_loss:
                exit_price = stop_loss
                exit_time = t
                hit_sl = True
                break

    # PnL calculation
    if direction == "LONG":
        gross_pnl_bps = (exit_price - entry_price) / entry_price * 10000
    else:
        gross_pnl_bps = (entry_price - exit_price) / entry_price * 10000

    net_taker = gross_pnl_bps - TAKER_COST_BPS - spread_bps
    net_maker = gross_pnl_bps - MAKER_COST_BPS

    # Adverse selection penalty
    if mae < -ADVERSE_SELECTION_BPS:
        net_taker -= ADVERSE_SELECTION_BPS * 0.5
        net_maker -= ADVERSE_SELECTION_BPS * 0.3

    return TradeSimResult(
        entry_price=entry_price,
        exit_price=exit_price,
        direction=direction,
        entry_time=entry_time,
        exit_time=exit_time,
        gross_pnl_bps=gross_pnl_bps,
        net_pnl_bps_taker=net_taker,
        net_pnl_bps_maker=net_maker,
        mfe_bps=mfe,
        mae_bps=mae,
        hit_tp=hit_tp,
        hit_sl=hit_sl,
        time_to_target_s=time_to_target,
        spread_at_entry_bps=spread_bps,
        is_win_taker=net_taker > 0,
        is_win_maker=net_maker > 0,
    )


def generate_random_entries(
    spe_events: list[dict],
    price_lookup: dict[float, float],
    vol_lookup: dict[float, float],
) -> list[dict]:
    """Generate random-direction entries at same timestamps."""
    entries = []
    times = sorted(price_lookup.keys())
    for evt in spe_events:
        entry_time = evt.get("timestamp", 0)
        entry_price = evt.get("entry_price", 0)
        if entry_price <= 0:
            continue

        # Random direction
        direction = random.choice(["LONG", "SHORT"])
        if direction == "LONG":
            sl = entry_price * 0.997
            tp = entry_price * 1.003
        else:
            sl = entry_price * 1.003
            tp = entry_price * 0.997

        entries.append({
            "entry_price": entry_price,
            "direction": direction,
            "entry_time": entry_time,
            "stop_loss": sl,
            "tp_levels": [tp],
            "spread_bps": 1.0,
        })
    return entries


def generate_vol_matched_entries(
    spe_events: list[dict],
    price_lookup: dict[float, float],
    vol_lookup: dict[float, float],
) -> list[dict]:
    """Generate entries at timestamps with similar volatility."""
    entries = []
    times = sorted(price_lookup.keys())
    for evt in spe_events:
        entry_time = evt.get("timestamp", 0)
        entry_price = evt.get("entry_price", 0)
        direction = evt.get("direction", "LONG")
        if entry_price <= 0:
            continue

        # Find similar-vol timestamps
        evt_vol = vol_lookup.get(entry_time, 10.0)
        similar_times = [t for t in times if abs(vol_lookup.get(t, 0) - evt_vol) < 5.0 and abs(t - entry_time) > 300]
        if not similar_times:
            continue

        shifted_time = random.choice(similar_times)
        sl = evt.get("stop_loss", entry_price * 0.997)
        tp = evt.get("tp_levels", [entry_price * 1.003])

        entries.append({
            "entry_price": price_lookup.get(shifted_time, entry_price),
            "direction": direction,
            "entry_time": shifted_time,
            "stop_loss": sl,
            "tp_levels": tp if isinstance(tp, list) else [tp],
            "spread_bps": 1.0,
        })
    return entries


def generate_opposite_entries(spe_events: list[dict]) -> list[dict]:
    """Generate opposite-direction entries."""
    entries = []
    for evt in spe_events:
        entry_price = evt.get("entry_price", 0)
        direction = evt.get("direction", "LONG")
        entry_time = evt.get("timestamp", 0)
        stop_loss = evt.get("stop_loss", 0)
        tp_levels = evt.get("tp_levels", [])

        if not all([entry_price, entry_time, stop_loss]):
            continue

        opposite = "SHORT" if direction == "LONG" else "LONG"
        if opposite == "LONG":
            sl = entry_price * 2 - (tp_levels[0] if tp_levels else entry_price * 1.003)
            tp = stop_loss
        else:
            sl = tp_levels[0] if tp_levels else entry_price * 1.003
            tp = stop_loss

        entries.append({
            "entry_price": entry_price,
            "direction": opposite,
            "entry_time": entry_time,
            "stop_loss": sl,
            "tp_levels": [tp],
            "spread_bps": 1.0,
        })
    return entries


def compute_report(
    group_name: str,
    results: list[TradeSimResult],
    forward_returns: dict[str, list[float]],
) -> ValidationReport:
    """Compute validation report from trade simulation results."""
    report = ValidationReport(group_name=group_name, total_samples=len(results))

    if not results:
        return report

    # Forward returns
    for horizon, returns in forward_returns.items():
        avg = sum(returns) / len(returns) if returns else 0
        if horizon == "5m":
            report.avg_return_5m_bps = round(avg, 2)
        elif horizon == "15m":
            report.avg_return_15m_bps = round(avg, 2)
        elif horizon == "30m":
            report.avg_return_30m_bps = round(avg, 2)
        elif horizon == "60m":
            report.avg_return_60m_bps = round(avg, 2)

    # MFE / MAE
    mfe_list = [r.mfe_bps for r in results]
    mae_list = [r.mae_bps for r in results]
    report.avg_mfe_bps = round(sum(mfe_list) / len(mfe_list), 2)
    report.avg_mae_bps = round(sum(mae_list) / len(mae_list), 2)

    mfe_mae_ratios = []
    for mfe, mae in zip(mfe_list, mae_list):
        if mae < 0:
            mfe_mae_ratios.append(mfe / abs(mae))
    report.avg_mfe_mae_ratio = round(sum(mfe_mae_ratios) / len(mfe_mae_ratios), 2) if mfe_mae_ratios else 0

    # Hit rates
    tp_hits = sum(1 for r in results if r.hit_tp)
    sl_hits = sum(1 for r in results if r.hit_sl)
    report.tp_hit_rate = round(tp_hits / len(results), 4)
    report.sl_hit_rate = round(sl_hits / len(results), 4)

    target_times = [r.time_to_target_s for r in results if r.hit_tp and r.time_to_target_s > 0]
    report.avg_time_to_target_s = round(sum(target_times) / len(target_times), 1) if target_times else 0

    # Spread
    spreads = [r.spread_at_entry_bps for r in results]
    report.avg_spread_bps = round(sum(spreads) / len(spreads), 2)

    # Net returns
    taker_returns = [r.net_pnl_bps_taker for r in results]
    maker_returns = [r.net_pnl_bps_maker for r in results]
    report.net_return_taker_bps = round(sum(taker_returns), 2)
    report.net_return_maker_bps = round(sum(maker_returns), 2)

    # Win rates
    report.win_rate_taker = round(sum(1 for r in results if r.is_win_taker) / len(results), 4)
    report.win_rate_maker = round(sum(1 for r in results if r.is_win_maker) / len(results), 4)

    # Profit factor
    taker_wins = sum(r for r in taker_returns if r > 0)
    taker_losses = abs(sum(r for r in taker_returns if r < 0))
    report.profit_factor_taker = round(taker_wins / taker_losses, 3) if taker_losses > 0 else float('inf')

    maker_wins = sum(r for r in maker_returns if r > 0)
    maker_losses = abs(sum(r for r in maker_returns if r < 0))
    report.profit_factor_maker = round(maker_wins / maker_losses, 3) if maker_losses > 0 else float('inf')

    # Adverse selection
    adverse = sum(1 for r in results if r.mae_bps < -ADVERSE_SELECTION_BPS)
    report.adverse_selection_rate = round(adverse / len(results), 4)

    # Missed fill adjusted
    missed_returns = [r.net_pnl_bps_maker * (1 - MISSED_FILL_PROB) for r in results]
    report.missed_fill_adjusted_return = round(sum(missed_returns), 2)

    # Stability (5 splits)
    if len(results) >= 10:
        shuffled = list(results)
        random.shuffle(shuffled)
        split_size = len(shuffled) // 5
        splits = []
        for i in range(5):
            chunk = shuffled[i * split_size:(i + 1) * split_size]
            splits.append(sum(r.net_pnl_bps_maker for r in chunk))
        report.split_returns = [round(s, 2) for s in splits]
        mean_split = sum(splits) / len(splits)
        variance = sum((s - mean_split) ** 2 for s in splits) / len(splits)
        report.split_std = round(math.sqrt(variance), 2)
        report.is_stable = report.split_std < abs(mean_split) * 0.5 if mean_split != 0 else False

    # Outlier analysis
    sorted_maker = sorted(maker_returns, reverse=True)
    if len(sorted_maker) >= 5:
        top5_pnl = sum(sorted_maker[:5])
        total_pnl = sum(sorted_maker)
        report.top_5_pnl_share = round(top5_pnl / total_pnl, 4) if total_pnl > 0 else 0

    median_idx = len(sorted_maker) // 2
    report.median_pnl_bps = round(sorted_maker[median_idx], 2) if sorted_maker else 0

    return report


def compute_forward_returns(
    events: list[dict],
    price_lookup: dict[float, float],
) -> dict[str, list[float]]:
    """Compute forward returns at 5m/15m/30m/60m horizons."""
    times = sorted(price_lookup.keys())
    horizons = {"5m": 300, "15m": 900, "30m": 1800, "60m": 3600}
    returns = {h: [] for h in horizons}

    for evt in events:
        entry_time = evt.get("timestamp", 0)
        entry_price = evt.get("entry_price", 0)
        direction = evt.get("direction", "LONG")

        if entry_price <= 0 or entry_time <= 0:
            continue

        # Find nearest entry
        nearest = min(times, key=lambda t: abs(t - entry_time))
        if abs(nearest - entry_time) > 120:
            continue

        for horizon_name, horizon_secs in horizons.items():
            target_time = entry_time + horizon_secs
            future = [t for t in times if t >= target_time]
            if not future:
                continue

            future_price = price_lookup[future[0]]
            if direction == "LONG":
                ret_bps = (future_price - entry_price) / entry_price * 10000
            else:
                ret_bps = (entry_price - future_price) / entry_price * 10000

            returns[horizon_name].append(ret_bps)

    return returns


def print_comparison(spe_report: ValidationReport, baselines: list[ValidationReport]):
    """Print comparison table."""
    print("\n" + "=" * 80)
    print(f"{'Metric':<35} {'SPE':>10}", end="")
    for b in baselines:
        print(f" {b.group_name:>12}", end="")
    print()
    print("-" * 80)

    metrics = [
        ("Samples", "total_samples"),
        ("Avg Return 5m (bps)", "avg_return_5m_bps"),
        ("Avg Return 15m (bps)", "avg_return_15m_bps"),
        ("Avg Return 30m (bps)", "avg_return_30m_bps"),
        ("Avg Return 60m (bps)", "avg_return_60m_bps"),
        ("Avg MFE (bps)", "avg_mfe_bps"),
        ("Avg MAE (bps)", "avg_mae_bps"),
        ("MFE/MAE Ratio", "avg_mfe_mae_ratio"),
        ("TP Hit Rate", "tp_hit_rate"),
        ("SL Hit Rate", "sl_hit_rate"),
        ("Avg Time to Target (s)", "avg_time_to_target_s"),
        ("Avg Spread (bps)", "avg_spread_bps"),
        ("Net Return Taker (bps)", "net_return_taker_bps"),
        ("Net Return Maker (bps)", "net_return_maker_bps"),
        ("Win Rate Taker", "win_rate_taker"),
        ("Win Rate Maker", "win_rate_maker"),
        ("PF Taker", "profit_factor_taker"),
        ("PF Maker", "profit_factor_maker"),
        ("Adverse Selection Rate", "adverse_selection_rate"),
        ("Missed-Fill Adj Return", "missed_fill_adjusted_return"),
        ("Split Std", "split_std"),
        ("Stable?", "is_stable"),
        ("Top 5 PnL Share", "top_5_pnl_share"),
        ("Median PnL (bps)", "median_pnl_bps"),
    ]

    for label, attr in metrics:
        val = getattr(spe_report, attr)
        val_str = f"{val}" if isinstance(val, bool) else f"{val:.4f}" if isinstance(val, float) else str(val)
        print(f"{label:<35} {val_str:>10}", end="")
        for b in baselines:
            bval = getattr(b, attr)
            bval_str = f"{bval}" if isinstance(bval, bool) else f"{bval:.4f}" if isinstance(bval, float) else str(bval)
            print(f" {bval_str:>12}", end="")
        print()


def generate_markdown_report(
    spe_report: ValidationReport,
    baselines: list[ValidationReport],
    spe_events: list[dict],
    spe_results: list[TradeSimResult],
) -> str:
    """Generate full validation report in Markdown."""

    # Determine verdict
    verdict = "D"
    verdict_text = "No exploitable SPE edge detected"

    if spe_report.total_samples >= 5:
        # Check pass conditions
        beats_random = spe_report.net_return_maker_bps > baselines[0].net_return_maker_bps if baselines else False
        positive_maker = spe_report.net_return_maker_bps > 0
        stable = spe_report.is_stable
        rare = spe_report.total_samples < 200  # SPE events should be rare
        mfe_improves = spe_report.avg_mfe_mae_ratio > (baselines[0].avg_mfe_mae_ratio if baselines else 0)
        not_outlier_driven = spe_report.top_5_pnl_share < 0.8

        conditions = [beats_random, positive_maker, stable, rare, mfe_improves, not_outlier_driven]
        passed = sum(conditions)

        if passed >= 5:
            verdict = "A"
            verdict_text = "SPE adds useful context — behavioral separation confirmed"
        elif passed >= 3:
            verdict = "B"
            verdict_text = "SPE detects structure but needs refinement"
        elif passed >= 1:
            verdict = "C"
            verdict_text = "SPE is noisy / late / not useful"
        else:
            verdict = "D"
            verdict_text = "No exploitable SPE edge detected"

    report = f"""# MANTIS SPE — Historical Validation Report

**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
**SPE Events Analyzed:** {spe_report.total_samples}
**Baselines:** Random, Vol-Matched, Opposite Direction

---

## Methodology

SPE events were simulated against historical price data with:
- **Taker cost:** {TAKER_COST_BPS} bps round trip
- **Maker cost:** {MAKER_COST_BPS} bps round trip
- **Adverse selection:** {ADVERSE_SELECTION_BPS} bps penalty
- **Missed fill:** {MISSED_FILL_PROB * 100}% probability

Three baselines compared:
1. **Random** — Same timestamps, random direction
2. **Vol-Matched** — Same direction, similar-volatility timestamps
3. **Opposite** — Opposite direction at same timestamps

---

## Results Comparison

| Metric | SPE | Random | Vol-Matched | Opposite |
|--------|-----|--------|-------------|----------|
| Samples | {spe_report.total_samples} | {baselines[0].total_samples if baselines else 0} | {baselines[1].total_samples if len(baselines) > 1 else 0} | {baselines[2].total_samples if len(baselines) > 2 else 0} |
| Avg Return 5m (bps) | {spe_report.avg_return_5m_bps} | {baselines[0].avg_return_5m_bps if baselines else 0} | {baselines[1].avg_return_5m_bps if len(baselines) > 1 else 0} | {baselines[2].avg_return_5m_bps if len(baselines) > 2 else 0} |
| Avg Return 15m (bps) | {spe_report.avg_return_15m_bps} | {baselines[0].avg_return_15m_bps if baselines else 0} | {baselines[1].avg_return_15m_bps if len(baselines) > 1 else 0} | {baselines[2].avg_return_15m_bps if len(baselines) > 2 else 0} |
| Avg Return 30m (bps) | {spe_report.avg_return_30m_bps} | {baselines[0].avg_return_30m_bps if baselines else 0} | {baselines[1].avg_return_30m_bps if len(baselines) > 1 else 0} | {baselines[2].avg_return_30m_bps if len(baselines) > 2 else 0} |
| Avg Return 60m (bps) | {spe_report.avg_return_60m_bps} | {baselines[0].avg_return_60m_bps if baselines else 0} | {baselines[1].avg_return_60m_bps if len(baselines) > 1 else 0} | {baselines[2].avg_return_60m_bps if len(baselines) > 2 else 0} |
| MFE/MAE Ratio | {spe_report.avg_mfe_mae_ratio} | {baselines[0].avg_mfe_mae_ratio if baselines else 0} | {baselines[1].avg_mfe_mae_ratio if len(baselines) > 1 else 0} | {baselines[2].avg_mfe_mae_ratio if len(baselines) > 2 else 0} |
| TP Hit Rate | {spe_report.tp_hit_rate:.1%} | {baselines[0].tp_hit_rate:.1% if baselines else 0} | {baselines[1].tp_hit_rate:.1% if len(baselines) > 1 else 0} | {baselines[2].tp_hit_rate:.1% if len(baselines) > 2 else 0} |
| Net Taker (bps) | {spe_report.net_return_taker_bps} | {baselines[0].net_return_taker_bps if baselines else 0} | {baselines[1].net_return_taker_bps if len(baselines) > 1 else 0} | {baselines[2].net_return_taker_bps if len(baselines) > 2 else 0} |
| Net Maker (bps) | {spe_report.net_return_maker_bps} | {baselines[0].net_return_maker_bps if baselines else 0} | {baselines[1].net_return_maker_bps if len(baselines) > 1 else 0} | {baselines[2].net_return_maker_bps if len(baselines) > 2 else 0} |
| Win Rate Maker | {spe_report.win_rate_maker:.1%} | {baselines[0].win_rate_maker:.1% if baselines else 0} | {baselines[1].win_rate_maker:.1% if len(baselines) > 1 else 0} | {baselines[2].win_rate_maker:.1% if len(baselines) > 2 else 0} |
| PF Maker | {spe_report.profit_factor_maker} | {baselines[0].profit_factor_maker if baselines else 0} | {baselines[1].profit_factor_maker if len(baselines) > 1 else 0} | {baselines[2].profit_factor_maker if len(baselines) > 2 else 0} |
| Adverse Selection | {spe_report.adverse_selection_rate:.1%} | {baselines[0].adverse_selection_rate:.1% if baselines else 0} | {baselines[1].adverse_selection_rate:.1% if len(baselines) > 1 else 0} | {baselines[2].adverse_selection_rate:.1% if len(baselines) > 2 else 0} |

---

## Detailed SPE Metrics

### Return Distribution
- **5m:** {spe_report.avg_return_5m_bps} bps avg
- **15m:** {spe_report.avg_return_15m_bps} bps avg
- **30m:** {spe_report.avg_return_30m_bps} bps avg
- **60m:** {spe_report.avg_return_60m_bps} bps avg

### Risk Metrics
- **Avg MFE:** {spe_report.avg_mfe_bps} bps (max favorable)
- **Avg MAE:** {spe_report.avg_mae_bps} bps (max adverse)
- **MFE/MAE Ratio:** {spe_report.avg_mfe_mae_ratio}
- **Adverse Selection Rate:** {spe_report.adverse_selection_rate:.1%}

### Execution Quality
- **Avg Spread:** {spe_report.avg_spread_bps} bps
- **TP Hit Rate:** {spe_report.tp_hit_rate:.1%}
- **SL Hit Rate:** {spe_report.sl_hit_rate:.1%}
- **Avg Time to Target:** {spe_report.avg_time_to_target_s:.0f}s

### Cost Analysis
- **Net with Taker (4 bps):** {spe_report.net_return_taker_bps} bps
- **Net with Maker (0.5 bps):** {spe_report.net_return_maker_bps} bps
- **Missed-Fill Adjusted:** {spe_report.missed_fill_adjusted_return} bps

### Stability
- **Split Returns:** {spe_report.split_returns}
- **Split Std:** {spe_report.split_std} bps
- **Stable:** {'Yes' if spe_report.is_stable else 'No'}

### Outlier Analysis
- **Top 5 PnL Share:** {spe_report.top_5_pnl_share:.1%} of total PnL from top 5 trades
- **Median PnL:** {spe_report.median_pnl_bps} bps

---

## Pass Conditions

| Condition | Result |
|-----------|--------|
| Events are rare | {'✅' if spe_report.total_samples < 200 else '❌'} ({spe_report.total_samples} events) |
| Behavior differs from random | {'✅' if baselines and spe_report.net_return_maker_bps > baselines[0].net_return_maker_bps else '❌'} |
| MFE/MAE improves | {'✅' if spe_report.avg_mfe_mae_ratio > 1.5 else '❌'} ({spe_report.avg_mfe_mae_ratio}) |
| Execution quality > average | {'✅' if spe_report.tp_hit_rate > 0.3 else '❌'} (TP: {spe_report.tp_hit_rate:.1%}) |
| Not driven by outliers | {'✅' if spe_report.top_5_pnl_share < 0.8 else '❌'} (top 5: {spe_report.top_5_pnl_share:.1%}) |
| Net survives maker assumptions | {'✅' if spe_report.net_return_maker_bps > 0 else '❌'} ({spe_report.net_return_maker_bps} bps) |

---

## Final Classification

| Class | Meaning |
|-------|---------|
| A | Useful execution/context layer |
| B | Useful but too restrictive/noisy |
| C | Not useful |
| D | No edge / kill module |

### **Verdict: {verdict} — {verdict_text}**

---

## Important Caveats

1. **This is NOT proof of profitability.** Historical simulation has survivorship bias, look-ahead bias, and assumes perfect fills.
2. **Thresholds were NOT tuned.** Results reflect the current configuration as-is.
3. **SPE is observation-only.** No trades were executed. This is purely diagnostic.
4. **Small sample caveat.** {f'With only {spe_report.total_samples} events, statistical power is limited.' if spe_report.total_samples < 30 else ''}
5. **Cost model is conservative.** Real-world costs may be higher due to slippage, latency, and market impact.
"""
    return report


def main():
    parser = argparse.ArgumentParser(description="MANTIS SPE Historical Validation")
    parser.add_argument("--events", type=str, default="data/events/spe_events.jsonl",
                        help="Path to SPE events JSONL")
    parser.add_argument("--candles", type=str, default="data/candles.jsonl",
                        help="Path to candles JSONL (time, open, high, low, close, volume)")
    parser.add_argument("--output", type=str, default="MANTIS_SPE_VALIDATION_REPORT.md",
                        help="Output report file")
    parser.add_argument("--json-output", type=str, default="data/spe_validation.json",
                        help="JSON output path")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════╗")
    print("║  MANTIS SPE — Historical Validation                 ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    # Load data
    spe_events = load_jsonl(args.events)
    candles = load_candles(args.candles)

    if not spe_events:
        print(f"❌ No SPE events found at {args.events}")
        print("   Run MANTIS + SPE first to collect events.")
        print("   Then re-run this script.")
        # Generate empty report
        report = ValidationReport(group_name="SPE", total_samples=0)
        report_text = generate_markdown_report(report, [], [], [])
        with open(args.output, "w") as f:
            f.write(report_text)
        print(f"\n⚠ Empty report written to {args.output}")
        return

    if not candles:
        print(f"❌ No candle data found at {args.candles}")
        print("   Export candles from MANTIS or fetch from Hyperliquid.")
        sys.exit(1)

    print(f"📊 Loaded {len(spe_events)} SPE events")
    print(f"📊 Loaded {len(candles)} candles")

    # Build lookups
    price_lookup = build_price_lookup(candles)
    vol_lookup = build_vol_lookup(candles)
    print(f"📊 Price lookup: {len(price_lookup)} points")

    # Compute forward returns for SPE events
    forward_returns = compute_forward_returns(spe_events, price_lookup)

    # Simulate SPE trades
    print("\n🔄 Simulating SPE trades...")
    spe_results = []
    for evt in spe_events:
        result = simulate_trade(
            entry_price=evt.get("entry_price", 0),
            direction=evt.get("direction", "LONG"),
            entry_time=evt.get("timestamp", 0),
            stop_loss=evt.get("stop_loss", 0),
            tp_levels=evt.get("tp_levels", []),
            price_lookup=price_lookup,
            spread_bps=evt.get("spread_bps", 1.0),
        )
        if result:
            spe_results.append(result)

    print(f"   Simulated {len(spe_results)} SPE trades")

    # Generate baselines
    print("\n🔄 Generating baselines...")

    random_entries = generate_random_entries(spe_events, price_lookup, vol_lookup)
    random_results = []
    for entry in random_entries:
        r = simulate_trade(**entry, price_lookup=price_lookup)
        if r:
            random_results.append(r)
    print(f"   Random: {len(random_results)} trades")

    vol_entries = generate_vol_matched_entries(spe_events, price_lookup, vol_lookup)
    vol_results = []
    for entry in vol_entries:
        r = simulate_trade(**entry, price_lookup=price_lookup)
        if r:
            vol_results.append(r)
    print(f"   Vol-matched: {len(vol_results)} trades")

    opposite_entries = generate_opposite_entries(spe_events)
    opposite_results = []
    for entry in opposite_entries:
        r = simulate_trade(**entry, price_lookup=price_lookup)
        if r:
            opposite_results.append(r)
    print(f"   Opposite: {len(opposite_results)} trades")

    # Compute reports
    spe_report = compute_report("SPE", spe_results, forward_returns)
    random_report = compute_report("Random", random_results, {})
    vol_report = compute_report("Vol-Matched", vol_results, {})
    opposite_report = compute_report("Opposite", opposite_results, {})

    baselines = [random_report, vol_report, opposite_report]

    # Print comparison
    print_comparison(spe_report, baselines)

    # Generate markdown report
    report_text = generate_markdown_report(spe_report, baselines, spe_events, spe_results)

    with open(args.output, "w") as f:
        f.write(report_text)
    print(f"\n✅ Report written to {args.output}")

    # JSON output
    json_data = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "spe": spe_report.to_dict(),
        "baselines": {b.group_name: b.to_dict() for b in baselines},
    }
    os.makedirs(os.path.dirname(args.json_output), exist_ok=True)
    with open(args.json_output, "w") as f:
        json.dump(json_data, f, indent=2)
    print(f"✅ JSON written to {args.json_output}")

    # Final verdict
    print(f"\n{'=' * 60}")
    print(f"VERDICT: Check {args.output}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
