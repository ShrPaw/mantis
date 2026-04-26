"""
Liquidity Sweep Detector — Price sweeps a recent high/low then fails or reverses.
"""

from ..base import BaseEventDetector
from ..models import LiquiditySweepEvent, MicrostructureEvent


class SweepDetector(BaseEventDetector):

    @property
    def event_type(self) -> str:
        return "liquidity_sweep"

    def update(self, trade_price: float, trade_qty: float,
               trade_delta: float, timestamp: float) -> list[MicrostructureEvent]:
        cfg = self.ctx.config.sweep
        ctx = self.ctx

        prices, volumes, deltas, timestamps = ctx.buffer.get_window(cfg.lookback_seconds, timestamp)
        if len(prices) < 20:
            return []

        # Exclude recent ticks as the "sweep zone"
        exclude = min(10, len(prices) // 4)
        if exclude < 3:
            return []
        prior_prices = prices[:-exclude]
        if len(prior_prices) < 5:
            return []

        prior_high = max(prior_prices)
        prior_low = min(prior_prices)

        recent = prices[-exclude:]
        recent_vol = volumes[-exclude:]
        recent_delta = deltas[-exclude:]
        sweep_vol = sum(recent_vol)
        sweep_delta = sum(recent_delta)

        events = []

        # High sweep: price breaks above prior high then comes back
        if trade_price > prior_high:
            max_recent = max(recent)
            sweep_dist = max_recent - prior_high
            if cfg.min_sweep_distance_usd <= sweep_dist <= cfg.max_sweep_distance_usd:
                # Check reclaim: came back inside
                came_back = any(p <= prior_high + 5 for p in recent[exclude // 2:]) if len(recent) > exclude // 2 else False
                if came_back:
                    evt = self._build_event(
                        "high_sweep", trade_price, timestamp,
                        prior_high, sweep_dist, sweep_vol, sweep_delta,
                        reclaim=True, reversal=(sweep_delta < 0),
                    )
                    if evt:
                        events.append(evt)

        # Low sweep
        if trade_price < prior_low:
            min_recent = min(recent)
            sweep_dist = prior_low - min_recent
            if cfg.min_sweep_distance_usd <= sweep_dist <= cfg.max_sweep_distance_usd:
                came_back = any(p >= prior_low - 5 for p in recent[exclude // 2:]) if len(recent) > exclude // 2 else False
                if came_back:
                    evt = self._build_event(
                        "low_sweep", trade_price, timestamp,
                        prior_low, sweep_dist, sweep_vol, sweep_delta,
                        reclaim=True, reversal=(sweep_delta > 0),
                    )
                    if evt:
                        events.append(evt)

        return events

    def _build_event(self, side: str, price: float, timestamp: float,
                     swept_level: float, distance: float, vol: float, delta: float,
                     reclaim: bool, reversal: bool) -> LiquiditySweepEvent:
        ctx = self.ctx
        regime = ctx.classify_regime()
        scorer = ctx.scoring

        scores = scorer.score_sweep(
            distance_pct=min(distance / 50, 1.0),
            volume_pct=min(vol / 5, 1.0),
            reclaimed=reclaim,
            reversal=reversal,
            prior_touches=2,
            regime=regime,
        )

        action = "high" if side == "high_sweep" else "low"
        explanation = (
            f"{action.title()} sweep detected: price swept {action} at {swept_level:.2f} "
            f"by {distance:.1f} USD, volume {vol:.2f} BTC. "
            f"{'Reclaimed' if reclaim else 'No reclaim'}. "
            f"{'Reversal confirmed' if reversal else 'No reversal yet'}."
        )

        return LiquiditySweepEvent(
            price=price,
            timestamp=timestamp,
            side=side,
            explanation=explanation,
            scores=scores,
            swept_level=swept_level,
            sweep_distance=distance,
            sweep_volume=vol,
            sweep_delta=delta,
            reclaim_status=reclaim,
            reversal_confirmation=reversal,
            prior_touches=2,
            raw_metrics={
                "swept_level": swept_level,
                "distance": distance,
                "volume": vol,
                "delta": delta,
            },
            context_metrics={
                "regime": regime,
                "reclaimed": reclaim,
                "reversal": reversal,
            },
        )
