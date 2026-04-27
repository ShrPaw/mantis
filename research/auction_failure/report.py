"""
Auction Failure Research — Report Generator

Generates AUCTION_FAILURE_RESEARCH_REPORT.md from collected event data.
No opinion. No narrative bias. Only what the data supports.
"""

from collections import defaultdict
from datetime import datetime, timezone, timedelta

from .models import AuctionEvent
from .config import AuctionFailureConfig
from .analytics import (
    compute_all_stats,
    compute_time_split_stats,
    compute_10min_blocks,
    compute_directional_returns,
)


def generate_report(events: list[AuctionEvent], config: AuctionFailureConfig) -> str:
    """Generate the full research report."""

    tz8 = timezone(timedelta(hours=8))
    now = datetime.now(tz8)

    lines = []
    lines.append("# AUCTION FAILURE RESEARCH REPORT")
    lines.append("")
    lines.append(f"**Generated:** {now.strftime('%Y-%m-%d %H:%M:%S')} CST")
    lines.append(f"**Module:** `research/auction_failure/`")
    lines.append(f"**Mode:** Shadow only — no production integration")
    lines.append(f"**Objective:** Do failed auctions or accepted breakouts produce repeatable net-positive behavior after costs?")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ============================================================
    # 1. DATA INTEGRITY
    # ============================================================
    lines.append("## 1. Data Integrity")
    lines.append("")

    n_total = len(events)
    n_complete = sum(1 for e in events if e.is_complete)
    by_class = defaultdict(int)
    for e in events:
        by_class[e.event_class] += 1

    if events:
        timestamps = [e.timestamp for e in events]
        t_min = min(timestamps)
        t_max = max(timestamps)
        span_min = (t_max - t_min) / 60
        t_start = datetime.fromtimestamp(t_min, tz=tz8)
        t_end = datetime.fromtimestamp(t_max, tz=tz8)
    else:
        span_min = 0
        t_start = t_end = now

    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total events | {n_total} |")
    lines.append(f"| Complete outcomes | {n_complete} |")
    lines.append(f"| Time span | {span_min:.1f} minutes |")
    lines.append(f"| Time range | {t_start.strftime('%H:%M:%S')} – {t_end.strftime('%H:%M:%S')} |")
    lines.append("")

    lines.append("### Event Class Distribution")
    lines.append("")
    lines.append(f"| Event Class | Count | % |")
    lines.append(f"|-------------|-------|---|")
    for ec, count in sorted(by_class.items()):
        pct = count / n_total * 100 if n_total > 0 else 0
        lines.append(f"| {ec} | {count} | {pct:.1f}% |")
    lines.append("")

    # Sufficiency
    if n_total == 0:
        lines.append("**⚠️ NO EVENTS DETECTED.** Awaiting data collection.")
        lines.append("")
        lines.append("### Next Steps")
        lines.append("")
        lines.append("1. **Start MANTIS backend:** `cd backend && python3 main.py`")
        lines.append("2. **Run the collector:** `python3 research/auction_failure/collector.py --duration 3600`")
        lines.append("3. **Or replay existing data:** `python3 research/auction_failure/replay.py --input <path> --format trades`")
        lines.append("")
        lines.append("### Module Status")
        lines.append("")
        lines.append("- ✅ Module architecture: complete")
        lines.append("- ✅ Four detectors: implemented")
        lines.append("- ✅ Outcome tracker: implemented (no lookahead bias)")
        lines.append("- ✅ Analytics engine: implemented")
        lines.append("- ✅ Report generator: implemented")
        lines.append("- ✅ CSV export: implemented")
        lines.append("- ✅ Collector (WebSocket): implemented")
        lines.append("- ✅ Offline replay: implemented")
        lines.append("- ⏳ Data collection: awaiting MANTIS backend connection")
        lines.append("- ⏳ Analysis: awaiting collected data")
        lines.append("")
        lines.append("### Detection Design Summary")
        lines.append("")
        lines.append("| Class | Aggression Condition | Failure Condition | Favorable |")
        lines.append("|-------|---------------------|-------------------|-----------|")
        lines.append("| failed_aggressive_sell | delta_ratio ≤ -0.40, percentile ≥ 0.85 | Price move < 3bps OR broke low and reclaimed | Price RISES |")
        lines.append("| failed_aggressive_buy | delta_ratio ≥ +0.40, percentile ≥ 0.85 | Price move < 3bps OR broke high and rejected | Price FALLS |")
        lines.append("| breakout_acceptance | Price outside range by 10% of range height | Holds outside for 15s, flow confirms (ratio ≥ 0.25) | Continuation |")
        lines.append("| breakout_rejection | Price WAS outside range | Returned inside within 30s, flow does NOT confirm | Reversal |")
        lines.append("")
        lines.append("All thresholds are **structural starting assumptions** (bps, percentile, ratio, fraction of range).")
        lines.append("They are NOT proven constants. They will NOT be tuned after results are observed.")
        lines.append("If no edge is found at these thresholds, the conclusion is \"no edge\" — not \"try different thresholds.\"")
        lines.append("")
        return "\n".join(lines)

    min_class_count = min(by_class.values()) if by_class else 0
    if min_class_count < 10:
        lines.append(f"**⚠️ INSUFFICIENT DATA** — smallest class has {min_class_count} events. Results are descriptive only.")
    elif min_class_count < 100:
        lines.append(f"**⚠️ PRELIMINARY DATA** — smallest class has {min_class_count} events. Need ≥100 for promotion.")
    lines.append("")

    # ============================================================
    # 2. EVENT DEFINITIONS
    # ============================================================
    lines.append("## 2. Event Definitions")
    lines.append("")
    lines.append("### Primitive Event Classes")
    lines.append("")
    lines.append("| Class | Side | Mechanism | Favorable Direction |")
    lines.append("|-------|------|-----------|-------------------|")
    lines.append("| failed_aggressive_sell | sell_pressure | Strong sell aggression, price fails to move lower | Price RISES |")
    lines.append("| failed_aggressive_buy | buy_pressure | Strong buy aggression, price fails to move higher | Price FALLS |")
    lines.append("| breakout_acceptance | upside_break / downside_break | Price breaks range, holds outside, flow confirms | Continuation |")
    lines.append("| breakout_rejection | sell_pressure / buy_pressure | Price breaks range, returns inside, flow fails | Reversal |")
    lines.append("")
    lines.append("### Detection Parameters (All Relative)")
    lines.append("")
    lines.append("| Parameter | Value | Type |")
    lines.append("|-----------|-------|------|")
    lines.append(f"| Delta ratio threshold | {config.aggression.delta_ratio_threshold} | ratio |")
    lines.append(f"| Delta percentile threshold | {config.aggression.delta_percentile_threshold} | rolling percentile |")
    lines.append(f"| Volume percentile threshold | {config.aggression.volume_percentile_threshold} | rolling percentile |")
    lines.append(f"| Max move for 'no response' | {config.failure.max_move_bps} bps | relative |")
    lines.append(f"| Reclaim window | {config.failure.reclaim_window_seconds}s | time |")
    lines.append(f"| Reclaim threshold | {config.failure.reclaim_threshold_bps} bps | relative |")
    lines.append(f"| Break distance (range fraction) | {config.breakout.break_distance_range_fraction} | fraction of range |")
    lines.append(f"| Min range height | {config.breakout.min_range_height_bps} bps | relative |")
    lines.append(f"| Flow confirmation ratio | {config.breakout.flow_confirmation_ratio} | ratio |")
    lines.append(f"| Hold window | {config.breakout.hold_window_seconds}s | time |")
    lines.append(f"| Rejection window | {config.breakout.rejection_window_seconds}s | time |")
    lines.append(f"| Detection window | {config.detection.detection_window_seconds}s | time |")
    lines.append(f"| Cooldown | {config.detection.cooldown_seconds}s | time |")
    lines.append("")
    lines.append("**These are structural starting assumptions, NOT proven constants.** They define what constitutes strong aggression and failure to continue in relative terms. They are chosen from market mechanics reasoning, not optimized from data. If results show no edge at these thresholds, the conclusion is \"no edge at these assumptions\" — not \"try different thresholds.\"")
    lines.append("")

    # ============================================================
    # 3. EVENT COUNTS
    # ============================================================
    lines.append("## 3. Event Counts")
    lines.append("")

    for ec in sorted(by_class.keys()):
        ec_events = [e for e in events if e.event_class == ec]
        ec_complete = sum(1 for e in ec_events if e.is_complete)
        sides = defaultdict(int)
        for e in ec_events:
            sides[e.side] += 1

        lines.append(f"### {ec}")
        lines.append(f"- Total: {len(ec_events)}")
        lines.append(f"- Complete: {ec_complete}")
        lines.append(f"- Sides: {dict(sides)}")
        lines.append("")

    # ============================================================
    # 4. OUTCOME TABLE BY EVENT CLASS
    # ============================================================
    lines.append("## 4. Outcome Table by Event Class")
    lines.append("")

    all_stats = compute_all_stats(events)
    horizons = ["5s", "10s", "30s", "60s", "120s", "300s"]

    # Gross return table
    lines.append("### 4.1 Gross Return (directional, bps)")
    lines.append("")
    header = "| Event Class |"
    separator = "|-------------|"
    for h in horizons:
        header += f" {h} |"
        separator += "------|"
    lines.append(header)
    lines.append(separator)

    for ec in sorted(all_stats.keys()):
        row = f"| {ec} |"
        for s in all_stats[ec]:
            if s.n > 0:
                row += f" {s.gross_return_bps:+.2f} (n={s.n}) |"
            else:
                row += " — |"
        lines.append(row)
    lines.append("")

    # Net return table at 4bps
    lines.append("### 4.2 Net Return @ 4bps (directional, bps)")
    lines.append("")
    header = "| Event Class |"
    separator = "|-------------|"
    for h in horizons:
        header += f" {h} |"
        separator += "------|"
    lines.append(header)
    lines.append(separator)

    for ec in sorted(all_stats.keys()):
        row = f"| {ec} |"
        for s in all_stats[ec]:
            if s.n > 0:
                row += f" {s.net_return_4bps:+.2f} |"
            else:
                row += " — |"
        lines.append(row)
    lines.append("")

    # Winrate table at 4bps
    lines.append("### 4.3 Winrate @ 4bps")
    lines.append("")
    header = "| Event Class |"
    separator = "|-------------|"
    for h in horizons:
        header += f" {h} |"
        separator += "------|"
    lines.append(header)
    lines.append(separator)

    for ec in sorted(all_stats.keys()):
        row = f"| {ec} |"
        for s in all_stats[ec]:
            if s.n > 0:
                row += f" {s.winrate_4bps:.1%} |"
            else:
                row += " — |"
        lines.append(row)
    lines.append("")

    # Profit factor table
    lines.append("### 4.4 Profit Factor @ 4bps")
    lines.append("")
    header = "| Event Class |"
    separator = "|-------------|"
    for h in horizons:
        header += f" {h} |"
        separator += "------|"
    lines.append(header)
    lines.append(separator)

    for ec in sorted(all_stats.keys()):
        row = f"| {ec} |"
        for s in all_stats[ec]:
            if s.n > 0:
                pf_str = f"{s.profit_factor_4bps:.2f}" if s.profit_factor_4bps != float('inf') else "∞"
                row += f" {pf_str} |"
            else:
                row += " — |"
        lines.append(row)
    lines.append("")

    # Detailed per-class stats at 60s
    lines.append("### 4.5 Detailed Stats at 60s Horizon")
    lines.append("")
    lines.append("| Event Class | N | Gross | Net@2 | Net@4 | Net@6 | WR@4 | PF@4 | MFE 30s | MAE 30s | MFE/MAE | Inval% |")
    lines.append("|-------------|---|-------|-------|-------|-------|------|------|---------|---------|---------|--------|")

    for ec in sorted(all_stats.keys()):
        stats_60 = None
        for s in all_stats[ec]:
            if s.horizon == "60s":
                stats_60 = s
                break
        if stats_60 is None or stats_60.n == 0:
            continue

        pf_str = f"{stats_60.profit_factor_4bps:.2f}" if stats_60.profit_factor_4bps != float('inf') else "∞"
        lines.append(
            f"| {ec} | {stats_60.n} | {stats_60.gross_return_bps:+.2f} | "
            f"{stats_60.net_return_2bps:+.2f} | {stats_60.net_return_4bps:+.2f} | "
            f"{stats_60.net_return_6bps:+.2f} | {stats_60.winrate_4bps:.1%} | "
            f"{pf_str} | {stats_60.avg_mfe_30s:+.2f} | {stats_60.avg_mae_30s:+.2f} | "
            f"{stats_60.mfe_mae_ratio_30s:.2f} | {stats_60.invalidation_rate:.1%} |"
        )
    lines.append("")

    # ============================================================
    # 5. FAST REACTION ANALYSIS
    # ============================================================
    lines.append("## 5. Fast Reaction Analysis")
    lines.append("")
    lines.append("How quickly do events produce favorable movement?")
    lines.append("")

    lines.append("| Event Class | Avg TTP | Median TTP | % Positive @ 30s |")
    lines.append("|-------------|---------|------------|------------------|")

    for ec in sorted(all_stats.keys()):
        stats_60 = None
        for s in all_stats[ec]:
            if s.horizon == "60s":
                stats_60 = s
                break
        if stats_60 is None or stats_60.n == 0:
            continue

        ttp_str = f"{stats_60.avg_time_to_positive:.1f}s" if stats_60.avg_time_to_positive > 0 else "—"
        mttp_str = f"{stats_60.median_time_to_positive:.1f}s" if stats_60.median_time_to_positive > 0 else "—"
        pct_str = f"{stats_60.pct_positive_at_30s:.1%}" if stats_60.pct_positive_at_30s > 0 else "—"

        lines.append(f"| {ec} | {ttp_str} | {mttp_str} | {pct_str} |")
    lines.append("")

    # 5s vs 30s comparison
    lines.append("### 5.1 Early vs Later Returns")
    lines.append("")
    lines.append("| Event Class | Gross 5s | Gross 10s | Gross 30s | 5s/30s Ratio |")
    lines.append("|-------------|----------|-----------|-----------|--------------|")

    for ec in sorted(all_stats.keys()):
        g5 = g10 = g30 = None
        for s in all_stats[ec]:
            if s.horizon == "5s":
                g5 = s.gross_return_bps if s.n > 0 else None
            elif s.horizon == "10s":
                g10 = s.gross_return_bps if s.n > 0 else None
            elif s.horizon == "30s":
                g30 = s.gross_return_bps if s.n > 0 else None

        if g5 is None and g10 is None and g30 is None:
            continue

        g5_str = f"{g5:+.2f}" if g5 is not None else "—"
        g10_str = f"{g10:+.2f}" if g10 is not None else "—"
        g30_str = f"{g30:+.2f}" if g30 is not None else "—"

        ratio_str = "—"
        if g5 is not None and g30 is not None and g30 != 0:
            ratio = g5 / g30
            ratio_str = f"{ratio:.2f}"

        lines.append(f"| {ec} | {g5_str} | {g10_str} | {g30_str} | {ratio_str} |")
    lines.append("")

    # ============================================================
    # 6. BREAKOUT ACCEPTANCE VS REJECTION
    # ============================================================
    lines.append("## 6. Breakout Acceptance vs Rejection")
    lines.append("")

    acceptance = [e for e in events if e.event_class == "breakout_acceptance"]
    rejection = [e for e in events if e.event_class == "breakout_rejection"]

    if not acceptance and not rejection:
        lines.append("**No breakout events detected.**")
        lines.append("")
    else:
        lines.append("### Direct Comparison (60s horizon)")
        lines.append("")
        lines.append("| Metric | Acceptance | Rejection |")
        lines.append("|--------|-----------|----------|")

        for label, evts in [("Acceptance", acceptance), ("Rejection", rejection)]:
            returns_60 = compute_directional_returns(evts, 60)
            if not returns_60:
                lines.append(f"| {label} N | 0 | — |")
                continue

            n = len(returns_60)
            gross = sum(returns_60) / n
            net4 = gross - 4
            wr4 = sum(1 for r in returns_60 if r - 4 > 0) / n
            mfe_vals = [e.mfe_30s for e in evts if e.mfe_30s is not None]
            mae_vals = [e.mae_30s for e in evts if e.mae_30s is not None]
            avg_mfe = sum(mfe_vals) / len(mfe_vals) if mfe_vals else 0
            avg_mae = sum(mae_vals) / len(mae_vals) if mae_vals else 0

            lines.append(f"| {label} N | {n} | |")
            lines.append(f"| {label} Gross 60s | {gross:+.2f} bps | |")
            lines.append(f"| {label} Net@4bps | {net4:+.2f} bps | |")
            lines.append(f"| {label} WR@4bps | {wr4:.1%} | |")
            lines.append(f"| {label} MFE 30s | {avg_mfe:+.2f} bps | |")
            lines.append(f"| {label} MAE 30s | {avg_mae:+.2f} bps | |")

        lines.append("")

        # By break direction
        lines.append("### By Break Direction")
        lines.append("")
        for direction in ["upside_break", "downside_break"]:
            dir_events = [e for e in events
                          if e.event_class in ("breakout_acceptance", "breakout_rejection")
                          and e.side == direction]
            if not dir_events:
                continue

            lines.append(f"**{direction}:**")
            for ec in ["breakout_acceptance", "breakout_rejection"]:
                subset = [e for e in dir_events if e.event_class == ec]
                returns = compute_directional_returns(subset, 60)
                if not returns:
                    continue
                n = len(returns)
                gross = sum(returns) / n
                net4 = gross - 4
                wr4 = sum(1 for r in returns if r - 4 > 0) / n
                lines.append(f"- {ec}: n={n}, gross={gross:+.2f}, net@4bps={net4:+.2f}, WR={wr4:.1%}")
            lines.append("")

    # ============================================================
    # 7. COST STRESS TEST
    # ============================================================
    lines.append("## 7. Cost Stress Test")
    lines.append("")
    lines.append("Net returns at multiple cost assumptions (60s horizon):")
    lines.append("")

    lines.append("| Event Class | N | Gross | Net@2bps | Net@4bps | Net@6bps |")
    lines.append("|-------------|---|-------|----------|----------|----------|")

    for ec in sorted(all_stats.keys()):
        stats_60 = None
        for s in all_stats[ec]:
            if s.horizon == "60s":
                stats_60 = s
                break
        if stats_60 is None or stats_60.n == 0:
            continue

        lines.append(
            f"| {ec} | {stats_60.n} | {stats_60.gross_return_bps:+.2f} | "
            f"{stats_60.net_return_2bps:+.2f} | {stats_60.net_return_4bps:+.2f} | "
            f"{stats_60.net_return_6bps:+.2f} |"
        )
    lines.append("")

    # PF across costs
    lines.append("### Profit Factor Across Costs")
    lines.append("")
    lines.append("| Event Class | PF@2bps | PF@4bps | PF@6bps |")
    lines.append("|-------------|---------|---------|---------|")

    for ec in sorted(all_stats.keys()):
        stats_60 = None
        for s in all_stats[ec]:
            if s.horizon == "60s":
                stats_60 = s
                break
        if stats_60 is None or stats_60.n == 0:
            continue

        # Compute PF at each cost
        returns = compute_directional_returns(
            [e for e in events if e.event_class == ec], 60
        )
        if not returns:
            continue

        pf_vals = []
        for cost in [2, 4, 6]:
            net = [r - cost for r in returns]
            gp = sum(r for r in net if r > 0)
            gl = abs(sum(r for r in net if r < 0))
            pf = gp / gl if gl > 0 else float('inf')
            pf_str = f"{pf:.2f}" if pf != float('inf') else "∞"
            pf_vals.append(pf_str)

        lines.append(f"| {ec} | {pf_vals[0]} | {pf_vals[1]} | {pf_vals[2]} |")
    lines.append("")

    # ============================================================
    # 8. FINAL VERDICT
    # ============================================================
    lines.append("## 8. Final Verdict")
    lines.append("")

    # Apply promotion criteria
    lines.append("### Promotion Criteria Check")
    lines.append("")
    lines.append("| Event Class | N≥100 | Gross>0 | Net≥0@4bps | Stable | MAE OK | Fast TTP | No Decay | Promotable |")
    lines.append("|-------------|-------|---------|-----------|--------|--------|----------|----------|------------|")

    promotable_any = False
    verdict_details = {}

    for ec in sorted(all_stats.keys()):
        stats_60 = None
        for s in all_stats[ec]:
            if s.horizon == "60s":
                stats_60 = s
                break
        if stats_60 is None:
            lines.append(f"| {ec} | — | — | — | — | — | — | — | ❌ |")
            continue

        # Criteria
        c_n = stats_60.n >= 100
        c_gross = stats_60.gross_return_bps > 0
        c_net = stats_60.net_return_4bps >= 0
        c_mae = stats_60.avg_mae_30s < 5.0  # controlled adverse
        c_ttp = (stats_60.avg_time_to_positive > 0 and
                 stats_60.avg_time_to_positive < 30)  # fast reaction

        # Time stability
        ts = compute_time_split_stats(events, ec, 60)
        if "error" in ts:
            c_stable = False
        else:
            f_net = ts["first_half"].get("net_4bps", -999)
            s_net = ts["second_half"].get("net_4bps", -999)
            c_stable = (f_net > 0 and s_net > 0) or (f_net < 0 and s_net < 0)

        # Decay
        blocks = compute_10min_blocks(events, ec, 60)
        c_decay = not blocks.get("decay_detected", True)

        promotable = all([c_n, c_gross, c_net, c_stable, c_mae, c_ttp, c_decay])
        if promotable:
            promotable_any = True

        verdict_details[ec] = {
            "n": stats_60.n,
            "gross": stats_60.gross_return_bps,
            "net_4bps": stats_60.net_return_4bps,
            "promotable": promotable,
            "criteria": {
                "n": c_n, "gross": c_gross, "net": c_net,
                "stable": c_stable, "mae": c_mae, "ttp": c_ttp, "decay": c_decay,
            },
        }

        def _c(v):
            return "✅" if v else "❌"

        lines.append(
            f"| {ec} | {_c(c_n)} ({stats_60.n}) | {_c(c_gross)} ({stats_60.gross_return_bps:+.1f}) | "
            f"{_c(c_net)} ({stats_60.net_return_4bps:+.1f}) | {_c(c_stable)} | "
            f"{_c(c_mae)} ({stats_60.avg_mae_30s:+.1f}) | {_c(c_ttp)} | "
            f"{_c(c_decay)} | {'✅' if promotable else '❌'} |"
        )
    lines.append("")

    # Final verdict
    lines.append("### System Verdict")
    lines.append("")

    if not events:
        lines.append("**No events collected.** Cannot determine if edge exists.")
    elif promotable_any:
        promotable_classes = [ec for ec, v in verdict_details.items() if v["promotable"]]
        lines.append(f"**Weak candidate signal(s) exist: {', '.join(promotable_classes)}**")
        lines.append("")
        lines.append("These event classes passed all promotion criteria at current sample size.")
        lines.append("However, this is RESEARCH PHASE — not production validation.")
        lines.append("Next step: collect 1,000+ events to confirm stability.")
    else:
        # Determine why no class promoted
        reasons = defaultdict(int)
        for ec, v in verdict_details.items():
            for criterion, passed in v["criteria"].items():
                if not passed:
                    reasons[criterion] += 1

        lines.append("**No statistically valid edge detected.**")
        lines.append("")
        lines.append("Failure breakdown across all event classes:")
        lines.append("")
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
            lines.append(f"- {reason}: failed for {count}/{len(verdict_details)} classes")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Report generated by research/auction_failure module.*")
    lines.append("*No parameters were tuned. No thresholds were optimized.*")
    lines.append("*Only structural conditions with relative metrics were used.*")

    return "\n".join(lines)
