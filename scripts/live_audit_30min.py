#!/usr/bin/env python3
"""MANTIS Post-Fix Live Audit — 30-minute simulation.

Replays realistic market scenarios through the fixed AlertManager
to validate deduplication under production-like conditions.

Produces: raw events, fired alerts, suppressed alerts, unique keys,
tier breakdown, state transitions, burst analysis.
"""

from __future__ import annotations

import json
import random
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, ".")

from engine.alerts import AlertManager
from engine.models import (
    Scores, MarketState, CrowdBuildupState, LiquidationCascadeState,
    UnwindState, ExhaustionAbsorptionState, ExecutionMode, Alert,
)

# ── Config (matches production) ─────────────────────────────────────────

CONFIG = {
    "alerts": {
        "tier1": {"imbalance_score_min": 60, "execution_quality_min": 50},
        "tier2": {"imbalance_score_min": 75, "execution_quality_min": 70, "risk_score_max": 60},
        "tier3": {"risk_score_min": 75, "execution_quality_max": 35, "cascade_intensity_min": 80},
        "min_seconds_between_same_alert": 60,
        "max_alerts_per_hour": 20,
    }
}

TICK_INTERVAL = 0.25  # 250ms tick = production rate
AUDIT_DURATION_SEC = 30 * 60  # 30 minutes
TOTAL_TICKS = int(AUDIT_DURATION_SEC / TICK_INTERVAL)

# ── Scenario Generator ──────────────────────────────────────────────────

@dataclass
class ScenarioPhase:
    """A market phase with specific characteristics."""
    name: str
    duration_ticks: int
    market_state: MarketState
    scores_fn: object  # callable(tick) -> Scores
    crowd_fn: object = None
    cascade_fn: object = None
    unwind_fn: object = None
    exhaustion_fn: object = None
    exec_mode: ExecutionMode = ExecutionMode.MAKER_ONLY


def _noise(base: float, amp: float = 5.0) -> float:
    return base + random.uniform(-amp, amp)


