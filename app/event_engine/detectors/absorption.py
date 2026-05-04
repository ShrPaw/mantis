"""
Absorption Detector — Detects when aggressive orders are absorbed.
Large sell delta but price doesn't break lower = buy absorption.
Large buy delta but price doesn't break higher = sell absorption.
"""

from app.event_engine.base import BaseEventDetector
from app.event_engine.context import EngineContext
from app.event_engine.models import AbsorptionEvent, MicrostructureEvent


class AbsorptionDetector(BaseEventDetector):

    @property
    def event_type(self) -> str:
        return "absorption"

    def update(self, trade_price: float, trade_qty: float,
               trade_delta: float, timestamp: float) -> list[MicrostructureEvent]:
        cfg = self.ctx.config.absorption
        ctx = self.ctx
        window = cfg.window_seconds

        prices, volumes, deltas, timestamps = ctx.buffer.get_window(window, timestamp)
        if len(prices) < 5:
            return []

        total_vol = sum(volumes)
        total_delta = sum(deltas)
        if total_vol < cfg.min_volume_btc:
            return []

        price_move = prices[-1] - prices[0]
        price_move_bps = abs(price_move / prices[0]) * 10000 if prices[0] > 0 else 0
        abs_delta_ratio = abs(total_delta) / total_vol

        vol_pct = ctx.buffer.percentile_volume(total_vol, window, timestamp)
        delta_pct = ctx.buffer.percentile_delta(total_delta, window, timestamp)

        # Must be high delta percentile
        if delta_pct < cfg.min_delta_percentile:
            return []

        price_non_cont = 1.0 - min(price_move_bps / (cfg.max_price_continuation_bps * 10), 1.0)

        events = []

        # Buy absorption: heavy selling but price doesn't break lower
        if total_delta < -cfg.min_volume_btc * 0.5 and price_move > -cfg.max_price_continuation_bps * prices[0] / 10000:
            if price_non_cont > 0.3:
                evt = self._build_event(
                    "buy_absorption", trade_price, timestamp,
                    total_vol, total_delta, price_move,
                    vol_pct, delta_pct, price_non_cont,
                )
                if evt:
                    events.append(evt)

        # Sell absorption: heavy buying but price doesn't break higher
        if total_delta > cfg.min_volume_btc * 0.5 and price_move < cfg.max_price_continuation_bps * prices[0] / 10000:
            if price_non_cont > 0.3:
                evt = self._build_event(
                    "sell_absorption", trade_price, timestamp,
                    total_vol, total_delta, price_move,
                    vol_pct, delta_pct, price_non_cont,
                )
                if evt:
                    events.append(evt)

        return events

    def _build_event(self, side: str, price: float, timestamp: float,
                     total_vol: float, total_delta: float, price_move: float,
                     vol_pct: float, delta_pct: float, price_non_cont: float) -> AbsorptionEvent | None:
        ctx = self.ctx
        cfg = ctx.config

        spread_ok = ctx.book.spread_bps < 5.0
        regime = ctx.classify_regime()
        book_support = ctx.book.bid_depth if side == "buy_absorption" else ctx.book.ask_depth

        scorer = ctx.scoring
        scores = scorer.score_absorption(
            volume_pct=vol_pct,
            delta_pct=delta_pct,
            price_non_continuation=price_non_cont,
            repeated_tests=1,
            book_support=book_support,
            spread_ok=spread_ok,
            regime=regime,
        )

        # Build explanation
        direction = "sell" if side == "buy_absorption" else "buy"
        action = "absorbed" if side == "buy_absorption" else "absorbed"
        pct_label = f"{int(delta_pct * 100)}th"
        move_bps = abs(price_move / price * 10000) if price > 0 else 0
        explanation = (
            f"{side.replace('_', ' ').title()} detected: {direction} aggression reached "
            f"{pct_label} percentile over {cfg.absorption.window_seconds}s, but price moved "
            f"only {move_bps:.1f} bps. Volume {total_vol:.2f} BTC with delta {total_delta:+.2f}."
        )

        return AbsorptionEvent(
            price=price,
            timestamp=timestamp,
            side=side,
            explanation=explanation,
            scores=scores,
            window_seconds=cfg.absorption.window_seconds,
            aggressive_volume=total_vol,
            signed_delta=total_delta,
            price_change_after_aggression=price_move,
            local_volume_percentile=vol_pct,
            delta_percentile=delta_pct,
            book_liquidity_context=book_support,
            vwap_distance=price - ctx.session.vwap if ctx.session.vwap > 0 else 0,
            spread_context=ctx.book.spread,
            regime_context=regime,
            raw_metrics={
                "total_volume": total_vol,
                "total_delta": total_delta,
                "price_move": price_move,
                "delta_ratio": abs(total_delta) / total_vol if total_vol > 0 else 0,
            },
            context_metrics={
                "regime": regime,
                "spread_bps": ctx.book.spread_bps,
                "vwap": ctx.session.vwap,
                "book_support": book_support,
            },
        )
