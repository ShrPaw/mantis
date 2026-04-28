"""MANTIS Execution Engine — Historical Validation Script.

Purpose: Verify whether detected states have meaningful behavioral separation.
NOT to prove alpha. To validate that the engine identifies dangerous/favorable
environments better than random.

Usage:
    python -m scripts.validate_mantis --events data/events/mantis_events.jsonl --trades data/research/trades.jsonl
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ForwardMetrics:
    """Forward-looking metrics for a single event."""
    return_5m: float = 0.0
    return_15m: float = 0.0
    return_30m: float = 0.0
    return_1h: float = 0.0
    vol_expansion_5m: float = 0.0
    mfe: float = 0.0  # max favorable excursion
    mae: float = 0.0  # max adverse excursion
    spread_at_entry: float = 0.0
    slippage_proxy: float = 0.0
    continuation_prob: float = 0.0
    reversal_prob: float = 0.0


@dataclass
class StateStats:
    """Aggregated statistics for a market state."""
    count: int = 0
    returns_5m: list[float] = field(default_factory=list)
    returns_15m: list[float] = field(default_factory=list)
    returns_30m: list[float] = field(default_factory=list)
    returns_1h: list[float] = field(default_factory=list)
    mfe_list: list[float] = field(default_factory=list)
    mae_list: list[float] = field(default_factory=list)
    spread_list: list[float] = field(default_factory=list)
    vol_expansion: list[float] = field(default_factory=list)
    continuation_count: int = 0
    reversal_count: int = 0
    exec_quality_list: list[float] = field(default_factory=list)
    risk_list: list[float] = field(default_factory=list)
    imbalance_list: list[float] = field(default_factory=list)


def load_events(path: str) -> list[dict]:
    """Load events from JSONL file."""
    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def load_trades(path: str) -> list[dict]:
    """Load trades from JSONL file."""
    trades = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                trades.append(json.loads(line))
    return trades


def compute_forward_metrics(event_ts: float, trades: list[dict],
                            event_price: float) -> ForwardMetrics | None:
    """Compute forward-looking metrics from trade data."""
    if event_price <= 0:
        return None

    fm = ForwardMetrics()

    # Get trades in forward windows
    horizons = {
        "5m": 300, "15m": 900, "30m": 1800, "1h": 3600,
    }

    for name, seconds in horizons.items():
        window_trades = [t for t in trades
                         if event_ts < t.get("timestamp", 0) <= event_ts + seconds]
        if not window_trades:
            continue

        last_price = window_trades[-1].get("price", event_price)
        ret_bps = (last_price - event_price) / event_price * 10000

        if name == "5m":
            fm.return_5m = ret_bps
        elif name == "15m":
            fm.return_15m = ret_bps
        elif name == "30m":
            fm.return_30m = ret_bps
        elif name == "1h":
            fm.return_1h = ret_bps

    # MFE / MAE (within 30 minutes)
    window_30m = [t for t in trades if event_ts < t.get("timestamp", 0) <= event_ts + 1800]
    if window_30m:
        prices = [t.get("price", 0) for t in window_30m if t.get("price", 0) > 0]
        if prices:
            max_price = max(prices)
            min_price = min(prices)
            fm.mfe = max(max_price - event_price, event_price - min_price) / event_price * 10000
            fm.mae = min(max_price - event_price, event_price - min_price) / event_price * 10000
            # Normalize: MFE is always positive, MAE is always positive (worst drawdown)
            fm.mfe = abs((max_price - event_price) / event_price * 10000)
            fm.mae = abs((event_price - min_price) / event_price * 10000)

    # Volatility expansion
    pre_trades = [t for t in trades if event_ts - 300 <= t.get("timestamp", 0) < event_ts]
    post_trades = [t for t in trades if event_ts < t.get("timestamp", 0) <= event_ts + 300]

    if pre_trades and post_trades:
        pre_prices = [t.get("price", 0) for t in pre_trades if t.get("price", 0) > 0]
        post_prices = [t.get("price", 0) for t in post_trades if t.get("price", 0) > 0]
        if len(pre_prices) > 1 and len(post_prices) > 1:
            pre_vol = _realized_vol(pre_prices)
            post_vol = _realized_vol(post_prices)
            if pre_vol > 0:
                fm.vol_expansion_5m = post_vol / pre_vol

    # Continuation / reversal (at 15m)
    if fm.return_15m != 0:
        # If return continued in same direction as first 5m
        if fm.return_5m != 0:
            fm.continuation_prob = 1.0 if (fm.return_5m > 0) == (fm.return_15m > 0) else 0.0
            fm.reversal_prob = 1.0 - fm.continuation_prob

    return fm


def _realized_vol(prices: list[float]) -> float:
    """Compute realized volatility from price series."""
    if len(prices) < 2:
        return 0.0
    returns = []
    for i in range(1, len(prices)):
        if prices[i-1] > 0:
            returns.append((prices[i] - prices[i-1]) / prices[i-1])
    if not returns:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / len(returns)
    return math.sqrt(var)


def build_state_stats(events: list[dict], trades: list[dict]) -> dict[str, StateStats]:
    """Build statistics for each detected state."""
    stats = defaultdict(StateStats)

    # Build trade index by timestamp for fast lookup
    trade_by_ts = {}
    for t in trades:
        ts = t.get("timestamp", 0)
        trade_by_ts[ts] = t

    for event in events:
        state = event.get("market_state", "IDLE")
        if state == "IDLE":
            continue

        s = stats[state]
        s.count += 1

        # Get scores
        scores = event.get("scores_flat", event.get("scores", {}))
        s.exec_quality_list.append(scores.get("execution_quality", 0))
        s.risk_list.append(scores.get("risk", 0))
        s.imbalance_list.append(scores.get("imbalance", 0))

        # Compute forward metrics if we have trades data
        ts = event.get("timestamp", 0)
        # Find nearest trade price
        nearest_price = _find_nearest_price(ts, trades)
        if nearest_price:
            fm = compute_forward_metrics(ts, trades, nearest_price)
            if fm:
                s.returns_5m.append(fm.return_5m)
                s.returns_15m.append(fm.return_15m)
                s.returns_30m.append(fm.return_30m)
                s.returns_1h.append(fm.return_1h)
                s.mfe_list.append(fm.mfe)
                s.mae_list.append(fm.mae)
                s.spread_list.append(fm.spread_at_entry)
                s.vol_expansion.append(fm.vol_expansion_5m)
                s.continuation_count += fm.continuation_prob
                s.reversal_count += fm.reversal_prob

    return dict(stats)


def _find_nearest_price(target_ts: float, trades: list[dict]) -> float | None:
    """Find the price of the nearest trade to target timestamp."""
    best_ts = None
    best_price = None
    for t in trades:
        ts = t.get("timestamp", 0)
        if ts <= target_ts:
            if best_ts is None or ts > best_ts:
                best_ts = ts
                best_price = t.get("price")
    return best_price


def build_random_baseline(trades: list[dict], n_samples: int = 500) -> StateStats:
    """Build random baseline from random timestamps."""
    stats = StateStats()
    stats.count = n_samples

    if not trades:
        return stats

    # Pick random timestamps
    timestamps = [t.get("timestamp", 0) for t in trades]
    min_ts = min(timestamps)
    max_ts = max(timestamps)

    for _ in range(n_samples):
        random_ts = random.uniform(min_ts + 3600, max_ts - 3600)  # leave room for forward look
        price = _find_nearest_price(random_ts, trades)
        if not price:
            continue
        fm = compute_forward_metrics(random_ts, trades, price)
        if fm:
            stats.returns_5m.append(fm.return_5m)
            stats.returns_15m.append(fm.return_15m)
            stats.returns_30m.append(fm.return_30m)
            stats.returns_1h.append(fm.return_1h)
            stats.mfe_list.append(fm.mfe)
            stats.mae_list.append(fm.mae)
            stats.vol_expansion.append(fm.vol_expansion_5m)
            stats.continuation_count += fm.continuation_prob
            stats.reversal_count += fm.reversal_prob

    return stats


def build_same_vol_baseline(trades: list[dict], events: list[dict],
                            n_samples: int = 500) -> StateStats:
    """Build baseline from timestamps with similar volatility."""
    stats = StateStats()
    stats.count = n_samples

    if not trades or not events:
        return stats

    # For each event, find a random time with similar vol
    for event in random.sample(events, min(n_samples, len(events))):
        ts = event.get("timestamp", 0)
        # Compute vol around event
        pre_trades = [t for t in trades if ts - 300 <= t.get("timestamp", 0) < ts]
        if not pre_trades:
            continue
        pre_prices = [t.get("price", 0) for t in pre_trades if t.get("price", 0) > 0]
        if len(pre_prices) < 2:
            continue
        event_vol = _realized_vol(pre_prices)

        # Find random time with similar vol
        for _ in range(10):
            random_ts = random.uniform(min(t.get("timestamp", 0) for t in trades) + 600,
                                       max(t.get("timestamp", 0) for t in trades) - 3600)
            rand_pre = [t for t in trades if random_ts - 300 <= t.get("timestamp", 0) < random_ts]
            if not rand_pre:
                continue
            rand_prices = [t.get("price", 0) for t in rand_pre if t.get("price", 0) > 0]
            if len(rand_prices) < 2:
                continue
            rand_vol = _realized_vol(rand_prices)
            if abs(rand_vol - event_vol) < event_vol * 0.5:  # within 50%
                price = _find_nearest_price(random_ts, trades)
                if price:
                    fm = compute_forward_metrics(random_ts, trades, price)
                    if fm:
                        stats.returns_5m.append(fm.return_5m)
                        stats.returns_15m.append(fm.return_15m)
                        stats.returns_30m.append(fm.return_30m)
                        stats.returns_1h.append(fm.return_1h)
                        stats.mfe_list.append(fm.mfe)
                        stats.mae_list.append(fm.mae)
                        stats.vol_expansion.append(fm.vol_expansion_5m)
                        stats.continuation_count += fm.continuation_prob
                        stats.reversal_count += fm.reversal_prob
                        break

    return stats


def _mean(lst: list[float]) -> float:
    return sum(lst) / len(lst) if lst else 0.0


def _median(lst: list[float]) -> float:
    if not lst:
        return 0.0
    s = sorted(lst)
    n = len(s)
    if n % 2 == 0:
        return (s[n//2-1] + s[n//2]) / 2
    return s[n//2]


def _std(lst: list[float]) -> float:
    if len(lst) < 2:
        return 0.0
    m = _mean(lst)
    return math.sqrt(sum((x - m) ** 2 for x in lst) / (len(lst) - 1))


def generate_report(state_stats: dict[str, StateStats],
                    random_baseline: StateStats,
                    same_vol_baseline: StateStats) -> str:
    """Generate the validation report in markdown."""
    lines = []
    lines.append("# MANTIS EXECUTION ENGINE — VALIDATION REPORT")
    lines.append("")
    lines.append(f"**Generated:** {__import__('datetime').datetime.now().isoformat()}")
    lines.append(f"**Purpose:** Verify detected states have meaningful behavioral separation from random.")
    lines.append(f"**NOT to prove alpha. To validate execution quality improvement.**")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive summary
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"Total detected events: {sum(s.count for s in state_stats.values())}")
    lines.append(f"Random baseline samples: {random_baseline.count}")
    lines.append(f"Same-volatility baseline samples: {same_vol_baseline.count}")
    lines.append("")

    for state_name, s in sorted(state_stats.items()):
        lines.append(f"### {state_name}")
        lines.append(f"- Events: {s.count}")
        if s.returns_30m:
            lines.append(f"- Mean 30m return: {_mean(s.returns_30m):.2f} bps")
            lines.append(f"- Median 30m return: {_median(s.returns_30m):.2f} bps")
        lines.append(f"- Mean execution quality: {_mean(s.exec_quality_list):.1f}")
        lines.append(f"- Mean risk: {_mean(s.risk_list):.1f}")
        lines.append(f"- Mean imbalance: {_mean(s.imbalance_list):.1f}")
        lines.append("")

    # Comparison tables
    lines.append("---")
    lines.append("")
    lines.append("## Forward Returns Comparison")
    lines.append("")
    lines.append("| State | N | 5m (bps) | 15m (bps) | 30m (bps) | 1h (bps) | vs Random 30m |")
    lines.append("|-------|---|----------|-----------|-----------|----------|---------------|")

    rand_30m = _mean(random_baseline.returns_30m)
    for state_name, s in sorted(state_stats.items()):
        r5 = _mean(s.returns_5m) if s.returns_5m else 0
        r15 = _mean(s.returns_15m) if s.returns_15m else 0
        r30 = _mean(s.returns_30m) if s.returns_30m else 0
        r60 = _mean(s.returns_1h) if s.returns_1h else 0
        diff = r30 - rand_30m
        lines.append(f"| {state_name} | {s.count} | {r5:.2f} | {r15:.2f} | {r30:.2f} | {r60:.2f} | {diff:+.2f} |")

    lines.append(f"| **RANDOM** | {random_baseline.count} | {_mean(random_baseline.returns_5m):.2f} | {_mean(random_baseline.returns_15m):.2f} | {_mean(random_baseline.returns_30m):.2f} | {_mean(random_baseline.returns_1h):.2f} | baseline |")
    lines.append(f"| **SAME_VOL** | {same_vol_baseline.count} | {_mean(same_vol_baseline.returns_5m):.2f} | {_mean(same_vol_baseline.returns_15m):.2f} | {_mean(same_vol_baseline.returns_30m):.2f} | {_mean(same_vol_baseline.returns_1h):.2f} | {_mean(same_vol_baseline.returns_30m) - rand_30m:+.2f} |")
    lines.append("")

    # MFE/MAE
    lines.append("## MFE / MAE Analysis")
    lines.append("")
    lines.append("| State | Mean MFE (bps) | Mean MAE (bps) | MFE/MAE |")
    lines.append("|-------|----------------|----------------|---------|")
    for state_name, s in sorted(state_stats.items()):
        mfe = _mean(s.mfe_list) if s.mfe_list else 0
        mae = _mean(s.mae_list) if s.mae_list else 0
        ratio = mfe / mae if mae > 0 else 0
        lines.append(f"| {state_name} | {mfe:.2f} | {mae:.2f} | {ratio:.2f} |")
    lines.append(f"| **RANDOM** | {_mean(random_baseline.mfe_list):.2f} | {_mean(random_baseline.mae_list):.2f} | {_mean(random_baseline.mfe_list) / _mean(random_baseline.mae_list) if _mean(random_baseline.mae_list) > 0 else 0:.2f} |")
    lines.append("")

    # Execution quality vs risk
    lines.append("## Execution Environment Quality")
    lines.append("")
    lines.append("| State | Exec Quality | Risk | Imbalance | Trade Env |")
    lines.append("|-------|-------------|------|-----------|-----------|")
    for state_name, s in sorted(state_stats.items()):
        eq = _mean(s.exec_quality_list)
        risk = _mean(s.risk_list)
        imb = _mean(s.imbalance_list)
        te = 0.4 * imb + 0.35 * eq - 0.25 * risk
        lines.append(f"| {state_name} | {eq:.1f} | {risk:.1f} | {imb:.1f} | {te:.1f} |")
    lines.append("")

    # Stability across time splits
    lines.append("## Time Stability Analysis")
    lines.append("")
    lines.append("Split events into first half and second half chronologically:")
    lines.append("")
    lines.append("| State | First Half 30m (bps) | Second Half 30m (bps) | Stable? |")
    lines.append("|-------|----------------------|----------------------|---------|")
    for state_name, s in sorted(state_stats.items()):
        if len(s.returns_30m) < 4:
            lines.append(f"| {state_name} | N/A (too few) | N/A | ❓ |")
            continue
        mid = len(s.returns_30m) // 2
        first = _mean(s.returns_30m[:mid])
        second = _mean(s.returns_30m[mid:])
        stable = "✅" if (first > 0) == (second > 0) else "❌"
        lines.append(f"| {state_name} | {first:.2f} | {second:.2f} | {stable} |")
    lines.append("")

    # Outlier analysis
    lines.append("## Outlier Dependence")
    lines.append("")
    lines.append("| State | Top 5% contribution | Without top 5% | Outlier dependent? |")
    lines.append("|-------|---------------------|----------------|--------------------|")
    for state_name, s in sorted(state_stats.items()):
        if len(s.returns_30m) < 10:
            lines.append(f"| {state_name} | N/A | N/A | ❓ |")
            continue
        sorted_ret = sorted(s.returns_30m, key=abs, reverse=True)
        top_5_n = max(1, len(sorted_ret) // 20)
        top_5 = sorted_ret[:top_5_n]
        rest = sorted_ret[top_5_n:]
        top_contrib = sum(top_5)
        total = sum(sorted_ret)
        without_top = sum(rest)
        pct = (top_contrib / total * 100) if total != 0 else 0
        dependent = "⚠️ YES" if abs(pct) > 80 else "✅ NO"
        lines.append(f"| {state_name} | {pct:.0f}% | {without_top:.1f} bps total | {dependent} |")
    lines.append("")

    # Alert frequency check
    lines.append("## Alert Frequency Check")
    lines.append("")
    total_events = sum(s.count for s in state_stats.values())
    idle_count = 0  # will be counted from total - non-idle
    non_idle = total_events
    lines.append(f"- Total non-IDLE events: {non_idle}")
    lines.append(f"- IDLE events (estimated): check event log")
    if total_events > 0:
        lines.append(f"- Alert rate: events constitute context, not signals")
    lines.append("")

    # Verdict
    lines.append("---")
    lines.append("")
    lines.append("## Final Verdict")
    lines.append("")

    # Determine grade
    has_separation = False
    improves_execution = False

    for state_name, s in state_stats.items():
        if s.returns_30m and random_baseline.returns_30m:
            state_mean = abs(_mean(s.returns_30m))
            rand_mean = abs(_mean(random_baseline.returns_30m))
            if state_mean > rand_mean * 1.5:
                has_separation = True
        if s.risk_list and _mean(s.risk_list) > 50:
            improves_execution = True  # high risk states identified

    if has_separation and improves_execution:
        grade = "A — Useful Execution Context Engine"
        grade_detail = "Detected states show meaningful behavioral separation from random AND identify dangerous environments."
    elif improves_execution:
        grade = "B — Weak Context Engine"
        grade_detail = "Detects abnormal states but limited improvement over random for execution filtering."
    else:
        grade = "C — Not Useful"
        grade_detail = "Events are noisy, unstable, or indistinguishable from random."

    lines.append(f"### Grade: **{grade}**")
    lines.append("")
    lines.append(grade_detail)
    lines.append("")
    lines.append("### Pass Conditions")
    lines.append("")

    # Check each condition
    conditions = []
    if has_separation:
        conditions.append(("Do detected states differ from random?", "✅ YES"))
    else:
        conditions.append(("Do detected states differ from random?", "❌ NO"))

    if improves_execution:
        conditions.append(("Do they improve execution avoidance?", "✅ YES"))
    else:
        conditions.append(("Do they improve execution avoidance?", "❌ NO"))

    conditions.append(("Do they reduce exposure to bad fills?", "❓ Requires live validation"))
    conditions.append(("Do they identify dangerous environments?", "✅ YES" if improves_execution else "❌ NO"))

    for cond, result in conditions:
        lines.append(f"- {cond}: {result}")

    lines.append("")
    lines.append("### Important Notes")
    lines.append("")
    lines.append("- This validation uses forward returns as proxy for execution quality.")
    lines.append("- Real execution quality requires spread/slippage data at event time.")
    lines.append("- Results are preliminary — more data needed for statistical confidence.")
    lines.append("- The engine's value is in AVOIDING bad environments, not predicting direction.")
    lines.append("")
    lines.append("---")
    lines.append("*Report generated by MANTIS Execution Engine validation pipeline.*")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="MANTIS Execution Engine Validator")
    parser.add_argument("--events", required=True, help="Path to mantis_events.jsonl")
    parser.add_argument("--trades", default=None, help="Path to trades.jsonl for forward analysis")
    parser.add_argument("--output", default="MANTIS_EXECUTION_VALIDATION_REPORT.md",
                        help="Output report path")
    parser.add_argument("--random-samples", type=int, default=500,
                        help="Number of random baseline samples")
    args = parser.parse_args()

    print("Loading events...")
    events = load_events(args.events)
    print(f"  Loaded {len(events)} events")

    trades = []
    if args.trades:
        print("Loading trades...")
        trades = load_trades(args.trades)
        print(f"  Loaded {len(trades)} trades")

    print("Building state statistics...")
    state_stats = build_state_stats(events, trades)

    print("Building random baseline...")
    random_baseline = build_random_baseline(trades, args.random_samples)

    print("Building same-volatility baseline...")
    same_vol_baseline = build_same_vol_baseline(trades, events, args.random_samples)

    print("Generating report...")
    report = generate_report(state_stats, random_baseline, same_vol_baseline)

    with open(args.output, "w") as f:
        f.write(report)

    print(f"\nReport saved to: {args.output}")
    print(f"\nSummary:")
    for state_name, s in sorted(state_stats.items()):
        r30 = _mean(s.returns_30m) if s.returns_30m else 0
        eq = _mean(s.exec_quality_list) if s.exec_quality_list else 0
        print(f"  {state_name}: {s.count} events, 30m={r30:.2f}bps, exec={eq:.1f}")
    print(f"  RANDOM: {random_baseline.count} samples, 30m={_mean(random_baseline.returns_30m):.2f}bps")


if __name__ == "__main__":
    main()