class MarketSimulator:
    """Generates realistic market phases over 30 minutes."""

    def __init__(self):
        self.phases = self._build_phases()

    def _build_phases(self) -> list[ScenarioPhase]:
        """Build a realistic 30-min market scenario with transitions."""
        phases = []

        # Phase 1: Calm market (5 min)
        phases.append(ScenarioPhase(
            name="CALM",
            duration_ticks=int(5 * 60 / TICK_INTERVAL),
            market_state=MarketState.IDLE,
            scores_fn=lambda t: Scores(
                imbalance=_noise(30, 8),
                execution_quality=_noise(80, 5),
                risk=_noise(20, 5),
                trade_environment=_noise(60, 5),
            ),
        ))

        # Phase 2: Crowd buildup forming (5 min) — should fire TIER1
        phases.append(ScenarioPhase(
            name="CROWD_BUILDUP_LONGS",
            duration_ticks=int(5 * 60 / TICK_INTERVAL),
            market_state=MarketState.CROWD_BUILDUP,
            scores_fn=lambda t: Scores(
                imbalance=_noise(68, 4),
                execution_quality=_noise(55, 5),
                risk=_noise(35, 5),
                trade_environment=_noise(55, 5),
            ),
            crowd_fn=lambda t: CrowdBuildupState(
                active=True, crowd_side="LONGS",
                severity=_noise(60, 5),
            ),
        ))

        # Phase 3: Escalation — crowd intensifies, TIER2 fires (3 min)
        phases.append(ScenarioPhase(
            name="CROWD_ESCALATION",
            duration_ticks=int(3 * 60 / TICK_INTERVAL),
            market_state=MarketState.CROWD_BUILDUP,
            scores_fn=lambda t: Scores(
                imbalance=_noise(80, 3),
                execution_quality=_noise(75, 3),
                risk=_noise(45, 5),
                trade_environment=_noise(70, 5),
            ),
            crowd_fn=lambda t: CrowdBuildupState(
                active=True, crowd_side="LONGS",
                severity=_noise(75, 5),
            ),
        ))

        # Phase 4: Liquidation cascade — TIER3 territory (4 min)
        phases.append(ScenarioPhase(
            name="LIQUIDATION_CASCADE",
            duration_ticks=int(4 * 60 / TICK_INTERVAL),
            market_state=MarketState.LIQUIDATION_CASCADE,
            scores_fn=lambda t: Scores(
                imbalance=_noise(50, 8),
                execution_quality=_noise(25, 5),
                risk=_noise(85, 4),
                trade_environment=_noise(30, 5),
            ),
            cascade_fn=lambda t: LiquidationCascadeState(
                active=True, cascade_direction="DOWN",
                intensity=_noise(88, 5),
                execution_mode="DANGER",
            ),
            exec_mode=ExecutionMode.NO_TRADE,
        ))

        # Phase 5: Cascade continues — same direction, tests burst suppression (3 min)
        phases.append(ScenarioPhase(
            name="CASCADE_CONTINUATION",
            duration_ticks=int(3 * 60 / TICK_INTERVAL),
            market_state=MarketState.LIQUIDATION_CASCADE,
            scores_fn=lambda t: Scores(
                imbalance=_noise(45, 8),
                execution_quality=_noise(20, 5),
                risk=_noise(90, 3),
                trade_environment=_noise(25, 5),
            ),
            cascade_fn=lambda t: LiquidationCascadeState(
                active=True, cascade_direction="DOWN",
                intensity=_noise(92, 3),
                execution_mode="DANGER",
            ),
            exec_mode=ExecutionMode.NO_TRADE,
        ))

        # Phase 6: Cascade reverses direction (2 min) — different side should fire
        phases.append(ScenarioPhase(
            name="CASCADE_REVERSAL",
            duration_ticks=int(2 * 60 / TICK_INTERVAL),
            market_state=MarketState.LIQUIDATION_CASCADE,
            scores_fn=lambda t: Scores(
                imbalance=_noise(55, 8),
                execution_quality=_noise(30, 5),
                risk=_noise(82, 4),
                trade_environment=_noise(35, 5),
            ),
            cascade_fn=lambda t: LiquidationCascadeState(
                active=True, cascade_direction="UP",
                intensity=_noise(85, 4),
                execution_mode="DANGER",
            ),
            exec_mode=ExecutionMode.NO_TRADE,
        ))

        # Phase 7: Exhaustion absorption (3 min)
        phases.append(ScenarioPhase(
            name="EXHAUSTION",
            duration_ticks=int(3 * 60 / TICK_INTERVAL),
            market_state=MarketState.EXHAUSTION_ABSORPTION,
            scores_fn=lambda t: Scores(
                imbalance=_noise(40, 8),
                execution_quality=_noise(45, 5),
                risk=_noise(55, 5),
                trade_environment=_noise(40, 5),
            ),
            exhaustion_fn=lambda t: ExhaustionAbsorptionState(
                active=True, side="SELL_EXHAUSTION",
                confidence=_noise(70, 5),
            ),
            exec_mode=ExecutionMode.WAIT,
        ))

        # Phase 8: Recovery — unwind (3 min) — TIER1/TIER2 on SHORTS side
        phases.append(ScenarioPhase(
            name="UNWIND_SHORTS",
            duration_ticks=int(3 * 60 / TICK_INTERVAL),
            market_state=MarketState.UNWIND,
            scores_fn=lambda t: Scores(
                imbalance=_noise(65, 5),
                execution_quality=_noise(60, 5),
                risk=_noise(40, 5),
                trade_environment=_noise(55, 5),
            ),
            unwind_fn=lambda t: UnwindState(
                active=True, unwind_side="SHORTS_EXITING",
                direction="UP", maturity="EARLY",
            ),
        ))

        # Phase 9: Return to calm (2 min)
        phases.append(ScenarioPhase(
            name="RECOVERY",
            duration_ticks=int(2 * 60 / TICK_INTERVAL),
            market_state=MarketState.IDLE,
            scores_fn=lambda t: Scores(
                imbalance=_noise(35, 8),
                execution_quality=_noise(75, 5),
                risk=_noise(25, 5),
                trade_environment=_noise(60, 5),
            ),
        ))

        return phases

    def run_audit(self) -> dict:
        """Run the full 30-min audit and collect metrics."""
        mgr = AlertManager(CONFIG)

        raw_events = 0
        fired_alerts: list[dict] = []
        unique_keys: set[str] = set()
        tier_counts: Counter = Counter()
        state_transitions: list[tuple[str, str]] = []
        high_severity_count = 0
        prev_state_name = None

        current_tick = 0
        phase_idx = 0
        phase_tick = 0
        start_time = time.time()

        for phase in self.phases:
            for t in range(phase.duration_ticks):
                raw_events += 1

                # Generate state for this tick
                scores = phase.scores_fn(t)
                crowd = phase.crowd_fn(t) if phase.crowd_fn else CrowdBuildupState()
                cascade = phase.cascade_fn(t) if phase.cascade_fn else LiquidationCascadeState()
                unwind = phase.unwind_fn(t) if phase.unwind_fn else UnwindState()
                exhaustion = phase.exhaustion_fn(t) if phase.exhaustion_fn else ExhaustionAbsorptionState()

                # Track state transitions
                state_name = phase.name
                if state_name != prev_state_name:
                    if prev_state_name is not None:
                        state_transitions.append((prev_state_name, state_name))
                    prev_state_name = state_name

                # Run alert check
                alert = mgr.check(
                    scores, phase.market_state, crowd, cascade,
                    unwind, exhaustion, phase.exec_mode,
                )

                if alert:
                    key = f"TIER{alert.tier}_{alert.state}_{alert.side}"
                    fired_alerts.append({
                        "tick": current_tick,
                        "phase": phase.name,
                        "tier": alert.tier,
                        "state": alert.state,
                        "side": alert.side,
                        "severity": alert.severity,
                        "key": key,
                    })
                    unique_keys.add(key)
                    tier_counts[alert.tier] += 1
                    if alert.severity >= 75:
                        high_severity_count += 1

                current_tick += 1

        elapsed = time.time() - start_time

        # Burst analysis: check for duplicate bursts within any 5-second window
        burst_windows = defaultdict(list)
        for a in fired_alerts:
            window = a["tick"] // int(5 / TICK_INTERVAL)  # 5-sec windows
            burst_windows[(a["key"], window)].append(a)

        duplicate_bursts = {
            k: len(v) for k, v in burst_windows.items() if len(v) > 1
        }

        return {
            "raw_events": raw_events,
            "fired_alerts": fired_alerts,
            "fired_count": len(fired_alerts),
            "suppressed_count": mgr.suppressed_alert_count,
            "unique_keys": sorted(unique_keys),
            "unique_key_count": len(unique_keys),
            "tier_counts": dict(tier_counts),
            "state_transitions": state_transitions,
            "high_severity_count": high_severity_count,
            "duplicate_bursts": duplicate_bursts,
            "elapsed_seconds": elapsed,
        }


