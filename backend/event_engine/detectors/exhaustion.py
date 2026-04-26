"""
Exhaustion Detector — Extreme aggressive flow with weakening continuation.
Buy exhaustion: massive buying near local high, price stalls.
Sell exhaustion: massive selling near local low, price stalls.
"""

from ..base import BaseEventDetector
from ..models import ExhaustionEvent, MicrostructureEvent


class ExhaustionDetector(BaseEventDetector):

    @property
    def event_type(self) -> str:
        return "exhaustion"

    def update(self, trade_price: float, trade_qty: float,
               trade_delta: float, timestamp: float) -> list[MicrostructureEvent]:
        cfg = self.ctx.config.exhaustion
        ctx = self.ctx
        window = cfg.window_seconds

        prices, volumes, deltas, timestamps = ctx.buffer.get_window(window, timestamp)
        if len(prices) < 10:
            return []

        total_vol = sum(volumes)
        total_delta = sum(deltas)
        if total_vol < cfg.min_volume_btc:
            return []

        # Split into halves for impact comparison
        half = len(prices) // 2
        first_prices = prices[:half]
        second_prices = prices[half:]
        first_range = max(first_prices) - min(first_prices) if len(first_prices) > 1 else 0
        second_range = max(second_prices) - min(second_prices) if len(second_prices) > 1 else 0
        first_vol = sum(volumes[:half])
        second_vol = sum(volumes[half:])

        first_impact = first_range / max(first_vol, 0.001)
        second_impact = second_range / max(second_vol, 0.001)

        # Impact must be declining
        if first_impact == 0:
            return []
        impact_decline = 1.0 - (second_impact / first_impact)
        if impact_decline < (1 - cfg.impact_decline_ratio):
            return []

        # Count recent bubbles
        bubble_cutoff = timestamp - cfg.bubble_window_seconds
        recent_bubbles = ctx.large_trades.get_window(cfg.bubble_window_seconds, timestamp)

        events = []

        # Buy exhaustion
        if total_delta > cfg.min_volume_btc * 0.5:
            local_high = max(prices)
            near_high = trade_price >= local_high - cfg.near_extreme_threshold_bps * local_high / 10000
            if near_high:
                evt = self._build_event(
                    "buy_exhaustion", trade_price, timestamp,
                    total_vol, total_delta, impact_decline,
                    recent_bubbles, "near_local_high",
                )
                if evt:
                    events.append(evt)

        # Sell exhaustion
        if total_delta < -cfg.min_volume_btc * 0.5:
            local_low = min(prices)
            near_low = trade_price <= local_low + cfg.near_extreme_threshold_bps * local_low / 10000
            if near_low:
                evt = self._build_event(
                    "sell_exhaustion", trade_price, timestamp,
                    total_vol, total_delta, impact_decline,
                    recent_bubbles, "near_local_low",
                )
                if evt:
                    events.append(evt)

        return events

    def _build_event(self, side: str, price: float, timestamp: float,
                     total_vol: float, total_delta: float, impact_decline: float,
                     recent_bubbles: list, extreme_ctx: str) -> ExhaustionEvent:
        ctx = self.ctx
        cfg = ctx.config.exhaustion
        regime = ctx.classify_regime()

        bubble_side = "buy" if side == "buy_exhaustion" else "sell"
        bubble_count = sum(1 for b in recent_bubbles if b["side"] == bubble_side)

        # CVD divergence
        cvd_list = ctx.buffer.get_cvd_window(cfg.window_seconds, timestamp)
        cvd_div = 0.0
        if len(cvd_list) > 2:
            cvd_change = cvd_list[-1] - cvd_list[0]
            prices, _, _, _ = ctx.buffer.get_window(cfg.window_seconds, timestamp)
            if prices:
                price_change = prices[-1] - prices[0]
                if price_change > 0 and cvd_change > 0:
                    cvd_div = 1.0 - min(abs(cvd_change) / max(abs(price_change) * 10, 0.001), 1.0)
                elif price_change < 0 and cvd_change < 0:
                    cvd_div = 1.0 - min(abs(cvd_change) / max(abs(price_change) * 10, 0.001), 1.0)

        scorer = ctx.scoring
        scores = scorer.score_exhaustion(
            volume_pct=min(total_vol / 10, 1.0),
            impact_decline=impact_decline,
            bubble_count=bubble_count,
            cvd_div=cvd_div,
            near_extreme=(extreme_ctx != ""),
            regime=regime,
        )

        action = "buying" if side == "buy_exhaustion" else "selling"
        explanation = (
            f"{side.replace('_', ' ').title()} detected: aggressive {action} volume "
            f"{total_vol:.2f} BTC near {extreme_ctx.replace('_', ' ')}, but price impact "
            f"declined {impact_decline * 100:.0f}%. {bubble_count} large trade bubbles. "
            f"CVD divergence: {cvd_div:.2f}."
        )

        return ExhaustionEvent(
            price=price,
            timestamp=timestamp,
            side=side,
            explanation=explanation,
            scores=scores,
            aggressive_volume=total_vol,
            delta=total_delta,
            bubble_count=bubble_count,
            price_impact_per_volume=impact_decline,
            continuation_failure_score=impact_decline,
            local_extreme_context=extreme_ctx,
            cvd_divergence_context=cvd_div,
            raw_metrics={
                "total_volume": total_vol,
                "total_delta": total_delta,
                "impact_decline": impact_decline,
                "bubble_count": bubble_count,
            },
            context_metrics={
                "regime": regime,
                "extreme_context": extreme_ctx,
                "cvd_divergence": cvd_div,
            },
        )
