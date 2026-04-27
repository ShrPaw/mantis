"""
failed_aggression_sell_v0 — Minimal shadow-only detector.

Detects: aggressive selling that FAILS to produce downside continuation.

Three components, no more:
  1. AGGRESSION:     strong sell delta relative to volume, extreme vs recent history
  2. NO RESPONSE:    price does not move lower meaningfully
  3. OUTCOME:        measured by OutcomeTracker (not used in live detection)

Live detection rule (no future data):
  if aggression AND no_downside_response → emit event

Forward return is measured AFTER detection by OutcomeTracker.
It is never used to trigger.

Shadow-only. Not registered in production ALL_DETECTORS list.
"""

from ..base import BaseEventDetector
from ..models import MicrostructureEvent
from dataclasses import dataclass, field
from typing import Optional
import uuid
import time


# ============================================================
# Event Model
# ============================================================

@dataclass
class FailedAggressionSellV0Event(MicrostructureEvent):
    event_type: str = "failed_aggression_sell_v0"
    delta_ratio: float = 0.0
    delta_percentile: float = 0.0
    downside_move_bps: float = 0.0
    distance_to_prior_low_bps: float = 0.0
    failed_to_break_low: bool = False
    aggression_score: float = 0.0
    no_response_score: float = 0.0

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "delta_ratio": round(self.delta_ratio, 4),
            "delta_percentile": round(self.delta_percentile, 4),
            "downside_move_bps": round(self.downside_move_bps, 4),
            "distance_to_prior_low_bps": round(self.distance_to_prior_low_bps, 4),
            "failed_to_break_low": self.failed_to_break_low,
            "aggression_score": round(self.aggression_score, 4),
            "no_response_score": round(self.no_response_score, 4),
        })
        return d


# ============================================================
# Detector
# ============================================================

class FailedAggressionSellV0Detector(BaseEventDetector):
    """
    Minimal failed-aggression detector.

    Fires when:
      - delta_ratio <= -0.40  (strongly negative)
      - abs_delta_percentile >= 0.85  (extreme vs recent)
      - downside_move_bps <= 2.0  OR  failed to break prior low

    That's it. Three conditions. No more.
    """

    # --- Structural thresholds (not optimized) ---
    AGGRESSION_DELTA_RATIO = -0.40
    AGGRESSION_PERCENTILE = 0.85
    MAX_DOWNSIDE_BPS = 2.0
    WINDOW_SECONDS = 15
    MIN_SAMPLES = 8
    MIN_VOLUME_BTC = 0.5
    PRIOR_LOW_LOOKBACK = 120
    PRIOR_LOW_PROXIMITY_BPS = 5.0  # must be within 5 bps of prior low

    @property
    def event_type(self) -> str:
        return "failed_aggression_sell_v0"

    def update(self, trade_price: float, trade_qty: float,
               trade_delta: float, timestamp: float) -> list[MicrostructureEvent]:
        ctx = self.ctx

        # --- Window data ---
        prices, volumes, deltas, timestamps = ctx.buffer.get_window(
            self.WINDOW_SECONDS, timestamp
        )
        if len(prices) < self.MIN_SAMPLES:
            return []

        total_vol = sum(volumes)
        total_delta = sum(deltas)

        if total_vol < self.MIN_VOLUME_BTC:
            return []

        # ── COMPONENT 1: AGGRESSION ─────────────────────────────
        delta_ratio = total_delta / total_vol
        if delta_ratio > self.AGGRESSION_DELTA_RATIO:
            return []

        abs_delta = abs(total_delta)
        delta_pct = ctx.buffer.percentile_delta(
            total_delta, self.WINDOW_SECONDS, timestamp, lookback=20
        )
        if delta_pct < self.AGGRESSION_PERCENTILE:
            return []

        # ── COMPONENT 2: NO PRICE RESPONSE ──────────────────────
        price_change = prices[-1] - prices[0]
        downside_move_bps = max(0, -price_change / prices[0] * 10000) if prices[0] > 0 else 0

        # Check prior low
        prior_prices, _, _, _ = ctx.buffer.get_window(
            self.PRIOR_LOW_LOOKBACK, timestamp
        )
        if prior_prices:
            prior_low = min(prior_prices)
        else:
            prior_low = min(prices)

        # Proximity: price must be NEAR the prior low (within threshold)
        # Otherwise "failed to break" is just mid-range noise
        if prior_low > 0:
            distance_to_low_bps = (trade_price - prior_low) / prior_low * 10000
        else:
            distance_to_low_bps = 999.0
        near_prior_low = distance_to_low_bps <= self.PRIOR_LOW_PROXIMITY_BPS

        failed_to_break_low = trade_price > prior_low and near_prior_low

        no_downside = (
            downside_move_bps <= self.MAX_DOWNSIDE_BPS
            or failed_to_break_low
        )
        if not no_downside:
            return []

        # ── BUILD EVENT ─────────────────────────────────────────
        aggression_score = min(delta_pct, 1.0)
        no_response_score = max(0, 1.0 - downside_move_bps / max(self.MAX_DOWNSIDE_BPS * 2, 0.1))

        explanation = (
            f"Failed aggression sell v0: delta_ratio={delta_ratio:.2f} "
            f"(p{delta_pct*100:.0f}), downside={downside_move_bps:.2f}bps, "
            f"broke_low={'no' if failed_to_break_low else 'yes'}. "
            f"Aggressive selling failing to produce downside."
        )

        return [FailedAggressionSellV0Event(
            price=trade_price,
            timestamp=timestamp,
            side="failed_aggression_sell_v0",
            explanation=explanation,
            scores=self._dummy_scores(aggression_score, no_response_score),
            delta_ratio=delta_ratio,
            delta_percentile=delta_pct,
            downside_move_bps=downside_move_bps,
            failed_to_break_low=failed_to_break_low,
            aggression_score=aggression_score,
            no_response_score=no_response_score,
            raw_metrics={
                "total_delta": total_delta,
                "total_volume": total_vol,
                "price_change": price_change,
                "delta_ratio": delta_ratio,
                "delta_percentile": delta_pct,
                "downside_bps": downside_move_bps,
                "distance_to_prior_low_bps": distance_to_low_bps,
            },
            context_metrics={
                "regime": ctx.classify_regime(),
                "prior_low": prior_low,
                "window_seconds": self.WINDOW_SECONDS,
            },
        )]

    def _dummy_scores(self, aggression: float, no_response: float):
        """Minimal scoring — not used for ranking, just stored."""
        from ..models import ScoreBreakdown
        composite = aggression * 0.6 + no_response * 0.4
        return ScoreBreakdown(
            strength_components={"aggression": aggression, "no_response": no_response},
            confidence_components={},
            noise_components={},
            regime_score=0.0,
            strength_score=aggression,
            confidence_score=no_response,
            noise_score=0.0,
            composite_score=composite,
        )