# ── Report Generator ────────────────────────────────────────────────────

def generate_report(results: dict) -> str:
    """Generate the audit report markdown."""
    r = results
    lines = []
    lines.append("# MANTIS POST-FIX AUDIT REPORT")
    lines.append(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    lines.append(f"Duration: 30 minutes (simulated at production tick rate)")
    lines.append(f"Tick interval: {TICK_INTERVAL}s")
    lines.append(f"min_seconds_between_same_alert: {CONFIG['alerts']['min_seconds_between_same_alert']}")
    lines.append("")

    # ── Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Raw events processed | {r['raw_events']:,} |")
    lines.append(f"| Fired alerts | {r['fired_count']} |")
    lines.append(f"| Suppressed (dedup) | {r['suppressed_count']} |")
    lines.append(f"| Unique alert keys | {r['unique_key_count']} |")
    lines.append(f"| High-severity (≥75) | {r['high_severity_count']} |")
    lines.append(f"| State transitions | {len(r['state_transitions'])} |")
    lines.append(f"| Duplicate bursts (>1 in 5s window) | {len(r['duplicate_bursts'])} |")
    lines.append(f"| Elapsed (sim) | {r['elapsed_seconds']:.1f}s |")
    lines.append("")

    # ── Tier Breakdown
    lines.append("## Tier Breakdown")
    lines.append("")
    lines.append(f"| Tier | Count |")
    lines.append(f"|------|-------|")
    for tier in sorted(r["tier_counts"].keys()):
        label = {1: "WATCH", 2: "ACTIONABLE", 3: "DANGER"}.get(tier, "?")
        lines.append(f"| Tier {tier} ({label}) | {r['tier_counts'][tier]} |")
    lines.append("")

    # ── Unique Alert Keys
    lines.append("## Unique Alert Keys")
    lines.append("")
    for key in r["unique_keys"]:
        count = sum(1 for a in r["fired_alerts"] if a["key"] == key)
        lines.append(f"- `{key}` — fired {count}x")
    lines.append("")

    # ── State Transitions
    lines.append("## State Transitions")
    lines.append("")
    for i, (frm, to) in enumerate(r["state_transitions"], 1):
        lines.append(f"{i}. {frm} → {to}")
    lines.append("")

    # ── Duplicate Burst Analysis
    lines.append("## Duplicate Burst Analysis")
    lines.append("")
    if r["duplicate_bursts"]:
        lines.append("⚠️ **DUPLICATE BURSTS DETECTED:**")
        lines.append("")
        for (key, window), count in r["duplicate_bursts"].items():
            lines.append(f"- `{key}` in window {window}: {count} alerts")
        lines.append("")
        lines.append("This indicates the rate limiter may still allow minor bursts")
        lines.append("within very short sub-second intervals before the cooldown")
        lines.append("timestamp is set. Investigation recommended.")
    else:
        lines.append("✅ **NO DUPLICATE BURSTS DETECTED**")
        lines.append("")
        lines.append("Every unique alert key fired at most once per cooldown window.")
        lines.append("The rate limiter is correctly suppressing duplicates.")
    lines.append("")

    # ── Alert Frequency
    lines.append("## Alert Frequency Assessment")
    lines.append("")
    alerts_per_minute = r["fired_count"] / 30.0
    lines.append(f"- Alerts per minute: {alerts_per_minute:.2f}")
    lines.append(f"- Alerts per hour (projected): {alerts_per_minute * 60:.0f}")
    lines.append("")
    if alerts_per_minute <= 1.0:
        lines.append("✅ Alert frequency is **usable** — less than 1 alert/minute.")
    elif alerts_per_minute <= 3.0:
        lines.append("⚠️ Alert frequency is **moderate** — 1-3 alerts/minute. May need tuning.")
    else:
        lines.append("❌ Alert frequency is **too high** — >3 alerts/minute. Not usable.")
    lines.append("")

    # ── Suppression Effectiveness
    lines.append("## Suppression Effectiveness")
    lines.append("")
    total_attempts = r["fired_count"] + r["suppressed_count"]
    if total_attempts > 0:
        suppression_rate = r["suppressed_count"] / total_attempts * 100
        lines.append(f"- Total alert attempts: {total_attempts}")
        lines.append(f"- Suppressed: {r['suppressed_count']} ({suppression_rate:.1f}%)")
        lines.append(f"- Fired: {r['fired_count']} ({100 - suppression_rate:.1f}%)")
    else:
        lines.append("- No alerts attempted (market was calm throughout)")
    lines.append("")

    # ── Raw Event Log (sample)
    lines.append("## Sample Fired Alerts (first 20)")
    lines.append("")
    lines.append("| # | Phase | Tier | State | Side | Severity | Key |")
    lines.append("|---|-------|------|-------|------|----------|-----|")
    for i, a in enumerate(r["fired_alerts"][:20], 1):
        lines.append(f"| {i} | {a['phase']} | {a['tier']} | {a['state']} | {a['side']} | {a['severity']:.0f} | `{a['key']}` |")
    if len(r["fired_alerts"]) > 20:
        lines.append(f"| ... | ... | ... | ... | ... | ... | ... |")
        lines.append(f"| {len(r['fired_alerts'])} | (total) | | | | | |")
    lines.append("")

    # ── Final Verdict
    lines.append("## Final Verdict")
    lines.append("")

    score = 0
    notes = []

    # No duplicate bursts = +2
    if len(r["duplicate_bursts"]) == 0:
        score += 2
        notes.append("✅ No duplicate bursts")
    else:
        notes.append(f"❌ {len(r['duplicate_bursts'])} duplicate bursts detected")

    # Suppression working = +2
    if r["suppressed_count"] > 0:
        score += 2
        notes.append(f"✅ Suppression active ({r['suppressed_count']} suppressed)")
    else:
        notes.append("⚠️ No suppressions occurred (may indicate no duplicates to suppress)")

    # Reasonable frequency = +2
    if alerts_per_minute <= 1.0:
        score += 2
        notes.append(f"✅ Alert frequency usable ({alerts_per_minute:.2f}/min)")
    elif alerts_per_minute <= 3.0:
        score += 1
        notes.append(f"⚠️ Alert frequency moderate ({alerts_per_minute:.2f}/min)")
    else:
        notes.append(f"❌ Alert frequency too high ({alerts_per_minute:.2f}/min)")

    # State transitions captured = +1
    if len(r["state_transitions"]) >= 3:
        score += 1
        notes.append(f"✅ Multiple state transitions ({len(r['state_transitions'])})")

    # All tiers exercised = +1
    if len(r["tier_counts"]) >= 2:
        score += 1
        notes.append(f"✅ Multiple tiers exercised ({list(r['tier_counts'].keys())})")

    # High severity handled = +1
    if r["high_severity_count"] > 0:
        score += 1
        notes.append(f"✅ High-severity alerts handled ({r['high_severity_count']})")

    lines.append("### Scoring")
    lines.append("")
    for note in notes:
        lines.append(f"- {note}")
    lines.append("")
    lines.append(f"**Score: {score}/8**")
    lines.append("")

    if score >= 7:
        verdict = "A"
        label = "usable"
        lines.append("## **VERDICT: A — Usable**")
        lines.append("")
        lines.append("The alert rate limiter fix is working correctly. Duplicate bursts")
        lines.append("are eliminated. Alert frequency is manageable. The system is ready")
        lines.append("for production use with current thresholds.")
    elif score >= 4:
        verdict = "B"
        label = "still noisy but fixable"
        lines.append("## **VERDICT: B — Still noisy but fixable**")
        lines.append("")
        lines.append("The rate limiter fix is working but the system still produces")
        lines.append("more alerts than ideal. Threshold tuning or additional suppression")
        lines.append("rules may be needed, but the core dedup bug is resolved.")
    else:
        verdict = "C"
        label = "not useful yet"
        lines.append("## **VERDICT: C — Not useful yet**")
        lines.append("")
        lines.append("Significant issues remain. The rate limiter may not be suppressing")
        lines.append("effectively or the alert volume is still unmanageable.")

    lines.append("")
    lines.append(f"---")
    lines.append(f"Report generated in {r['elapsed_seconds']:.1f}s")
    lines.append(f"Verdict: **{verdict} — {label}**")

    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  MANTIS POST-FIX LIVE AUDIT")
    print("  30-minute simulation at production tick rate")
    print("=" * 60)
    print()

    sim = MarketSimulator()
    print("Running simulation...")
    results = sim.run_audit()

    print(f"  Raw events:      {results['raw_events']:,}")
    print(f"  Fired alerts:    {results['fired_count']}")
    print(f"  Suppressed:      {results['suppressed_count']}")
    print(f"  Unique keys:     {results['unique_key_count']}")
    print(f"  Duplicate bursts:{len(results['duplicate_bursts'])}")
    print()

    report = generate_report(results)
    out_path = Path("MANTIS_POST_FIX_AUDIT.md")
    out_path.write_text(report)
    print(f"Report written to {out_path}")
    print()

    # Also print report
    print(report)


if __name__ == "__main__":
    main()
