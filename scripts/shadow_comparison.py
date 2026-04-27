#!/usr/bin/env python3
"""
MANTIS Shadow Comparison — Validates original vs shadow blacklist/watchlist behavior.

Produces three-way comparison:
  1. Original live behavior (all events, no filtering)
  2. Shadow blacklist behavior (excluding blacklisted events)
  3. Shadow watchlist behavior (watchlist events only)

Requirements for blacklist promotion to production:
  - ≥100 events per type
  - Positive net expectancy at 4bps
  - Stable across chronological splits
  - No threshold tuning

This script does NOT modify any live data. Read-only analysis.
"""

import json
import os
import sys
import csv
from collections import defaultdict
from datetime import datetime, timezone, timedelta


# ============================================================
# Blacklist / Watchlist definitions (must match config.py)
# ============================================================

BLACKLISTED_TYPES = {"sell_exhaustion", "sell_imbalance", "sell_cluster"}
WATCHLISTED_TYPES = {"sell_absorption", "down_break", "up_break"}


def is_blacklisted(event_type: str, side: str) -> bool:
    for bl in BLACKLISTED_TYPES:
        if bl in event_type or bl in side:
            return True
    return False


def is_watchlisted(event_type: str, side: str) -> bool:
    for wt in WATCHLISTED_TYPES:
        if wt in event_type or wt in side:
            return True
    return False


# ============================================================
# Data Loading
# ============================================================

def load_events(path: str) -> list[dict]:
    events = []
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


# ============================================================
# Analysis
# ============================================================

def compute_stats(events: list[dict], horizon: int = 60, cost_bps: float = 4.0) -> dict:
    """Compute outcome statistics for a set of events."""
    return_field = f"future_return_{horizon}s"
    valid = [e for e in events if e.get("forward", {}).get(return_field) is not None]

    if not valid:
        return {"n": 0, "n_with_outcome": 0}

    returns = []
    for e in valid:
        fwd = e["forward"]
        raw = fwd.get(return_field, 0)
        # Adjust for sell-side (flip sign for directional return)
        side = e.get("side", "")
        is_sell = any(kw in side.lower() for kw in ["sell", "bearish", "high_sweep", "down_break", "above_vwap"])
        ret = -raw if is_sell else raw
        returns.append(ret)

    net = [r - cost_bps for r in returns]
    wins = [r for r in net if r > 0]
    losses = [r for r in net if r <= 0]
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0

    return {
        "n": len(events),
        "n_with_outcome": len(valid),
        "mean_gross_bps": round(sum(returns) / len(returns), 2),
        "mean_net_bps": round(sum(net) / len(net), 2),
        "winrate": round(len(wins) / len(net), 4) if net else 0,
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss > 0 else float('inf'),
        "worst_loss_bps": round(min(returns), 2) if returns else 0,
    }


def compute_type_breakdown(events: list[dict], horizon: int = 60, cost_bps: float = 4.0) -> dict:
    """Breakdown by event_type × side."""
    groups = defaultdict(list)
    for e in events:
        key = f"{e['event_type']}|{e['side']}"
        groups[key].append(e)

    results = {}
    for key, evts in sorted(groups.items()):
        results[key] = compute_stats(evts, horizon, cost_bps)
    return results


def compute_time_split(events: list[dict], horizon: int = 60, cost_bps: float = 4.0) -> dict:
    """Split events chronologically and compare."""
    sorted_by_time = sorted(events, key=lambda e: e.get("timestamp", 0))
    n = len(sorted_by_time)
    mid = n // 2

    return {
        "first_half": compute_stats(sorted_by_time[:mid], horizon, cost_bps),
        "second_half": compute_stats(sorted_by_time[mid:], horizon, cost_bps),
    }


def check_promotion_criteria(events: list[dict], event_type: str) -> dict:
    """
    Check if a watchlist event type meets promotion criteria:
      - ≥100 events
      - Positive net expectancy at 4bps
      - Stable across chronological splits
      - No threshold tuning
    """
    filtered = [e for e in events if event_type in e.get("event_type", "") or
                event_type in e.get("side", "")]

    stats = compute_stats(filtered, horizon=60, cost_bps=4.0)
    time_split = compute_time_split(filtered, horizon=60, cost_bps=4.0)

    n = stats.get("n_with_outcome", 0)
    net = stats.get("mean_net_bps", -999)
    first_net = time_split.get("first_half", {}).get("mean_net_bps", -999)
    second_net = time_split.get("second_half", {}).get("mean_net_bps", -999)

    stable = (first_net > 0 and second_net > 0) or (first_net < 0 and second_net < 0)
    positive_net = net > 0
    sufficient_sample = n >= 100

    criteria = {
        "event_type": event_type,
        "n": n,
        "n_criterion": "✅" if sufficient_sample else "❌",
        "mean_net_4bps": net,
        "positive_net_criterion": "✅" if positive_net else "❌",
        "first_half_net": first_net,
        "second_half_net": second_net,
        "stable_criterion": "✅" if stable else "❌",
        "promotable": sufficient_sample and positive_net and stable,
    }
    return criteria


