"""Feature pipeline — computes all market metrics from raw data.

Maintains rolling buffers and computes:
- Funding metrics
- OI metrics
- Liquidation metrics
- Trade flow metrics
- Order book metrics
- Execution quality metrics
"""

from __future__ import annotations

import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field

from engine.models import (
    Trade, OrderBook, FundingRate, OpenInterest, Liquidation, Candle,
    FundingFeatures, OIFeatures, LiquidationFeatures, TradeFlowFeatures,
    OrderBookFeatures, ExecutionQualityFeatures,
)

logger = logging.getLogger("mantis.features")


def _z_score(value: float, values: deque) -> float:
    """Compute z-score of value against a deque of historical values."""
    if len(values) < 10:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    std = math.sqrt(variance) if variance > 0 else 1e-10
    return (value - mean) / std


def _percentile_rank(value: float, values: deque) -> float:
    """Compute percentile rank of value within historical values."""
    if not values:
        return 0.5
    count_below = sum(1 for v in values if v < value)
    return count_below / len(values)


class FeaturePipeline:
    """Computes all market features from incoming raw data."""

    def __init__(self, config: dict):
        self.cfg = config

        # Rolling buffers
        self._funding_history: deque[float] = deque(maxlen=10000)
        self._oi_history: deque[tuple[float, float]] = deque(maxlen=10000)  # (ts, oi)
        self._trades: deque[Trade] = deque(maxlen=50000)
        self._liquidations: deque[Liquidation] = deque(maxlen=5000)
        self._books: deque[OrderBook] = deque(maxlen=1000)
        self._volumes_1m: deque[float] = deque(maxlen=1000)
        self._spreads: deque[float] = deque(maxlen=1000)
        self._depths: deque[float] = deque(maxlen=1000)
        self._deltas: deque[float] = deque(maxlen=1000)
        self._prices: deque[float] = deque(maxlen=10000)

        # Current values
        self._current_funding: Optional[FundingRate] = None
        self._current_oi: Optional[OpenInterest] = None
        self._last_book: Optional[OrderBook] = None
        self._last_price: float = 0.0
        self._cum_delta: float = 0.0

        # Rolling window configs
        self._flow_window = config.get("trade_flow", {}).get("rolling_window_seconds", 300)

    # ── Data Ingestion ─────────────────────────────────────────────────

    def on_trade(self, trade: Trade):
        """Ingest a new trade."""
        self._trades.append(trade)
        self._last_price = trade.price
        self._prices.append(trade.price)
        delta = trade.qty if trade.side == "buy" else -trade.qty
        self._cum_delta += delta
        self._deltas.append(delta)

    def on_book(self, book: OrderBook):
        """Ingest order book update."""
        self._books.append(book)
        self._last_book = book
        if book.spread_bps > 0:
            self._spreads.append(book.spread_bps)
        total_depth = sum(l.qty for l in book.bids[:10]) + sum(l.qty for l in book.asks[:10])
        self._depths.append(total_depth)

    def on_funding(self, funding: FundingRate):
        """Ingest funding rate update."""
        self._current_funding = funding
        self._funding_history.append(funding.rate)

    def on_open_interest(self, oi: OpenInterest):
        """Ingest open interest update."""
        self._current_oi = oi
        self._oi_history.append((oi.timestamp, oi.oi))

    def on_liquidation(self, liq: Liquidation):
        """Ingest liquidation event."""
        self._liquidations.append(liq)

    def on_candle(self, candle: Candle):
        """Ingest candle for volume tracking."""
        self._volumes_1m.append(candle.volume)

    # ── Feature Computation ────────────────────────────────────────────

    def compute_funding(self) -> FundingFeatures:
        """Compute all funding metrics."""
        f = FundingFeatures()
        if not self._current_funding:
            return f

        f.current = self._current_funding.rate
        if len(self._funding_history) < 2:
            return f

        rates = list(self._funding_history)
        f.rolling_mean = sum(rates) / len(rates)
        variance = sum((r - f.rolling_mean) ** 2 for r in rates) / len(rates)
        f.rolling_std = math.sqrt(variance) if variance > 0 else 1e-10
        f.z_score = (f.current - f.rolling_mean) / f.rolling_std if f.rolling_std > 0 else 0.0
        f.percentile = _percentile_rank(f.current, self._funding_history)

        # Persistence: fraction of last 24 windows with same sign
        recent = list(self._funding_history)[-24:]
        if recent:
            same_sign = sum(1 for r in recent if (r > 0) == (f.current > 0))
            f.persistence = same_sign / len(recent)

        f.direction = 1 if f.current > 0 else (-1 if f.current < 0 else 0)

        z_extreme = self.cfg.get("funding", {}).get("z_extreme", 2.0)
        pct_extreme = self.cfg.get("funding", {}).get("percentile_extreme", 0.95)
        f.positive_extreme = f.z_score >= z_extreme or f.percentile >= pct_extreme
        f.negative_extreme = f.z_score <= -z_extreme or f.percentile <= (1 - pct_extreme)

        return f

    def compute_oi(self) -> OIFeatures:
        """Compute all open interest metrics."""
        o = OIFeatures()
        if not self._current_oi or len(self._oi_history) < 2:
            return o

        o.current = self._current_oi.oi
        now = time.time()

        # Compute changes at different windows
        for window_min, attr in [(5, "change_5m"), (15, "change_15m"), (60, "change_1h")]:
            cutoff = now - window_min * 60
            old_oi = None
            for ts, oi_val in self._oi_history:
                if ts >= cutoff:
                    old_oi = oi_val
                    break
            if old_oi and old_oi > 0:
                setattr(o, attr, (o.current - old_oi) / old_oi * 100)

        # Z-score of current OI
        oi_values = deque(v for _, v in self._oi_history)
        o.z_score = _z_score(o.current, oi_values)
        o.percentile = _percentile_rank(o.current, oi_values)

        # Acceleration
        o.acceleration = o.change_15m - o.change_5m

        # Strong rise/fall
        strong_rise_pct = self.cfg.get("open_interest", {}).get("strong_rise_percentile", 0.80)
        strong_fall_pct = self.cfg.get("open_interest", {}).get("strong_fall_percentile", 0.20)
        o.strong_rise = _percentile_rank(o.change_1h, deque(v for _, v in self._oi_history)) >= strong_rise_pct
        o.strong_fall = _percentile_rank(o.change_1h, deque(v for _, v in self._oi_history)) <= strong_fall_pct

        return o

    def compute_liquidations(self) -> LiquidationFeatures:
        """Compute liquidation metrics."""
        lf = LiquidationFeatures()
        now = time.time()

        # Filter recent liquidations
        liqs_1m = [l for l in self._liquidations if now - l.timestamp <= 60]
        liqs_5m = [l for l in self._liquidations if now - l.timestamp <= 300]

        lf.count_1m = len(liqs_1m)
        lf.count_5m = len(liqs_5m)
        lf.notional_1m = sum(l.notional_usd for l in liqs_1m)
        lf.notional_5m = sum(l.notional_usd for l in liqs_5m)

        # Direction
        long_liq = sum(l.notional_usd for l in liqs_1m if l.side == "long")
        short_liq = sum(l.notional_usd for l in liqs_1m if l.side == "short")
        if long_liq > short_liq * 1.5:
            lf.direction = "long_liq"
        elif short_liq > long_liq * 1.5:
            lf.direction = "short_liq"
        else:
            lf.direction = "neutral"

        # Z-score of notional
        all_notional_1m = deque(maxlen=1000)
        # Build historical 1m notional from liquidation buffer
        # For now use current as z=0 if insufficient history
        if len(self._liquidations) > 20:
            # Compute rolling 1m notional at each point
            historical = []
            liq_list = list(self._liquidations)
            for i in range(len(liq_list)):
                t = liq_list[i].timestamp
                window = [l for l in liq_list if t - 60 <= l.timestamp <= t]
                historical.append(sum(l.notional_usd for l in window))
            all_notional_1m = deque(historical[-1000:])
            lf.notional_z = _z_score(lf.notional_1m, all_notional_1m)

        # Cascade detection
        cascade_pct = self.cfg.get("liquidations", {}).get("cascade_percentile", 0.95)
        if len(all_notional_1m) >= 20:
            lf.cascade_active = _percentile_rank(lf.notional_1m, all_notional_1m) >= cascade_pct
            if lf.cascade_active:
                lf.cascade_direction = "DOWN" if lf.direction == "long_liq" else "UP"

        # Cluster detection
        cluster_window = self.cfg.get("liquidations", {}).get("cluster_window_seconds", 60)
        if lf.count_1m >= 3:  # 3+ liquidations in 60s = cluster
            lf.cluster_detected = True

        return lf

    def compute_trade_flow(self) -> TradeFlowFeatures:
        """Compute trade flow metrics over rolling window."""
        tf = TradeFlowFeatures()
        now = time.time()
        cutoff = now - self._flow_window

        recent = [t for t in self._trades if t.timestamp >= cutoff]
        if not recent:
            return tf

        buy_vol = sum(t.qty for t in recent if t.side == "buy")
        sell_vol = sum(t.qty for t in recent if t.side == "sell")
        total = buy_vol + sell_vol

        tf.buy_volume = buy_vol
        tf.sell_volume = sell_vol
        tf.delta = buy_vol - sell_vol
        tf.cum_delta = self._cum_delta
        tf.trade_count = len(recent)

        if total > 0:
            tf.buy_pressure = buy_vol / total
            tf.sell_pressure = sell_vol / total

        strong_buy = self.cfg.get("trade_flow", {}).get("strong_buy_pressure", 0.65)
        strong_sell = self.cfg.get("trade_flow", {}).get("strong_sell_pressure", 0.65)
        tf.strong_buy = tf.buy_pressure >= strong_buy
        tf.strong_sell = tf.sell_pressure >= strong_sell

        # Delta z-score
        tf.delta_z = _z_score(tf.delta, self._deltas)

        # Trade frequency
        if len(recent) > 1:
            duration = recent[-1].timestamp - recent[0].timestamp
            tf.trade_frequency = len(recent) / max(duration, 1)

        # Volume spike
        vol_spike_pct = self.cfg.get("trade_flow", {}).get("volume_spike_percentile", 0.90)
        if self._volumes_1m:
            current_vol = sum(t.qty for t in recent if now - t.timestamp <= 60)
            tf.volume_spike = _percentile_rank(current_vol, self._volumes_1m) >= vol_spike_pct

        return tf

    def compute_order_book(self) -> OrderBookFeatures:
        """Compute order book metrics."""
        ob = OrderBookFeatures()
        book = self._last_book
        if not book:
            return ob

        ob.spread_bps = book.spread_bps
        ob.bid_depth = sum(l.qty for l in book.bids[:10])
        ob.ask_depth = sum(l.qty for l in book.asks[:10])

        total_depth = ob.bid_depth + ob.ask_depth
        if total_depth > 0:
            ob.book_imbalance = (ob.bid_depth - ob.ask_depth) / total_depth
            ob.depth_imbalance = ob.book_imbalance

        # Z-scores
        ob.spread_z = _z_score(ob.spread_bps, self._spreads)
        ob.depth_z = _z_score(total_depth, self._depths)

        # Liquidity thinning
        depth_danger_z = self.cfg.get("order_book", {}).get("depth_danger_z", -2.0)
        spread_danger_z = self.cfg.get("order_book", {}).get("spread_danger_z", 2.0)
        ob.liquidity_thinning = ob.depth_z <= depth_danger_z or ob.spread_z >= spread_danger_z

        # Sudden depth drop
        if len(self._depths) >= 5:
            recent_avg = sum(list(self._depths)[-5:]) / 5
            if recent_avg > 0 and total_depth < recent_avg * (1 - self.cfg.get("order_book", {}).get("sudden_depth_drop_pct", 0.50)):
                ob.sudden_depth_drop = True

        return ob

    def compute_execution_quality(self, flow: TradeFlowFeatures,
                                  book: OrderBookFeatures,
                                  liq: LiquidationFeatures) -> ExecutionQualityFeatures:
        """Compute execution quality score."""
        eq = ExecutionQualityFeatures()
        eq.spread_bps = book.spread_bps

        # Expected slippage: rough estimate based on spread + depth
        if book.bid_depth > 0 and book.ask_depth > 0:
            min_depth = min(book.bid_depth, book.ask_depth)
            # Slippage increases as depth decreases
            eq.expected_slippage_bps = book.spread_bps + max(0, 2.0 - min_depth / 10) * 0.5
        else:
            eq.expected_slippage_bps = book.spread_bps * 2

        eq.available_depth_usd = (book.bid_depth + book.ask_depth) * self._last_price
        eq.volatility_burst = flow.volume_spike
        eq.book_stable = not book.liquidity_thinning and not book.sudden_depth_drop

        # Score computation (0-100)
        score = 100.0

        # Spread penalty
        max_spread = self.cfg.get("execution", {}).get("max_spread_bps", 2.0)
        if eq.spread_bps > max_spread:
            score -= min(30, (eq.spread_bps - max_spread) * 15)

        # Slippage penalty
        max_slip = self.cfg.get("execution", {}).get("max_expected_slippage_bps", 4.0)
        if eq.expected_slippage_bps > max_slip:
            score -= min(25, (eq.expected_slippage_bps - max_slip) * 10)

        # Depth penalty
        min_depth_usd = self.cfg.get("execution", {}).get("min_depth_usd", 50000)
        if eq.available_depth_usd < min_depth_usd:
            score -= min(20, (1 - eq.available_depth_usd / min_depth_usd) * 20)

        # Volatility penalty
        if eq.volatility_burst:
            score -= 15

        # Cascade penalty
        if liq.cascade_active:
            score -= 20

        # Book instability penalty
        if not eq.book_stable:
            score -= 10

        eq.score = max(0, min(100, score))
        return eq

    # ── Snapshot ───────────────────────────────────────────────────────

    def compute_all(self) -> dict:
        """Compute all features and return as dict."""
        funding = self.compute_funding()
        oi = self.compute_oi()
        liq = self.compute_liquidations()
        flow = self.compute_trade_flow()
        book = self.compute_order_book()
        exec_quality = self.compute_execution_quality(flow, book, liq)

        return {
            "funding": funding,
            "oi": oi,
            "liquidation": liq,
            "trade_flow": flow,
            "order_book": book,
            "execution_quality": exec_quality,
            "last_price": self._last_price,
            "timestamp": time.time(),
        }
