"""
Delta Divergence Detector — Price and CVD disagree.
"""

from ..base import BaseEventDetector
from ..models import DeltaDivergenceEvent, MicrostructureEvent


class DivergenceDetector(BaseEventDetector):

    @property
    def event_type(self) -> str:
        return "delta_divergence"

    def update(self, trade_price: float, trade_qty: float,
               trade_delta: float, timestamp: float) -> list[MicrostructureEvent]:
        cfg = self.ctx.config.divergence
        ctx = self.ctx

        prices, _, _, _ = ctx.buffer.get_window(cfg.window_seconds, timestamp)
        cvd_list = ctx.buffer.get_cvd_window(cfg.window_seconds, timestamp)

        if len(prices) < 10 or len(cvd_list) < 10:
            return []

        price_change = prices[-1] - prices[0]
        cvd_change = cvd_list[-1] - cvd_list[0]

        if abs(price_change) < cfg.min_price_move_usd:
            return []

        regime = ctx.classify_regime()
        scorer = ctx.scoring
        events = []

        # Bearish divergence: price higher high, CVD doesn't confirm
        if price_change > 0 and cvd_change <= cfg.min_cvd_opposite_move:
            strength = min(abs(price_change) / 100, 1.0)
            cvd_opp = min(max(-cvd_change, 0) / 5, 1.0)
            scores = scorer.score_divergence(strength, cvd_opp, regime)

            explanation = (
                f"Bearish delta divergence: price rose {price_change:.1f} USD over "
                f"{cfg.window_seconds}s but CVD {'fell' if cvd_change < 0 else 'stayed flat'} "
                f"({cvd_change:+.2f}). Price making higher highs without flow confirmation."
            )

            events.append(DeltaDivergenceEvent(
                price=trade_price,
                timestamp=timestamp,
                side="bearish_divergence",
                explanation=explanation,
                scores=scores,
                price_structure="higher_high",
                cvd_structure="lower_or_flat",
                divergence_window=cfg.window_seconds,
                price_at_detection=trade_price,
                cvd_at_detection=ctx.buffer.current_cvd,
                local_trend_context=regime,
                raw_metrics={"price_change": price_change, "cvd_change": cvd_change},
                context_metrics={"regime": regime},
            ))

        # Bullish divergence: price lower low, CVD doesn't confirm
        if price_change < 0 and cvd_change >= -cfg.min_cvd_opposite_move:
            strength = min(abs(price_change) / 100, 1.0)
            cvd_opp = min(max(cvd_change, 0) / 5, 1.0)
            scores = scorer.score_divergence(strength, cvd_opp, regime)

            explanation = (
                f"Bullish delta divergence: price fell {abs(price_change):.1f} USD over "
                f"{cfg.window_seconds}s but CVD {'rose' if cvd_change > 0 else 'stayed flat'} "
                f"({cvd_change:+.2f}). Price making lower lows without flow confirmation."
            )

            events.append(DeltaDivergenceEvent(
                price=trade_price,
                timestamp=timestamp,
                side="bullish_divergence",
                explanation=explanation,
                scores=scores,
                price_structure="lower_low",
                cvd_structure="higher_or_flat",
                divergence_window=cfg.window_seconds,
                price_at_detection=trade_price,
                cvd_at_detection=ctx.buffer.current_cvd,
                local_trend_context=regime,
                raw_metrics={"price_change": price_change, "cvd_change": cvd_change},
                context_metrics={"regime": regime},
            ))

        return events
