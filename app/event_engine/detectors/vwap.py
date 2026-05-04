"""
VWAP / Session Context Detector — Detects behavior around VWAP and session levels.
"""

from app.event_engine.base import BaseEventDetector
from app.event_engine.models import VWAPReactionEvent, MicrostructureEvent


class VWAPDetector(BaseEventDetector):

    def __init__(self, context):
        super().__init__(context)
        self._last_vwap_cross: float = 0.0
        self._above_vwap: bool | None = None

    @property
    def event_type(self) -> str:
        return "vwap_reaction"

    def update(self, trade_price: float, trade_qty: float,
               trade_delta: float, timestamp: float) -> list[MicrostructureEvent]:
        cfg = self.ctx.config.vwap
        ctx = self.ctx

        vwap = ctx.session.vwap
        if vwap == 0:
            return []

        distance = trade_price - vwap
        abs_dist = abs(distance)

        # Track VWAP position
        currently_above = trade_price > vwap
        if self._above_vwap is None:
            self._above_vwap = currently_above
            return []

        # Detect crossing
        crossed = currently_above != self._above_vwap
        self._above_vwap = currently_above

        # Only react near VWAP or on cross
        if abs_dist > cfg.proximity_threshold_usd and not crossed:
            return []

        # Get recent flow context
        prices, volumes, deltas, _ = ctx.buffer.get_window(cfg.reaction_window_seconds, timestamp)
        if len(prices) < 3:
            return []

        recent_vol = sum(volumes)
        recent_delta = sum(deltas)

        if recent_vol < cfg.min_volume_for_reaction:
            return []

        # Determine reaction type
        reaction_type = self._classify_reaction(
            trade_price, vwap, distance, crossed, recent_delta, prices
        )
        if reaction_type is None:
            return []

        # Follow-through: price movement after reaction
        follow_through = prices[-1] - prices[0] if len(prices) > 1 else 0

        regime = ctx.classify_regime()
        scorer = ctx.scoring
        scores = scorer.score_vwap_reaction(
            volume_pct=min(recent_vol / 5, 1.0),
            delta_strength=min(abs(recent_delta) / 3, 1.0),
            follow_through=follow_through,
            regime=regime,
        )

        side = "above_vwap" if currently_above else "below_vwap"
        explanation = (
            f"VWAP {reaction_type} detected: price at {trade_price:.2f}, "
            f"VWAP at {vwap:.2f} (distance: {distance:+.1f} USD). "
            f"{'Crossed' if crossed else 'Approached'} VWAP. "
            f"Recent delta: {recent_delta:+.2f} BTC. "
            f"Follow-through: {follow_through:+.1f} USD."
        )

        return [VWAPReactionEvent(
            price=trade_price,
            timestamp=timestamp,
            side=side,
            explanation=explanation,
            scores=scores,
            vwap=vwap,
            distance_to_vwap=distance,
            reaction_type=reaction_type,
            delta_context=recent_delta,
            volume_context=recent_vol,
            follow_through=follow_through,
            raw_metrics={
                "vwap": vwap, "distance": distance,
                "recent_delta": recent_delta, "recent_vol": recent_vol,
                "crossed": crossed,
            },
            context_metrics={"regime": regime, "reaction": reaction_type},
        )]

    def _classify_reaction(self, price: float, vwap: float, distance: float,
                           crossed: bool, delta: float, prices: list) -> str | None:
        """Classify the VWAP reaction type."""
        cfg = self.ctx.config.vwap

        # Reclaim: crossed below then came back above (or vice versa)
        if crossed:
            if price > vwap and delta > cfg.min_delta_for_reaction:
                return "reclaim"
            if price < vwap and delta < -cfg.min_delta_for_reaction:
                return "reclaim"

        # Reject: price approached VWAP and reversed
        if abs(distance) < cfg.proximity_threshold_usd:
            if len(prices) >= 3:
                # Check if price was moving toward VWAP then reversed
                trend = prices[-1] - prices[-3]
                if distance > 0 and trend < -5:  # above VWAP, selling off
                    return "reject"
                if distance < 0 and trend > 5:  # below VWAP, bouncing
                    return "reject"

        # Hold: price sitting at VWAP with balanced flow
        if abs(distance) < 5:
            return "hold"

        # Break: price broke through VWAP with momentum
        if crossed and abs(delta) > cfg.min_delta_for_reaction:
            return "break"

        return None
