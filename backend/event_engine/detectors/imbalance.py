"""
Imbalance Detector — Aggressive directional order-flow imbalance.
Classifies as continuation, absorption, or exhaustion.
"""

from ..base import BaseEventDetector
from ..models import ImbalanceEvent, MicrostructureEvent


class ImbalanceDetector(BaseEventDetector):

    @property
    def event_type(self) -> str:
        return "imbalance"

    def update(self, trade_price: float, trade_qty: float,
               trade_delta: float, timestamp: float) -> list[MicrostructureEvent]:
        cfg = self.ctx.config.imbalance
        ctx = self.ctx

        _, volumes, deltas, _ = ctx.buffer.get_window(cfg.window_seconds, timestamp)
        if len(volumes) < 5:
            return []

        buy_vol = sum(v for v, d in zip(volumes, deltas) if d > 0)
        sell_vol = sum(v for v, d in zip(volumes, deltas) if d < 0)
        total = buy_vol + sell_vol

        if total < cfg.min_volume_btc:
            return []
        if buy_vol == 0 or sell_vol == 0:
            return []

        ratio = buy_vol / sell_vol if sell_vol > 0 else 999
        inv_ratio = sell_vol / buy_vol if buy_vol > 0 else 999
        net_delta = buy_vol - sell_vol

        events = []

        # Buy imbalance
        if ratio >= cfg.min_ratio:
            classification = self._classify(trade_price, net_delta, "buy", timestamp)
            prices, _, _, _ = ctx.buffer.get_window(cfg.window_seconds, timestamp)
            price_resp = (prices[-1] - prices[0]) if len(prices) > 1 else 0
            events.append(self._build("buy_imbalance", trade_price, timestamp,
                                      buy_vol, sell_vol, net_delta, ratio,
                                      price_resp, classification))

        # Sell imbalance
        if inv_ratio >= cfg.min_ratio:
            classification = self._classify(trade_price, net_delta, "sell", timestamp)
            prices, _, _, _ = ctx.buffer.get_window(cfg.window_seconds, timestamp)
            price_resp = (prices[-1] - prices[0]) if len(prices) > 1 else 0
            events.append(self._build("sell_imbalance", trade_price, timestamp,
                                      buy_vol, sell_vol, net_delta, inv_ratio,
                                      price_resp, classification))

        return events

    def _classify(self, price: float, delta: float, side: str, now: float) -> str:
        cfg = self.ctx.config.imbalance
        recent_prices, _, _, _ = self.ctx.buffer.get_window(cfg.classification_window_seconds, now)
        if len(recent_prices) < 2:
            return "continuation"
        move = recent_prices[-1] - recent_prices[0]
        if side == "buy":
            if move > 10:
                return "continuation"
            elif move < -5:
                return "absorption"
            return "exhaustion"
        else:
            if move < -10:
                return "continuation"
            elif move > 5:
                return "absorption"
            return "exhaustion"

    def _build(self, side: str, price: float, timestamp: float,
               buy_vol: float, sell_vol: float, delta: float, ratio: float,
               price_resp: float, classification: str) -> ImbalanceEvent:
        ctx = self.ctx
        regime = ctx.classify_regime()
        scorer = ctx.scoring

        scores = scorer.score_imbalance(
            ratio=ratio,
            volume_pct=min((buy_vol + sell_vol) / 10, 1.0),
            price_response=price_resp,
            regime=regime,
        )

        cont = 1.0 if classification == "continuation" else 0.0
        fail = 1.0 if classification in ("absorption", "exhaustion") else 0.0

        explanation = (
            f"{side.replace('_', ' ').title()} detected: {ratio:.1f}x ratio "
            f"(buy {buy_vol:.2f} / sell {sell_vol:.2f} BTC) over "
            f"{self.ctx.config.imbalance.window_seconds}s. "
            f"Price response: {price_resp:+.1f} USD. "
            f"Classification: {classification}."
        )

        return ImbalanceEvent(
            price=price,
            timestamp=timestamp,
            side=side,
            explanation=explanation,
            scores=scores,
            volume_buy=buy_vol,
            volume_sell=sell_vol,
            delta=delta,
            imbalance_ratio=ratio,
            price_response=price_resp,
            continuation_score=cont,
            failure_score=fail,
            classification=classification,
            raw_metrics={
                "buy_vol": buy_vol, "sell_vol": sell_vol,
                "ratio": ratio, "delta": delta,
            },
            context_metrics={"regime": regime, "classification": classification},
        )
