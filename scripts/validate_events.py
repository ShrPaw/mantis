#!/usr/bin/env python3
"""
MANTIS Event Engine — Validation Script
Loads event logs and produces strict, cost-aware statistical validation.

Usage:
    python scripts/validate_events.py [--jsonl path] [--costs 2,4,6]

Philosophy:
- No curve fitting
- No parameter optimization
- No claiming profitability from small samples
- No ML
- No lookahead bias
- Every result includes sample-size warnings
- Gross-only results are NEVER reported without costs
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ============================================================
# Data Loading
# ============================================================

@dataclass
class EventRecord:
    event_id: str
    timestamp: float
    event_type: str
    side: str
    price: float
    strength_score: float
    confidence_score: float
    noise_score: float
    composite_score: float
    explanation: str
    regime: str
    # Forward outcomes
    future_return_10s: Optional[float] = None
    future_return_30s: Optional[float] = None
    future_return_60s: Optional[float] = None
    future_return_120s: Optional[float] = None
    future_return_300s: Optional[float] = None
    mfe_30s: Optional[float] = None
    mae_30s: Optional[float] = None
    mfe_120s: Optional[float] = None
    mae_120s: Optional[float] = None
    hit_tp_10: Optional[bool] = None
    hit_tp_20: Optional[bool] = None
    hit_sl_10: Optional[bool] = None
    hit_sl_20: Optional[bool] = None
    # Hour for time analysis
    hour: int = 0


def load_jsonl(path: str) -> list[EventRecord]:
    """Load events from JSONL file."""
    events = []
    if not os.path.exists(path):
        print(f"[WARN] File not found: {path}")
        return events

    with open(path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                fwd = d.get("forward", {})
                events.append(EventRecord(
                    event_id=d.get("event_id", ""),
                    timestamp=d.get("timestamp", 0),
                    event_type=d.get("event_type", ""),
                    side=d.get("side", ""),
                    price=d.get("price", 0),
                    strength_score=d.get("scores", {}).get("strength_score", 0),
                    confidence_score=d.get("scores", {}).get("confidence_score", 0),
                    noise_score=d.get("scores", {}).get("noise_score", 0),
                    composite_score=d.get("scores", {}).get("composite_score", 0),
                    explanation=d.get("explanation", ""),
                    regime=d.get("context_metrics", {}).get("regime", "unknown"),
                    future_return_10s=fwd.get("future_return_10s"),
                    future_return_30s=fwd.get("future_return_30s"),
                    future_return_60s=fwd.get("future_return_60s"),
                    future_return_120s=fwd.get("future_return_120s"),
                    future_return_300s=fwd.get("future_return_300s"),
                    mfe_30s=fwd.get("max_favorable_excursion_30s"),
                    mae_30s=fwd.get("max_adverse_excursion_30s"),
                    mfe_120s=fwd.get("max_favorable_excursion_120s"),
                    mae_120s=fwd.get("max_adverse_excursion_120s"),
                    hit_tp_10=fwd.get("hit_tp_0_10pct"),
                    hit_tp_20=fwd.get("hit_tp_0_20pct"),
                    hit_sl_10=fwd.get("hit_sl_0_10pct"),
                    hit_sl_20=fwd.get("hit_sl_0_20pct"),
                    hour=int((d.get("timestamp", 0) % 86400) / 3600),
                ))
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[WARN] Line {line_num}: {e}")

    return events


def load_csv(path: str) -> list[EventRecord]:
    """Load events from CSV file."""
    events = []
    if not os.path.exists(path):
        print(f"[WARN] File not found: {path}")
        return events

    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                def safe_float(v):
                    if v is None or v == '' or v == 'None':
                        return None
                    return float(v)

                def safe_bool(v):
                    if v is None or v == '' or v == 'None':
                        return None
                    return v == 'True'

                ts = float(row.get("timestamp", 0))
                events.append(EventRecord(
                    event_id=row.get("event_id", ""),
                    timestamp=ts,
                    event_type=row.get("event_type", ""),
                    side=row.get("side", ""),
                    price=float(row.get("price", 0)),
                    strength_score=float(row.get("strength_score", 0)),
                    confidence_score=float(row.get("confidence_score", 0)),
                    noise_score=float(row.get("noise_score", 0)),
                    composite_score=float(row.get("composite_score", 0)),
                    explanation=row.get("explanation", ""),
                    regime=row.get("regime", "unknown"),
                    future_return_10s=safe_float(row.get("future_return_10s")),
                    future_return_30s=safe_float(row.get("future_return_30s")),
                    future_return_60s=safe_float(row.get("future_return_60s")),
                    future_return_120s=safe_float(row.get("future_return_120s")),
                    future_return_300s=safe_float(row.get("future_return_300s")),
                    hour=int((ts % 86400) / 3600),
                ))
            except (ValueError, KeyError) as e:
                pass

    return events


# ============================================================
# Analysis Functions
# ============================================================

def sample_warning(n: int) -> str:
    """Generate sample-size warning."""
    if n < 10:
        return "⚠️  CRITICALLY LOW SAMPLE (n<10) — results are meaningless"
    if n < 30:
        return "⚠️  LOW SAMPLE (n<30) — results are unreliable, need more data"
    if n < 100:
        return "⚠️  MODERATE SAMPLE (n<100) — treat with caution"
    return f"✓ Adequate sample size (n={n})"


def compute_stats(returns: list[float], costs_bps: float = 0) -> dict:
    """Compute statistics for a list of returns (in bps)."""
    if not returns:
        return {"n": 0}

    net_returns = [r - costs_bps for r in returns]
    n = len(returns)
    wins = [r for r in net_returns if r > 0]
    losses = [r for r in net_returns if r <= 0]

    avg_return = sum(net_returns) / n
    win_rate = len(wins) / n if n > 0 else 0
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else float('inf')

    sorted_returns = sorted(net_returns)
    median = sorted_returns[n // 2] if n > 0 else 0

    return {
        "n": n,
        "avg_return_bps": round(avg_return, 2),
        "median_return_bps": round(median, 2),
        "win_rate": round(win_rate, 4),
        "avg_win_bps": round(avg_win, 2),
        "avg_loss_bps": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 3),
        "gross_avg_bps": round(sum(returns) / n, 2),
        "costs_bps": costs_bps,
    }


def bin_by_strength(events: list[EventRecord], bins: int = 5) -> dict:
    """Bin events by strength score and compute stats per bin."""
    if not events:
        return {}

    sorted_events = sorted(events, key=lambda e: e.strength_score)
    n = len(sorted_events)
    bin_size = max(n // bins, 1)

    result = {}
    for i in range(bins):
        start = i * bin_size
        end = start + bin_size if i < bins - 1 else n
        bin_events = sorted_events[start:end]
        if not bin_events:
            continue

        low = bin_events[0].strength_score
        high = bin_events[-1].strength_score
        returns = [e.future_return_60s for e in bin_events if e.future_return_60s is not None]
        label = f"{low:.2f}-{high:.2f}"

        result[label] = {
            "n": len(bin_events),
            "returns": compute_stats(returns),
        }

    return result


def bin_by_confidence(events: list[EventRecord], bins: int = 5) -> dict:
    """Bin events by confidence score."""
    if not events:
        return {}

    sorted_events = sorted(events, key=lambda e: e.confidence_score)
    n = len(sorted_events)
    bin_size = max(n // bins, 1)

    result = {}
    for i in range(bins):
        start = i * bin_size
        end = start + bin_size if i < bins - 1 else n
        bin_events = sorted_events[start:end]
        if not bin_events:
            continue

        low = bin_events[0].confidence_score
        high = bin_events[-1].confidence_score
        returns = [e.future_return_60s for e in bin_events if e.future_return_60s is not None]
        label = f"{low:.2f}-{high:.2f}"

        result[label] = {
            "n": len(bin_events),
            "returns": compute_stats(returns),
        }

    return result


# ============================================================
# Main Report
# ============================================================

def generate_report(events: list[EventRecord], costs_bps: list[float]):
    """Generate full validation report."""
    print("=" * 70)
    print("MANTIS EVENT ENGINE — VALIDATION REPORT")
    print("=" * 70)
    print()

    # 1. Count by event type
    print("1. EVENT COUNT BY TYPE")
    print("-" * 40)
    by_type = defaultdict(list)
    for e in events:
        by_type[e.event_type].append(e)

    for etype, elist in sorted(by_type.items()):
        print(f"  {etype:25s} {len(elist):>6d}")
    print(f"  {'TOTAL':25s} {len(events):>6d}")
    print()

    # 2. Count by side
    print("2. EVENT COUNT BY SIDE")
    print("-" * 40)
    by_side = defaultdict(int)
    for e in events:
        by_side[e.side] += 1
    for side, count in sorted(by_side.items()):
        print(f"  {side:25s} {count:>6d}")
    print()

    # 3. Sample size warnings
    print("3. SAMPLE SIZE ASSESSMENT")
    print("-" * 40)
    completed = [e for e in events if e.future_return_60s is not None]
    print(f"  Total events: {len(events)}")
    print(f"  With 60s outcome: {len(completed)}")
    print(f"  {sample_warning(len(completed))}")
    print()

    if not completed:
        print("[STOP] No events with completed outcomes. Cannot validate.")
        return

    # 4. Performance by horizon (with costs)
    print("4. AVERAGE FUTURE RETURN BY HORIZON")
    print("-" * 70)
    horizons = [
        ("10s", lambda e: e.future_return_10s),
        ("30s", lambda e: e.future_return_30s),
        ("60s", lambda e: e.future_return_60s),
        ("120s", lambda e: e.future_return_120s),
        ("300s", lambda e: e.future_return_300s),
    ]

    header = f"  {'Horizon':>8s}"
    for cost in costs_bps:
        header += f"  {'Net@' + str(cost) + 'bps':>12s}"
    print(header)

    for label, getter in horizons:
        returns = [getter(e) for e in completed if getter(e) is not None]
        if not returns:
            continue
        line = f"  {label:>8s}"
        gross = sum(returns) / len(returns)
        for cost in costs_bps:
            net = gross - cost
            line += f"  {net:>+12.2f}"
        print(line)
    print()

    # 5. Win rate by horizon
    print("5. WIN RATE BY HORIZON (net after 4bps)")
    print("-" * 40)
    cost = 4.0
    for label, getter in horizons:
        returns = [getter(e) for e in completed if getter(e) is not None]
        if not returns:
            continue
        net = [r - cost for r in returns]
        wr = sum(1 for r in net if r > 0) / len(net)
        print(f"  {label:>8s}: {wr:>6.1%}  (n={len(returns)})")
    print()

    # 6. Expectancy gross vs net
    print("6. EXPECTANCY (60s horizon)")
    print("-" * 50)
    returns_60 = [e.future_return_60s for e in completed if e.future_return_60s is not None]
    for cost in costs_bps:
        stats = compute_stats(returns_60, cost)
        print(f"  Cost {cost}bps: avg={stats['avg_return_bps']:+.2f}bps  "
              f"WR={stats['win_rate']:.1%}  PF={stats['profit_factor']:.2f}  "
              f"median={stats['median_return_bps']:+.2f}bps")
    print()

    # 7. Profit factor
    print("7. PROFIT FACTOR (60s, net)")
    print("-" * 40)
    for cost in costs_bps:
        net = [r - cost for r in returns_60]
        gross_profit = sum(r for r in net if r > 0)
        gross_loss = abs(sum(r for r in net if r < 0))
        pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        print(f"  Cost {cost}bps: PF={pf:.3f}")
    print()

    # 8. MFE/MAE distribution
    print("8. MFE/MAE DISTRIBUTION (30s)")
    print("-" * 40)
    mfe_vals = [e.mfe_30s for e in completed if e.mfe_30s is not None]
    mae_vals = [e.mae_30s for e in completed if e.mae_30s is not None]
    if mfe_vals:
        mfe_vals.sort()
        print(f"  MFE: median={mfe_vals[len(mfe_vals)//2]:.2f}  "
              f"p25={mfe_vals[len(mfe_vals)//4]:.2f}  "
              f"p75={mfe_vals[3*len(mfe_vals)//4]:.2f}")
    if mae_vals:
        mae_vals.sort()
        print(f"  MAE: median={mae_vals[len(mae_vals)//2]:.2f}  "
              f"p25={mae_vals[len(mae_vals)//4]:.2f}  "
              f"p75={mae_vals[3*len(mae_vals)//4]:.2f}")
    print()

    # 9. Performance by hour
    print("9. PERFORMANCE BY HOUR (UTC, 60s net@4bps)")
    print("-" * 50)
    by_hour = defaultdict(list)
    for e in completed:
        if e.future_return_60s is not None:
            by_hour[e.hour].append(e.future_return_60s)
    for hour in sorted(by_hour.keys()):
        rets = by_hour[hour]
        net = [r - 4 for r in rets]
        avg = sum(net) / len(net)
        wr = sum(1 for r in net if r > 0) / len(net)
        print(f"  {hour:02d}:00  avg={avg:+.2f}bps  WR={wr:.0%}  n={len(rets)}")
    print()

    # 10. Performance by regime
    print("10. PERFORMANCE BY REGIME (60s net@4bps)")
    print("-" * 50)
    by_regime = defaultdict(list)
    for e in completed:
        if e.future_return_60s is not None:
            by_regime[e.regime].append(e.future_return_60s)
    for regime, rets in sorted(by_regime.items()):
        net = [r - 4 for r in rets]
        avg = sum(net) / len(net)
        wr = sum(1 for r in net if r > 0) / len(net)
        print(f"  {regime:20s} avg={avg:+.2f}bps  WR={wr:.0%}  n={len(rets)}")
    print()

    # 11. Performance by strength bin
    print("11. PERFORMANCE BY STRENGTH BIN (60s net@4bps)")
    print("-" * 60)
    str_bins = bin_by_strength(completed)
    for label, data in str_bins.items():
        r = data["returns"]
        print(f"  [{label}] n={r['n']:>4d}  avg={r['avg_return_bps']:+.2f}bps  "
              f"WR={r['win_rate']:.0%}  PF={r['profit_factor']:.2f}")
    print()

    # 12. Performance by confidence bin
    print("12. PERFORMANCE BY CONFIDENCE BIN (60s net@4bps)")
    print("-" * 60)
    conf_bins = bin_by_confidence(completed)
    for label, data in conf_bins.items():
        r = data["returns"]
        print(f"  [{label}] n={r['n']:>4d}  avg={r['avg_return_bps']:+.2f}bps  "
              f"WR={r['win_rate']:.0%}  PF={r['profit_factor']:.2f}")
    print()

    # 13. Long/short asymmetry
    print("13. LONG/SHORT ASYMMETRY (60s net@4bps)")
    print("-" * 50)
    for side_label, side_filter in [
        ("Buy-side", lambda e: "buy" in e.side or "bullish" in e.side or "low_sweep" in e.side),
        ("Sell-side", lambda e: "sell" in e.side or "bearish" in e.side or "high_sweep" in e.side),
    ]:
        subset = [e for e in completed if side_filter(e) and e.future_return_60s is not None]
        if not subset:
            continue
        rets = [e.future_return_60s - 4 for e in subset]
        avg = sum(rets) / len(rets)
        wr = sum(1 for r in rets if r > 0) / len(rets)
        print(f"  {side_label:12s} avg={avg:+.2f}bps  WR={wr:.0%}  n={len(subset)}")
    print()

    # 14. TP/SL hit rates
    print("14. TP/SL HIT RATES")
    print("-" * 40)
    tp10 = [e for e in completed if e.hit_tp_10 is not None]
    tp20 = [e for e in completed if e.hit_tp_20 is not None]
    sl10 = [e for e in completed if e.hit_sl_10 is not None]
    sl20 = [e for e in completed if e.hit_sl_20 is not None]
    if tp10:
        print(f"  TP 10bps: {sum(1 for e in tp10 if e.hit_tp_10) / len(tp10):.1%} (n={len(tp10)})")
    if tp20:
        print(f"  TP 20bps: {sum(1 for e in tp20 if e.hit_tp_20) / len(tp20):.1%} (n={len(tp20)})")
    if sl10:
        print(f"  SL 10bps: {sum(1 for e in sl10 if e.hit_sl_10) / len(sl10):.1%} (n={len(sl10)})")
    if sl20:
        print(f"  SL 20bps: {sum(1 for e in sl20 if e.hit_sl_20) / len(sl20):.1%} (n={len(sl20)})")
    print()

    # 15. Per-event-type detailed stats
    print("15. DETAILED STATS BY EVENT TYPE (60s)")
    print("-" * 70)
    for etype, elist in sorted(by_type.items()):
        completed_type = [e for e in elist if e.future_return_60s is not None]
        if not completed_type:
            print(f"  {etype}: no completed outcomes")
            continue

        returns = [e.future_return_60s for e in completed_type]
        print(f"\n  {etype.upper()} (n={len(completed_type)}, completed={len(completed_type)})")
        for cost in costs_bps:
            stats = compute_stats(returns, cost)
            print(f"    cost={cost}bps: avg={stats['avg_return_bps']:+.2f}bps  "
                  f"WR={stats['win_rate']:.0%}  PF={stats['profit_factor']:.2f}  "
                  f"median={stats['median_return_bps']:+.2f}bps")
    print()

    # Final warning
    print("=" * 70)
    print("⚠️  VALIDATION NOTES:")
    print("  - Results depend on event engine thresholds — not optimized")
    print("  - Forward returns measured from event price at detection time")
    print("  - Costs are per-trade (one-way); round-trip = 2x")
    print("  - Small samples produce unreliable statistics")
    print("  - This is NOT a trading system — it's a measurement tool")
    print("  - Do NOT optimize thresholds based on these numbers")
    print("=" * 70)


# ============================================================
# Entry Point
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="MANTIS Event Validation")
    parser.add_argument("--jsonl", default="data/events/events_raw.jsonl",
                        help="Path to JSONL event log")
    parser.add_argument("--csv", default="data/events/events_summary.csv",
                        help="Path to CSV event log")
    parser.add_argument("--costs", default="2,4,6",
                        help="Comma-separated cost assumptions in bps")
    args = parser.parse_args()

    costs = [float(c) for c in args.costs.split(",")]

    # Try JSONL first, fall back to CSV
    events = load_jsonl(args.jsonl)
    if not events:
        events = load_csv(args.csv)

    if not events:
        print("[ERROR] No events loaded. Run the event engine first to generate data.")
        sys.exit(1)

    print(f"Loaded {len(events)} events from {'JSONL' if events else 'CSV'}")
    generate_report(events, costs)


if __name__ == "__main__":
    main()
