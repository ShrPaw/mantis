"""MANTIS Execution Engine — Alert Manager.

Generates tiered alerts with strict rate limiting.
Alerts must be rare and meaningful.
"""

from __future__ import annotations

import logging
import time
from collections import deque

from engine.models import (
    Alert, AlertTier, Scores, MarketState,
    CrowdBuildupState, LiquidationCascadeState, UnwindState,
    ExhaustionAbsorptionState, ExecutionMode,
)

logger = logging.getLogger("mantis.alerts")


class AlertManager:
    """Generates and rate-limits alerts."""

    def __init__(self, config: dict):
        self.cfg = config.get("alerts", {})
        self._tier1 = self.cfg.get("tier1", {})
        self._tier2 = self.cfg.get("tier2", {})
        self._tier3 = self.cfg.get("tier3", {})
        self._min_seconds = self.cfg.get("min_seconds_between_same_alert", 60)
        self._max_per_hour = self.cfg.get("max_alerts_per_hour", 20)

        # Rate limiting
        self._last_alert_by_key: dict[str, float] = {}
        self._alert_times: deque[float] = deque(maxlen=100)

        # Suppression tracking
        self.suppressed_alert_count: int = 0

    def check(self, scores: Scores, state: MarketState,
              crowd: CrowdBuildupState, cascade: LiquidationCascadeState,
              unwind: UnwindState, exhaustion: ExhaustionAbsorptionState,
              execution_mode: ExecutionMode) -> Alert | None:
        """Check if an alert should fire. Returns Alert or None."""

        now = time.time()

        # Rate limit: max per hour
        while self._alert_times and now - self._alert_times[0] > 3600:
            self._alert_times.popleft()
        if len(self._alert_times) >= self._max_per_hour:
            return None

        # Check tier 3 first (highest priority — danger)
        alert = self._check_tier3(scores, state, cascade, execution_mode, now)
        if alert:
            return alert

        # Check tier 2 (actionable)
        alert = self._check_tier2(scores, state, crowd, unwind, now)
        if alert:
            return alert

        # Check tier 1 (watch)
        alert = self._check_tier1(scores, state, crowd, unwind, now)
        if alert:
            return alert

        return None

    @staticmethod
    def _build_key(tier: int, state: str, side: str) -> str:
        """Build a canonical dedup key: tier + state + side."""
        return f"TIER{tier}_{state}_{side}"

    def _is_rate_limited(self, dedup_key: str, now: float) -> bool:
        """Check if this exact key (tier+state+side) was recently alerted."""
        last = self._last_alert_by_key.get(dedup_key, 0)
        if now - last < self._min_seconds:
            self.suppressed_alert_count += 1
            return True
        return False

    def _record_alert(self, dedup_key: str, now: float):
        """Record alert for rate limiting using the same key that was checked."""
        self._last_alert_by_key[dedup_key] = now
        self._alert_times.append(now)

    def _check_tier3(self, scores: Scores, state: MarketState,
                     cascade: LiquidationCascadeState,
                     execution_mode: ExecutionMode, now: float) -> Alert | None:
        """Tier 3: Danger alerts."""
        risk_min = self._tier3.get("risk_score_min", 75)
        exec_max = self._tier3.get("execution_quality_max", 35)
        cascade_min = self._tier3.get("cascade_intensity_min", 80)

        reasons = []
        if scores.risk >= risk_min:
            reasons.append(f"Risk score {scores.risk:.0f} >= {risk_min}")
        if scores.execution_quality <= exec_max:
            reasons.append(f"Execution quality {scores.execution_quality:.0f} <= {exec_max}")
        if cascade.active and cascade.intensity >= cascade_min:
            reasons.append(f"Cascade intensity {cascade.intensity:.0f} >= {cascade_min}")

        if not reasons:
            return None

        side = self._determine_side(cascade, scores)
        dedup_key = self._build_key(3, "DANGER", side)
        if self._is_rate_limited(dedup_key, now):
            return None

        # Determine execution recommendation
        if cascade.active:
            exec_rec = "NO_TRADE — Cascade active. Wait for exhaustion."
        elif scores.execution_quality <= exec_max:
            exec_rec = "NO_TRADE — Execution hostile."
        else:
            exec_rec = "REDUCE_SIZE — High risk environment."

        alert = Alert(
            timestamp=now,
            tier=3,
            state="DANGER",
            side=side,
            severity=scores.risk,
            reason="; ".join(reasons),
            do_not="Do NOT enter new positions. Do NOT chase moves.",
            execution_recommendation=exec_rec,
            scores=scores,
        )
        self._record_alert(dedup_key, now)
        return alert

    def _check_tier2(self, scores: Scores, state: MarketState,
                     crowd: CrowdBuildupState, unwind: UnwindState,
                     now: float) -> Alert | None:
        """Tier 2: Actionable context."""
        imb_min = self._tier2.get("imbalance_score_min", 75)
        exec_min = self._tier2.get("execution_quality_min", 70)
        risk_max = self._tier2.get("risk_score_max", 60)

        if not (scores.imbalance >= imb_min and
                scores.execution_quality >= exec_min and
                scores.risk <= risk_max):
            return None

        side = "NEUTRAL"
        reason_parts = [f"Imbalance {scores.imbalance:.0f}", f"Exec {scores.execution_quality:.0f}"]
        if crowd.active:
            side = crowd.crowd_side
            reason_parts.append(f"Crowd: {crowd.crowd_side}")
        if unwind.active:
            side = unwind.unwind_side
            reason_parts.append(f"Unwind: {unwind.unwind_side}")

        dedup_key = self._build_key(2, state.value, side)
        if self._is_rate_limited(dedup_key, now):
            return None

        # Determine execution mode
        if scores.execution_quality >= 80:
            exec_rec = "MAKER_ONLY — Favorable conditions for limit orders."
        else:
            exec_rec = "WAIT — Monitor for better entry conditions."

        alert = Alert(
            timestamp=now,
            tier=2,
            state=state.value,
            side=side,
            severity=scores.trade_environment,
            reason="; ".join(reason_parts),
            do_not="Do NOT market buy/sell. Use limit orders only.",
            execution_recommendation=exec_rec,
            scores=scores,
        )
        self._record_alert(dedup_key, now)
        return alert

    def _check_tier1(self, scores: Scores, state: MarketState,
                     crowd: CrowdBuildupState, unwind: UnwindState,
                     now: float) -> Alert | None:
        """Tier 1: Watch alerts."""
        imb_min = self._tier1.get("imbalance_score_min", 60)
        exec_min = self._tier1.get("execution_quality_min", 50)

        if not (scores.imbalance >= imb_min and scores.execution_quality >= exec_min):
            return None

        side = "NEUTRAL"
        if crowd.active:
            side = crowd.crowd_side
        elif unwind.active:
            side = unwind.unwind_side

        dedup_key = self._build_key(1, state.value, side)
        if self._is_rate_limited(dedup_key, now):
            return None

        alert = Alert(
            timestamp=now,
            tier=1,
            state=state.value,
            side=side,
            severity=scores.imbalance,
            reason=f"Imbalance elevated ({scores.imbalance:.0f}). Execution quality adequate ({scores.execution_quality:.0f}).",
            do_not="Do NOT act without confirmation.",
            execution_recommendation="WATCH — Monitor for escalation or resolution.",
            scores=scores,
        )
        self._record_alert(dedup_key, now)
        return alert

    def _determine_side(self, cascade: LiquidationCascadeState,
                        scores: Scores) -> str:
        """Determine which side is under pressure."""
        if cascade.active:
            return cascade.cascade_direction
        return "NEUTRAL"