# ============================================================
# Report Generation
# ============================================================

def generate_report(events: list[dict]) -> str:
    """Generate SHADOW_COMPARISON_REPORT.md content."""
    n = len(events)
    tz8 = timezone(timedelta(hours=8))
    now = datetime.now(tz8)

    # Classify events
    all_events = events
    blacklisted = [e for e in events if is_blacklisted(e.get("event_type", ""), e.get("side", ""))]
    non_blacklisted = [e for e in events if not is_blacklisted(e.get("event_type", ""), e.get("side", ""))]
    watchlisted = [e for e in events if is_watchlisted(e.get("event_type", ""), e.get("side", ""))]

    lines = []
    lines.append("# SHADOW COMPARISON REPORT")
    lines.append("")
    lines.append(f"**Generated:** {now.strftime('%Y-%m-%d %H:%M:%S')} CST")
    lines.append(f"**Total events:** {n}")
    lines.append(f"**Blacklisted:** {len(blacklisted)}")
    lines.append(f"**Non-blacklisted:** {len(non_blacklisted)}")
    lines.append(f"**Watchlisted:** {len(watchlisted)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 1: Three-way comparison
    lines.append("## 1. Three-Way Behavior Comparison (60s horizon, net @ 4bps)")
    lines.append("")
    stats_all = compute_stats(all_events, 60, 4.0)
    stats_non_bl = compute_stats(non_blacklisted, 60, 4.0)
    stats_bl = compute_stats(blacklisted, 60, 4.0)
    stats_wl = compute_stats(watchlisted, 60, 4.0)

    lines.append("| Metric | ALL (original) | Non-BL (after) | Blacklisted | Watchlisted |")
    lines.append("|--------|---------------|----------------|-------------|-------------|")
    lines.append(f"| N | {stats_all['n']} | {stats_non_bl['n']} | {stats_bl['n']} | {stats_wl['n']} |")
    lines.append(f"| N w/ outcome | {stats_all.get('n_with_outcome', 0)} | {stats_non_bl.get('n_with_outcome', 0)} | {stats_bl.get('n_with_outcome', 0)} | {stats_wl.get('n_with_outcome', 0)} |")
    lines.append(f"| Mean gross | {stats_all.get('mean_gross_bps', 'N/A')} | {stats_non_bl.get('mean_gross_bps', 'N/A')} | {stats_bl.get('mean_gross_bps', 'N/A')} | {stats_wl.get('mean_gross_bps', 'N/A')} |")
    lines.append(f"| Mean net @4bps | {stats_all.get('mean_net_bps', 'N/A')} | {stats_non_bl.get('mean_net_bps', 'N/A')} | {stats_bl.get('mean_net_bps', 'N/A')} | {stats_wl.get('mean_net_bps', 'N/A')} |")
    lines.append(f"| Winrate | {stats_all.get('winrate', 'N/A')} | {stats_non_bl.get('winrate', 'N/A')} | {stats_bl.get('winrate', 'N/A')} | {stats_wl.get('winrate', 'N/A')} |")
    lines.append(f"| PF | {stats_all.get('profit_factor', 'N/A')} | {stats_non_bl.get('profit_factor', 'N/A')} | {stats_bl.get('profit_factor', 'N/A')} | {stats_wl.get('profit_factor', 'N/A')} |")
    lines.append("")

    # Section 2: Blacklist impact
    lines.append("## 2. Blacklist Impact (Original vs After Blacklist Removal)")
    lines.append("")
    bl_impact = stats_all.get('mean_net_bps', 0) - stats_non_bl.get('mean_net_bps', 0)
    lines.append(f"- Events removed: {len(blacklisted)} ({len(blacklisted)/n*100:.1f}% of total)")
    lines.append(f"- Net @4bps before: {stats_all.get('mean_net_bps', 'N/A')} bps")
    lines.append(f"- Net @4bps after: {stats_non_bl.get('mean_net_bps', 'N/A')} bps")
    lines.append(f"- Impact: {bl_impact:+.2f} bps")
    lines.append("")

    # Section 3: Cost stress comparison
    lines.append("## 3. Cost Stress: Original vs After Blacklist")
    lines.append("")
    lines.append("| Cost | ALL Net | Non-BL Net | Delta |")
    lines.append("|------|---------|------------|-------|")
    for cost in [2, 4, 6]:
        s_all = compute_stats(all_events, 60, cost)
        s_non = compute_stats(non_blacklisted, 60, cost)
        delta = s_non.get('mean_net_bps', 0) - s_all.get('mean_net_bps', 0)
        lines.append(f"| {cost}bps | {s_all.get('mean_net_bps', 'N/A')} | {s_non.get('mean_net_bps', 'N/A')} | {delta:+.2f} |")
    lines.append("")

    # Section 4: Time stability
    lines.append("## 4. Time Stability (Non-Blacklisted Only)")
    lines.append("")
    ts = compute_time_split(non_blacklisted, 60, 4.0)
    first = ts.get("first_half", {})
    second = ts.get("second_half", {})
    lines.append("| Metric | First Half | Second Half |")
    lines.append("|--------|-----------|-------------|")
    lines.append(f"| N | {first.get('n', 0)} | {second.get('n', 0)} |")
    lines.append(f"| Mean net @4bps | {first.get('mean_net_bps', 'N/A')} bps | {second.get('mean_net_bps', 'N/A')} bps |")
    lines.append(f"| Winrate | {first.get('winrate', 'N/A')} | {second.get('winrate', 'N/A')} |")
    lines.append(f"| PF | {first.get('profit_factor', 'N/A')} | {second.get('profit_factor', 'N/A')} |")
    lines.append("")

    f_net = first.get('mean_net_bps', 0)
    s_net = second.get('mean_net_bps', 0)
    if (f_net > 0 and s_net > 0) or (f_net < 0 and s_net < 0):
        lines.append("**Stability:** ✅ Directionally consistent across halves.")
    else:
        lines.append("**Stability:** ❌ Direction inconsistent across halves.")
    lines.append("")

    # Section 5: Watchlist promotion criteria
    lines.append("## 5. Watchlist Promotion Criteria Check")
    lines.append("")
    lines.append("**Requirements:** ≥100 events, positive net @4bps, stable across splits, no threshold tuning")
    lines.append("")
    lines.append("| Type | N | N≥100 | Net@4bps | Positive | 1st Half | 2nd Half | Stable | Promotable |")
    lines.append("|------|---|-------|----------|----------|----------|----------|--------|------------|")
    for wt in sorted(WATCHLISTED_TYPES):
        criteria = check_promotion_criteria(events, wt)
        lines.append(
            f"| {wt} | {criteria['n']} | {criteria['n_criterion']} | "
            f"{criteria['mean_net_4bps']:+.2f} | {criteria['positive_net_criterion']} | "
            f"{criteria['first_half_net']:+.2f} | {criteria['second_half_net']:+.2f} | "
            f"{criteria['stable_criterion']} | {'✅' if criteria['promotable'] else '❌'} |"
        )
    lines.append("")

    # Section 6: Blacklisted event individual performance
    lines.append("## 6. Blacklisted Events: Individual Performance (Diagnostics)")
    lines.append("")
    lines.append("These events are excluded from tradeable set in shadow mode.")
    lines.append("Shown for diagnostic purposes only.")
    lines.append("")
    bl_breakdown = compute_type_breakdown(blacklisted, 60, 4.0)
    lines.append("| Type|Side | N | Gross@60s | Net@4bps | Winrate | PF |")
    lines.append("|-----|-----|---|-----------|----------|---------|-----|")
    for key, stats in bl_breakdown.items():
        if stats.get('n_with_outcome', 0) == 0:
            continue
        lines.append(f"| {key} | {stats.get('n_with_outcome', 0)} | "
                     f"{stats.get('mean_gross_bps', 'N/A')} | "
                     f"{stats.get('mean_net_bps', 'N/A')} | "
                     f"{stats.get('winrate', 'N/A')} | "
                     f"{stats.get('profit_factor', 'N/A')} |")
    lines.append("")

    # Section 7: Watchlisted event individual performance
    lines.append("## 7. Watchlisted Events: Current Performance (Candidates)")
    lines.append("")
    lines.append("These are candidates. NOT tradeable. Diagnostic only.")
    lines.append("")
    wl_breakdown = compute_type_breakdown(watchlisted, 60, 4.0)
    lines.append("| Type|Side | N | Gross@60s | Net@4bps | Winrate | PF |")
    lines.append("|-----|-----|---|-----------|----------|---------|-----|")
    for key, stats in wl_breakdown.items():
        if stats.get('n_with_outcome', 0) == 0:
            continue
        lines.append(f"| {key} | {stats.get('n_with_outcome', 0)} | "
                     f"{stats.get('mean_gross_bps', 'N/A')} | "
                     f"{stats.get('mean_net_bps', 'N/A')} | "
                     f"{stats.get('winrate', 'N/A')} | "
                     f"{stats.get('profit_factor', 'N/A')} |")
    lines.append("")

    # Section 8: Promotion decision
    lines.append("## 8. Promotion Decision")
    lines.append("")
    any_promotable = False
    for wt in sorted(WATCHLISTED_TYPES):
        criteria = check_promotion_criteria(events, wt)
        if criteria['promotable']:
            any_promotable = True
            lines.append(f"- **{wt}**: ✅ READY FOR PROMOTION (all criteria met)")
        else:
            reasons = []
            if not criteria['n_criterion'].startswith("✅"):
                reasons.append(f"sample too small ({criteria['n']})")
            if not criteria['positive_net_criterion'].startswith("✅"):
                reasons.append(f"net negative ({criteria['mean_net_4bps']:+.2f})")
            if not criteria['stable_criterion'].startswith("✅"):
                reasons.append("unstable across splits")
            lines.append(f"- **{wt}**: ❌ NOT READY — {', '.join(reasons)}")
    lines.append("")
    if not any_promotable:
        lines.append("**Decision: KEEP SHADOW MODE** — No event type meets all promotion criteria.")
        lines.append("")
        lines.append("No blacklist enforcement in production until validated with:")
        lines.append("- ≥100 events per type")
        lines.append("- Positive net expectancy at 4bps")
        lines.append("- Stable across chronological splits")
        lines.append("- No threshold tuning")
    lines.append("")

    return "\n".join(lines)


# ============================================================
# Main
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="backend/data/events/events_with_outcomes.jsonl")
    parser.add_argument("--output-csv", default="backend/data/events/blacklist_watchlist_report.csv")
    parser.add_argument("--output-md", default="SHADOW_COMPARISON_REPORT.md")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}")
        print("Run the event engine first to collect events with outcomes.")
        sys.exit(1)

    print("Loading events...")
    events = load_events(args.input)
    print(f"  Loaded {len(events)} events")

    # Generate CSV report
    blacklisted = [e for e in events if is_blacklisted(e.get("event_type", ""), e.get("side", ""))]
    if blacklisted:
        os.makedirs(os.path.dirname(args.output_csv), exist_ok=True)
        with open(args.output_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["event_id", "timestamp", "event_type", "side", "price",
                             "composite_score", "reason"])
            for e in blacklisted:
                writer.writerow([
                    e.get("event_id", ""),
                    e.get("timestamp", ""),
                    e.get("event_type", ""),
                    e.get("side", ""),
                    e.get("price", ""),
                    e.get("scores", {}).get("composite_score", ""),
                    f"blacklisted:{e.get('event_type', '')}:{e.get('side', '')}",
                ])
        print(f"  Blacklist report CSV: {args.output_csv}")

    # Generate Markdown report
    report = generate_report(events)
    with open(args.output_md, 'w') as f:
        f.write(report)
    print(f"  Comparison report: {args.output_md}")

    # Print summary
    print("\n" + "=" * 60)
    print("SHADOW COMPARISON COMPLETE")
    print("=" * 60)
    non_bl = [e for e in events if not is_blacklisted(e.get("event_type", ""), e.get("side", ""))]
    stats_all = compute_stats(events, 60, 4.0)
    stats_non = compute_stats(non_bl, 60, 4.0)
    print(f"  ALL:  n={stats_all['n']}, net@4bps={stats_all.get('mean_net_bps', 'N/A')}, WR={stats_all.get('winrate', 'N/A')}")
    print(f"  Non-BL: n={stats_non['n']}, net@4bps={stats_non.get('mean_net_bps', 'N/A')}, WR={stats_non.get('winrate', 'N/A')}")

    for wt in sorted(WATCHLISTED_TYPES):
        criteria = check_promotion_criteria(events, wt)
        status = "✅ PROMOTABLE" if criteria['promotable'] else "❌ NOT READY"
        print(f"  {wt}: {status} (n={criteria['n']}, net={criteria['mean_net_4bps']:+.2f})")


if __name__ == "__main__":
    main()
