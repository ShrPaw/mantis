"""
Core microstructure metrics engine.
Computes delta, cumulative delta, imbalance, trade frequency, and absorption.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class TradeData:
    price: float
    qty: float
    is_buyer_maker: bool  # True = taker sell (aggressive sell), False = taker buy
    timestamp: float
    trade_id: int


@dataclass
class OrderBookLevel:
    price: float
    qty: float


@dataclass
class FlowMetrics:
    """Snapshot of order flow metrics at a point in time."""
    taker_buy_vol: float = 0.0
    taker_sell_vol: float = 0.0
    delta: float = 0.0
    cum_delta: float = 0.0
    trade_count: int = 0
    trade_frequency: float = 0.0  # trades per second
    imbalance: float = 0.0  # (buy - sell) / (buy + sell)
    vwap: float = 0.0
    last_price: float = 0.0
    session_high: float = 0.0
    session_low: float = float("inf")

    def to_dict(self) -> dict:
        return {
            "taker_buy_vol": round(self.taker_buy_vol, 4),
            "taker_sell_vol": round(self.taker_sell_vol, 4),
            "delta": round(self.delta, 4),
            "cum_delta": round(self.cum_delta, 4),
            "trade_count": self.trade_count,
            "trade_frequency": round(self.trade_frequency, 2),
            "imbalance": round(self.imbalance, 4),
            "vwap": round(self.vwap, 2),
            "last_price": round(self.last_price, 2),
            "session_high": round(self.session_high, 2),
            "session_low": round(self.session_low, 2),
        }


@dataclass
class FootprintLevel:
    """Volume at a specific price level within a candle."""
    price: float
    bid_vol: float = 0.0
    ask_vol: float = 0.0
    delta: float = 0.0
    trade_count: int = 0


@dataclass
class FootprintCandle:
    """Footprint data for a single 1m candle."""
    open_time: float
    open: float = 0.0
    high: float = 0.0
    low: float = float("inf")
    close: float = 0.0
    levels: dict[float, FootprintLevel] = field(default_factory=dict)
    total_vol: float = 0.0
    total_delta: float = 0.0

    def add_trade(self, trade: TradeData):
        price_tick = round(trade.price, 1)  # bucket by $0.10
        if price_tick not in self.levels:
            self.levels[price_tick] = FootprintLevel(price=price_tick)
        level = self.levels[price_tick]

        if trade.is_buyer_maker:
            level.bid_vol += trade.qty
            level.delta -= trade.qty
        else:
            level.ask_vol += trade.qty
            level.delta += trade.qty
        level.trade_count += 1

        if self.open == 0.0:
            self.open = trade.price
        self.high = max(self.high, trade.price)
        self.low = min(self.low, trade.price)
        self.close = trade.price
        self.total_vol += trade.qty
        self.total_delta += trade.qty * (1 if not trade.is_buyer_maker else -1)

    def to_dict(self) -> dict:
        levels = []
        for price in sorted(self.levels.keys()):
            lv = self.levels[price]
            levels.append({
                "price": lv.price,
                "bid_vol": round(lv.bid_vol, 4),
                "ask_vol": round(lv.ask_vol, 4),
                "delta": round(lv.delta, 4),
                "imbalance": round(
                    (lv.ask_vol - lv.bid_vol) / max(lv.ask_vol + lv.bid_vol, 0.0001), 4
                ),
                "trades": lv.trade_count,
            })
        return {
            "open_time": self.open_time,
            "open": round(self.open, 2),
            "high": round(self.high, 2),
            "low": round(self.low, 2) if self.low != float("inf") else 0,
            "close": round(self.close, 2),
            "total_vol": round(self.total_vol, 4),
            "total_delta": round(self.total_delta, 4),
            "levels": levels,
        }


class MicrostructureEngine:
    """
    Core engine for computing microstructure metrics from raw trade and depth data.
    Maintains rolling windows and session state.
    """

    LARGE_TRADE_THRESHOLD = 0.5  # BTC — adjust based on what's "large"
    ROLLING_WINDOW = 300  # 5 minutes of seconds for frequency calc
    MAX_FOOTPRINT_CANDLES = 60  # keep last 60 1m footprint candles

    def __init__(self):
        self.flow = FlowMetrics()
        self._cum_delta = 0.0
        self._trade_timestamps: deque[float] = deque(maxlen=10000)
        self._volume_price_sum = 0.0
        self._volume_sum = 0.0
        self._session_start = time.time()

        # Footprint: candle open_time -> FootprintCandle
        self._footprints: dict[float, FootprintCandle] = {}
        self._current_candle_open: float = 0.0

        # Order book snapshot
        self._bids: dict[float, float] = {}
        self._asks: dict[float, float] = {}

        # Large trades for bubble tape
        self._large_trades: deque[dict] = deque(maxlen=200)

    def process_trade(self, data: dict) -> Optional[dict]:
        """
        Process an aggTrade event from Binance.
        Returns large trade dict if threshold met, else None.
        """
        trade = TradeData(
            price=float(data["p"]),
            qty=float(data["q"]),
            is_buyer_maker=data["m"],
            timestamp=data["T"] / 1000.0,
            trade_id=data["a"],
        )

        # Update flow metrics
        if trade.is_buyer_maker:
            self.flow.taker_sell_vol += trade.qty
        else:
            self.flow.taker_buy_vol += trade.qty

        self.flow.delta = self.flow.taker_buy_vol - self.flow.taker_sell_vol
        self._cum_delta += trade.qty * (1 if not trade.is_buyer_maker else -1)
        self.flow.cum_delta = self._cum_delta
        self.flow.trade_count += 1
        self.flow.last_price = trade.price

        # Session high/low
        self.flow.session_high = max(self.flow.session_high, trade.price)
        if self.flow.session_low == float("inf"):
            self.flow.session_low = trade.price
        else:
            self.flow.session_low = min(self.flow.session_low, trade.price)

        # VWAP
        self._volume_price_sum += trade.price * trade.qty
        self._volume_sum += trade.qty
        self.flow.vwap = self._volume_price_sum / self._volume_sum if self._volume_sum > 0 else 0

        # Trade frequency
        now = trade.timestamp
        self._trade_timestamps.append(now)
        cutoff = now - self.ROLLING_WINDOW
        while self._trade_timestamps and self._trade_timestamps[0] < cutoff:
            self._trade_timestamps.popleft()
        self.flow.trade_frequency = len(self._trade_timestamps) / self.ROLLING_WINDOW

        # Imbalance
        total = self.flow.taker_buy_vol + self.flow.taker_sell_vol
        self.flow.imbalance = (
            (self.flow.taker_buy_vol - self.flow.taker_sell_vol) / total if total > 0 else 0
        )

        # Footprint
        candle_open = int(now / 60) * 60
        if candle_open != self._current_candle_open:
            self._current_candle_open = candle_open
            if len(self._footprints) >= self.MAX_FOOTPRINT_CANDLES:
                oldest = min(self._footprints.keys())
                del self._footprints[oldest]
            self._footprints[candle_open] = FootprintCandle(open_time=candle_open)

        self._footprints[candle_open].add_trade(trade)

        # Large trade detection
        if trade.qty >= self.LARGE_TRADE_THRESHOLD:
            bubble = {
                "price": round(trade.price, 2),
                "qty": round(trade.qty, 4),
                "side": "sell" if trade.is_buyer_maker else "buy",
                "timestamp": trade.timestamp,
                "value_usd": round(trade.price * trade.qty, 2),
            }
            self._large_trades.append(bubble)
            return bubble

        return None

    def process_depth(self, data: dict):
        """Process depth update (100ms diff stream)."""
        for bid in data.get("b", []):
            price = float(bid[0])
            qty = float(bid[1])
            if qty == 0:
                self._bids.pop(price, None)
            else:
                self._bids[price] = qty

        for ask in data.get("a", []):
            price = float(ask[0])
            qty = float(ask[1])
            if qty == 0:
                self._asks.pop(price, None)
            else:
                self._asks[price] = qty

    def get_flow_metrics(self) -> dict:
        return self.flow.to_dict()

    def get_footprints(self) -> list[dict]:
        return [fp.to_dict() for fp in sorted(self._footprints.values(), key=lambda x: x.open_time)]

    def get_large_trades(self) -> list[dict]:
        return list(self._large_trades)

    def get_heatmap_data(self, depth_levels: int = 20) -> dict:
        """Get order book heatmap data around current price."""
        if not self._bids or not self._asks:
            return {"bids": [], "asks": [], "mid": 0}

        best_bid = max(self._bids.keys())
        best_ask = min(self._asks.keys())
        mid = (best_bid + best_ask) / 2

        # Get top N levels sorted
        sorted_bids = sorted(self._bids.items(), key=lambda x: x[0], reverse=True)[:depth_levels]
        sorted_asks = sorted(self._asks.items(), key=lambda x: x[0])[:depth_levels]

        bids = [{"price": round(p, 2), "qty": round(q, 4)} for p, q in sorted_bids]
        asks = [{"price": round(p, 2), "qty": round(q, 4)} for p, q in sorted_asks]

        return {"bids": bids, "asks": asks, "mid": round(mid, 2)}

    def get_absorption_zones(self) -> list[dict]:
        """
        Detect absorption: price levels where high volume traded but price didn't move.
        Simple heuristic: levels in recent footprints with high volume and near-zero delta.
        """
        zones = []
        for candle in list(self._footprints.values())[-5:]:
            for price, level in candle.levels.items():
                total = level.bid_vol + level.ask_vol
                if total > 1.0 and abs(level.delta) / total < 0.15:
                    zones.append({
                        "price": price,
                        "volume": round(total, 4),
                        "delta": round(level.delta, 4),
                        "candle_time": candle.open_time,
                    })
        return zones
