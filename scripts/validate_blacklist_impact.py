#!/usr/bin/env python3
"""
Validation comparison: before vs after blacklist/watchlist enforcement.

Loads event data and compares:
  - All events (before)
  - Non-blacklisted events only (after)

Reports the difference in performance to show impact of blacklist.

Usage:
    python3 scripts/validate_blacklist_impact.py \
        --input backend/data/events/events_with_outcomes.jsonl \
        --output-md BLACKLIST_VALIDATION_REPORT.md
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ============================================================
# Blacklist definition (must match config.py)
# ============================================================

BLACKLISTED_SIDES = {"sell_exhaustion", "sell_imbalance", "sell_cluster"}
WATCHLISTED_SIDES = {"sell_absorption", "down_break", "up_break"}
HORIZONS = [10, 30, 60, 120, 300]
COSTS = [2, 4, 6]


def is_blacklisted_side(side: str) -> bool:
    for bl in BLACKLISTED_SIDES:
        if bl in side:
            return True
    return False


def is_watchlisted_side(side: str) -> bool:
    for wt in WATCHLISTED_SIDES:
        if wt in side:
            return True
    return False


def load_events(path: str) -> list[dict]:
    events = []
    if not os.path.exists(path):
        print(f"[ERROR] File not found: {path}")
        sys.exit(1)
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def compute_stats(returns: list[float], cost: float = 0) -> dict:
    if not returns:
        return {"n": 0}
    net = [r - cost for r in returns]
    n = len(net)
    wins = [r for r in net if r > 0]
    losses = [r for r in net if r <= 0]
    avg = sum(net) / n
    wr = len(wins) / n if n > 0 else 0
    gp = sum(wins) if wins else 0
    gl = abs(sum(losses)) if losses else 0
    pf = gp / gl if gl > 0 else float('inf')
    return {
        "n": n, "avg_bps": round(avg, 2), "winrate": round(wr, 4),
        "profit_factor": round(pf, 3),
        "gross_avg_bps": round(sum(returns) / n, 2),
    }


def horizon_stats(events: list[dict], horizon: int) -> dict:
    field = f"future_return_{horizon}s"
    returns = []
    for e in events:
        # Check top-level first, then nested forward dict
        r = e.get(field)
        if r is None:
            fwd = e.get("forward", {})
            r = fwd.get(field)
        if r is not None:
            returns.append(r)
    return compute_stats(returns)


def horizon_stats_with_cost(events: list[dict], horizon: int, cost: float) -> dict:
    field = f"future_return_{horizon}s"
    returns = []
    for e in events:
        r = e.get(field)
        if r is None:
            fwd = e.get("forward", {})
            r = fwd.get(field)
        if r is not None:
            returns.append(r)
    return compute_stats(returns, cost)


def _get_forward(e: dict, field: str):
    """Get forward outcome from top-level or nested forward dict."""
    r = e.get(field)
    if r is None:
        fwd = e.get("forward", {})
        r = fwd.get(field)
    return r


def time_split(events: list[dict], horizon: int = 60) -> dict:
    field = f"future_return_{horizon}s"
    sorted_e = sorted(events, key=lambda e: e.get("timestamp", 0))
    valid = [e for e in sorted_e if _get_forward(e, field) is not None]
    if not valid:
        return {"first": {"n": 0}, "second": {"n": 0}}
    n = len(valid)
    mid = n // 2
    first = valid[:mid]
    second = valid[mid:]
    return {
        "first": compute_stats([_get_forward(e, field) for e in first]),
        "second": compute_stats([_get_forward(e, field) for e in second]),
    }


def type_breakdown(events: list[dict], horizon: int = 60) -> dict:
    field = f"future_return_{horizon}s"
    by_type = defaultdict(list)
    for e in events:
        r = _get_forward(e, field)
        if r is not None:
            by_type[e.get("side", e.get("event_type", "unknown"))].append(r)
    result = {}
    for side, returns in sorted(by_type.items()):
        result[side] = compute_stats(returns)
    return result


def generate_report(all_events: list[dict]) -> str:
    tz8 = timezone(timedelta(hours=8))
    now = datetime.now(tz8).strftime('%Y-%m-%d %H:%M:%S')

    # Split events
    blacklisted = [e for e in all_events if is_blacklisted_side(e.get("side", ""))]
    non_blacklisted = [e for e in all_events if not is_blacklisted_side(e.get("side", ""))]
    watchlisted = [e for e in all_events if is_watchlisted_side(e.get("side", ""))]

    lines = []
    lines.append("# BLACKLIST VALIDATION REPORT")
    lines.append("")
    lines.append(f"**Generated:** {now} CST")
    lines.append(f"**Total events:** {len(all_events)}")
    lines.append(f"**Blacklisted:** {len(blacklisted)}")
    lines.append(f"**Non-blacklisted:** {len(non_blacklisted)}")
    lines.append(f"**Watchlisted:** {len(watchlisted)}")
    lines.append("")

    # ── Blacklist breakdown ─────────────────────────────────
    lines.append("## 1. Blacklist Event Breakdown")
    lines.append("")
    bl_types = defaultdict(int)
    for e in blacklisted:
        bl_types[e.get("side", "unknown")] += 1
    lines.append("| Type | Count |")
    lines.append("|------|-------|")
    for t, c in sorted(bl_types.items()):
        lines.append(f"| {t} | {c} |")
    lines.append(f"| **TOTAL** | **{len(blacklisted)}** |")
    lines.append("")

    # ── Before vs After comparison ──────────────────────────
    lines.append("## 2. Before vs After Blacklist")
    lines.append("")
    lines.append("| Horizon | Metric | ALL (before) | Non-BL (after) | Delta |")
    lines.append("|---------|--------|-------------|----------------|-------|")
    for h in HORIZONS:
        before = horizon_stats(all_events, h)
        after = horizon_stats(non_blacklisted, h)
        if before["n"] == 0 or after["n"] == 0:
            continue
        delta = after["avg_bps"] - before["avg_bps"]
        lines.append(
            f"| {h}s | Avg | {before['avg_bps']:+.2f}bps | {after['avg_bps']:+.2f}bps | {delta:+.2f} |"
        )
        lines.append(
            f"| {h}s | WR | {before['winrate']:.1%} | {after['winrate']:.1%} | {after['winrate']-before['winrate']:+.1%} |"
        )
    lines.append("")

    # ── Cost stress comparison ──────────────────────────────
    lines.append("## 3. Cost Stress: Before vs After")
    lines.append("")
    lines.append("| Cost | Horizon | ALL Net | Non-BL Net | Delta |")
    lines.append("|------|---------|---------|------------|-------|")
    for cost in COSTS:
        for h in [10, 30, 60]:
            before = horizon_stats_with_cost(all_events, h, cost)
            after = horizon_stats_with_cost(non_blacklisted, h, cost)
            if before["n"] == 0 or after["n"] == 0:
                continue
            delta = after["avg_bps"] - before["avg_bps"]
            lines.append(
                f"| {cost}bps | {h}s | {before['avg_bps']:+.2f} | {after['avg_bps']:+.2f} | {delta:+.2f} |"
            )
    lines.append("")

    # ── Blacklisted events: individual performance ──────────
    lines.append("## 4. Blacklisted Events: Individual Performance")
    lines.append("")
    lines.append("These events are excluded from tradeable set.")
    lines.append("")
    bl_type_stats = type_breakdown(blacklisted, 60)
    lines.append("| Side | N | Gross Avg (60s) | Winrate | PF |")
    lines.append("|------|---|-----------------|---------|-----|")
    for side, stats in sorted(bl_type_stats.items()):
        lines.append(
            f"| {side} | {stats['n']} | {stats['gross_avg_bps']:+.2f} | {stats['winrate']:.1%} | {stats['profit_factor']:.2f} |"
        )
    lines.append("")

    # ── Watchlisted events: current performance ─────────────
    lines.append("## 5. Watchlisted Events: Current Performance")
    lines.append("")
    lines.append("These are candidates. NOT tradeable. Diagnostic only.")
    lines.append("")
    wl_type_stats = type_breakdown(watchlisted, 60)
    lines.append("| Side | N | Gross Avg (60s) | Winrate | PF |")
    lines.append("|------|---|-----------------|---------|-----|")
    for side, stats in sorted(wl_type_stats.items()):
        lines.append(
            f"| {side} | {stats['n']} | {stats['gross_avg_bps']:+.2f} | {stats['winrate']:.1%} | {stats['profit_factor']:.2f} |"
        )
    lines.append("")

    # ── Time stability (non-blacklisted only) ───────────────
    lines.append("## 6. Time Stability (Non-Blacklisted Only)")
    lines.append("")
    ts = time_split(non_blacklisted, 60)
    first = ts.get("first", {})
    second = ts.get("second", {})
    lines.append("| Metric | First Half | Second Half |")
    lines.append("|--------|-----------|-------------|")
    lines.append(f"| N | {first.get('n', 0)} | {second.get('n', 0)} |")
    if first.get("n", 0) > 0:
        lines.append(f"| Avg (60s) | {first['avg_bps']:+.2f}bps | {second.get('avg_bps', 0):+.2f}bps |")
        lines.append(f"| Winrate | {first['winrate']:.1%} | {second.get('winrate', 0):.1%} |")
        lines.append(f"| PF | {first['profit_factor']:.2f} | {second.get('profit_factor', 0):.2f} |")
    lines.append("")

    # ── Impact summary ──────────────────────────────────────
    lines.append("## 7. Blacklist Impact Summary")
    lines.append("")
    before_60 = horizon_stats(all_events, 60)
    after_60 = horizon_stats(non_blacklisted, 60)
    if before_60["n"] > 0 and after_60["n"] > 0:
        improvement = after_60["avg_bps"] - before_60["avg_bps"]
        lines.append(f"- **Events removed:** {len(blacklisted)} ({len(blacklisted)/len(all_events)*100:.1f}%)")
        lines.append(f"- **Gross avg (60s) before:** {before_60['gross_avg_bps']:+.2f}bps")
        lines.append(f"- **Gross avg (60s) after:** {after_60['gross_avg_bps']:+.2f}bps")
        lines.append(f"- **Gross improvement:** {after_60['gross_avg_bps'] - before_60['gross_avg_bps']:+.2f}bps")
        lines.append(f"- **Winrate before:** {before_60['winrate']:.1%}")
        lines.append(f"- **Winrate after:** {after_60['winrate']:.1%}")
    lines.append("")
    lines.append("**Note:** Blacklist is NOT about improving performance.")
    lines.append("It is about removing structurally unsound detectors from tradeable logic.")
    lines.append("Performance improvement (if any) is a side effect, not the goal.")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Blacklist validation impact")
    parser.add_argument("--input", default="backend/data/events/events_with_outcomes.jsonl")
    parser.add_argument("--output-md", default="BLACKLIST_VALIDATION_REPORT.md")
    args = parser.parse_args()

    events = load_events(args.input)
    print(f"Loaded {len(events)} events")

    report = generate_report(events)
    with open(args.output_md, 'w') as f:
        f.write(report)
    print(f"Report written to {args.output_md}")

    # Summary
    bl = sum(1 for e in events if is_blacklisted_side(e.get("side", "")))
    nbl = len(events) - bl
    print(f"\nBlacklisted: {bl} / {len(events)} ({bl/len(events)*100:.1f}%)")
    print(f"Non-blacklisted: {nbl}")


if __name__ == "__main__":
    main()
