"""
Range Break / Failed Break Detector — Detects breakouts and failed breakouts.
"""

from ..base import BaseEventDetector
from ..models import RangeBreakEvent, MicrostructureEvent


class RangeBreakDetector(BaseEventDetector):

    def __init__(self, context):
        super().__init__(context)
        self._last_range_high: float = 0.0
        self._last_range_low: float = 0.0
        self._range_formed: bool = False

    @property
    def event_type(self) -> str:
        return "range_break"

    def update(self, trade_price: float, trade_qty: float,
               trade_delta: float, timestamp: float) -> list[MicrostructureEvent]:
        cfg = self.ctx.config.range_break
        ctx = self.ctx

        prices, volumes, deltas, _ = ctx.buffer.get_window(cfg.lookback_seconds, timestamp)
        if len(prices) < 20:
            return []

        # Find range from most of the window (exclude last portion for "break" zone)
        range_end = max(len(prices) - 10, len(prices) // 2)
        range_prices = prices[:range_end]
        if len(range_prices) < 10:
            return []

        range_high = max(range_prices)
        range_low = min(range_prices)
        range_height = range_high - range_low

        if range_height < cfg.min_range_height_usd:
            return []

        # Count touches of range boundaries
        high_touches = sum(1 for p in range_prices if abs(p - range_high) < 10)
        low_touches = sum(1 for p in range_prices if abs(p - range_low) < 10)
        total_touches = high_touches + low_touches

        if total_touches < cfg.min_range_touches:
            return []

        self._last_range_high = range_high
        self._last_range_low = range_low
        self._range_formed = True

        # Check for break above
        break_threshold = range_height * cfg.break_threshold_bps / 10000
        recent_prices = prices[-10:]
        recent_vol = sum(volumes[-10:])
        recent_delta = sum(deltas[-10:])

        events = []

        # Upside break
        if trade_price > range_high + break_threshold:
            break_dist = trade_price - range_high
            # Check if it failed (came back inside)
            came_back = any(p <= range_high + break_threshold * 0.5 for p in recent_prices[-5:]) if len(recent_prices) >= 5 else False

            evt = self._build(
                "up_break", trade_price, timestamp,
                range_high, range_low, break_dist,
                recent_vol, recent_delta,
                continuation=break_dist if not came_back else 0,
                failed=came_back,
            )
            events.append(evt)

        # Downside break
        if trade_price < range_low - break_threshold:
            break_dist = range_low - trade_price
            came_back = any(p >= range_low - break_threshold * 0.5 for p in recent_prices[-5:]) if len(recent_prices) >= 5 else False

            evt = self._build(
                "down_break", trade_price, timestamp,
                range_high, range_low, break_dist,
                recent_vol, recent_delta,
                continuation=break_dist if not came_back else 0,
                failed=came_back,
            )
            events.append(evt)

        return events

    def _build(self, side: str, price: float, timestamp: float,
               range_high: float, range_low: float, break_dist: float,
               vol: float, delta: float, continuation: float,
               failed: bool) -> RangeBreakEvent:
        ctx = self.ctx
        regime = ctx.classify_regime()
        scorer = ctx.scoring
        range_height = range_high - range_low

        range_quality = min(total_touches / 6.0, 1.0) if hasattr(self, '_last_touches') else 0.5
        scores = scorer.score_range_break(
            break_strength=min(break_dist / 50, 1.0),
            volume_pct=min(vol / 10, 1.0),
            range_quality=0.5,
            regime=regime,
        )

        direction = "up" if side == "up_break" else "down"
        explanation = (
            f"{direction.title()} break detected: price broke {'above' if side == 'up_break' else 'below'} "
            f"range [{range_low:.0f}-{range_high:.0f}] by {break_dist:.1f} USD. "
            f"Volume: {vol:.2f} BTC, delta: {delta:+.2f}. "
            f"{'FAILED — reclaimed into range' if failed else 'Continuation in progress'}."
        )

        return RangeBreakEvent(
            price=price,
            timestamp=timestamp,
            side=side,
            explanation=explanation,
            scores=scores,
            range_high=range_high,
            range_low=range_low,
            break_distance=break_dist,
            break_volume=vol,
            break_delta=delta,
            continuation_after_break=continuation,
            failed_break_status=failed,
            reclaim_time=0.0 if not failed else 0.0,
            range_context_score=0.5,
            raw_metrics={
                "range_high": range_high, "range_low": range_low,
                "range_height": range_height,
                "break_distance": break_dist, "volume": vol, "delta": delta,
            },
            context_metrics={"regime": regime, "failed": failed},
        )
