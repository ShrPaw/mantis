"""
MANTIS Event Engine — Shared Context
Rolling buffers, order book state, session stats, large trade history.
All detectors read from this shared context. No duplication.
"""

import time
from collections import deque
from typing import Optional


class RollingBuffer:
    """Time-indexed rolling buffer for trade data."""

    def __init__(self, max_age_seconds: float = 600.0, maxlen: int = 100000):
        self.max_age = max_age_seconds
        self._trades: deque = deque(maxlen=maxlen)
        self._prices: deque = deque(maxlen=maxlen)
        self._volumes: deque = deque(maxlen=maxlen)
        self._deltas: deque = deque(maxlen=maxlen)
        self._timestamps: deque = deque(maxlen=maxlen)
        self._cvd_values: deque = deque(maxlen=maxlen)
        self._cvd_running: float = 0.0

    def add(self, timestamp: float, price: float, qty: float, delta: float):
        self._trades.append({"ts": timestamp, "price": price, "qty": qty, "delta": delta})
        self._prices.append(price)
        self._volumes.append(qty)
        self._deltas.append(delta)
        self._timestamps.append(timestamp)
        self._cvd_running += delta
        self._cvd_values.append(self._cvd_running)
        self._prune(timestamp)

    def _prune(self, now: float):
        cutoff = now - self.max_age
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
            self._prices.popleft()
            self._volumes.popleft()
            self._deltas.popleft()
            self._cvd_values.popleft()
            self._trades.popleft()

    def get_window(self, window_seconds: float, now: float):
        """Get (prices, volumes, deltas, timestamps) within window."""
        cutoff = now - window_seconds
        start = None
        for i, ts in enumerate(self._timestamps):
            if ts >= cutoff:
                start = i
                break
        if start is None:
            return [], [], [], []
        return (
            list(self._prices)[start:],
            list(self._volumes)[start:],
            list(self._deltas)[start:],
            list(self._timestamps)[start:],
        )

    def get_cvd_window(self, window_seconds: float, now: float):
        """Get CVD values within window."""
        cutoff = now - window_seconds
        cvd_list = []
        for i, ts in enumerate(self._timestamps):
            if ts >= cutoff:
                cvd_list.append(self._cvd_values[i])
        return cvd_list

    @property
    def current_cvd(self) -> float:
        return self._cvd_running

    @property
    def last_price(self) -> float:
        return self._prices[-1] if self._prices else 0.0

    @property
    def count(self) -> int:
        return len(self._timestamps)

    def volume_in_window(self, window_seconds: float, now: float) -> float:
        cutoff = now - window_seconds
        return sum(v for ts, v in zip(self._timestamps, self._volumes) if ts >= cutoff)

    def delta_in_window(self, window_seconds: float, now: float) -> float:
        cutoff = now - window_seconds
        return sum(d for ts, d in zip(self._timestamps, self._deltas) if ts >= cutoff)

    def price_range_in_window(self, window_seconds: float, now: float):
        prices, _, _, _ = self.get_window(window_seconds, now)
        if not prices:
            return 0.0, 0.0
        return min(prices), max(prices)

    def percentile_volume(self, vol: float, window: float, now: float, lookback: int = 10) -> float:
        """What percentile is `vol` vs recent windows of same size."""
        scores = []
        for i in range(1, lookback + 1):
            offset = i * window
            _, w_vols, _, _ = self.get_window(window, now - offset)
            if w_vols:
                scores.append(sum(w_vols))
        if not scores:
            return 0.5
        return sum(1 for s in scores if vol > s) / len(scores)

    def percentile_delta(self, delta: float, window: float, now: float, lookback: int = 10) -> float:
        scores = []
        for i in range(1, lookback + 1):
            offset = i * window
            _, _, w_deltas, _ = self.get_window(window, now - offset)
            if w_deltas:
                scores.append(abs(sum(w_deltas)))
        if not scores:
            return 0.5
        return sum(1 for s in scores if abs(delta) > s) / len(scores)


class BookState:
    """Order book snapshot."""

    def __init__(self):
        self.best_bid: float = 0.0
        self.best_ask: float = 0.0
        self.bid_depth: float = 0.0  # total qty in top N levels
        self.ask_depth: float = 0.0
        self.bids: dict[float, float] = {}
        self.asks: dict[float, float] = {}
        self._last_update: float = 0.0

    def update(self, bids: list[tuple[float, float]], asks: list[tuple[float, float]]):
        """Update from bid/ask lists of (price, qty)."""
        for price, qty in bids:
            if qty == 0:
                self.bids.pop(price, None)
            else:
                self.bids[price] = qty
        for price, qty in asks:
            if qty == 0:
                self.asks.pop(price, None)
            else:
                self.asks[price] = qty

        if self.bids:
            self.best_bid = max(self.bids.keys())
            self.bid_depth = sum(q for _, q in sorted(self.bids.items(), key=lambda x: -x[0])[:10])
        if self.asks:
            self.best_ask = min(self.asks.keys())
            self.ask_depth = sum(q for _, q in sorted(self.asks.items(), key=lambda x: x[0])[:10])
        self._last_update = time.time()

    @property
    def mid(self) -> float:
        if self.best_bid > 0 and self.best_ask > 0:
            return (self.best_bid + self.best_ask) / 2
        return 0.0

    @property
    def spread(self) -> float:
        if self.best_bid > 0 and self.best_ask > 0:
            return self.best_ask - self.best_bid
        return 0.0

    @property
    def spread_bps(self) -> float:
        mid = self.mid
        if mid > 0:
            return (self.spread / mid) * 10000
        return 0.0


class SessionState:
    """Session-level stats."""

    def __init__(self):
        self.vwap: float = 0.0
        self.session_high: float = 0.0
        self.session_low: float = float("inf")
        self._volume_price_sum: float = 0.0
        self._volume_sum: float = 0.0

    def update(self, price: float, qty: float):
        self._volume_price_sum += price * qty
        self._volume_sum += qty
        if self._volume_sum > 0:
            self.vwap = self._volume_price_sum / self._volume_sum
        self.session_high = max(self.session_high, price)
        if self.session_low == float("inf"):
            self.session_low = price
        else:
            self.session_low = min(self.session_low, price)

    @property
    def session_low_safe(self) -> float:
        return self.session_low if self.session_low != float("inf") else 0.0


class LargeTradeHistory:
    """Track recent large trades for cluster detection."""

    def __init__(self, max_age_seconds: float = 300.0):
        self.max_age = max_age_seconds
        self._trades: deque = deque(maxlen=500)

    def add(self, price: float, qty: float, side: str, timestamp: float):
        self._trades.append({"price": price, "qty": qty, "side": side, "ts": timestamp})
        self._prune(timestamp)

    def _prune(self, now: float):
        cutoff = now - self.max_age
        while self._trades and self._trades[0]["ts"] < cutoff:
            self._trades.popleft()

    def get_window(self, window_seconds: float, now: float) -> list[dict]:
        cutoff = now - window_seconds
        return [t for t in self._trades if t["ts"] >= cutoff]

    @property
    def count(self) -> int:
        return len(self._trades)


class EngineContext:
    """
    Shared state container for all detectors.
    One instance, read by all detectors.
    """

    def __init__(self, rolling_buffer_seconds: float = 600.0):
        self.buffer = RollingBuffer(max_age_seconds=rolling_buffer_seconds)
        self.book = BookState()
        self.session = SessionState()
        self.large_trades = LargeTradeHistory()
        self._trades_processed: int = 0
        self._start_time: float = time.time()

    def on_trade(self, price: float, qty: float, delta: float, timestamp: float):
        """Called on every trade. Updates all shared state."""
        self.buffer.add(timestamp, price, qty, delta)
        self.session.update(price, qty)
        self._trades_processed += 1

    def on_book(self, bids: list[tuple[float, float]], asks: list[tuple[float, float]]):
        """Called on every book update."""
        self.book.update(bids, asks)

    def on_large_trade(self, price: float, qty: float, side: str, timestamp: float):
        """Called when a large trade is detected."""
        self.large_trades.add(price, qty, side, timestamp)

    @property
    def trades_processed(self) -> int:
        return self._trades_processed

    @property
    def uptime(self) -> float:
        return time.time() - self._start_time

    def classify_regime(self) -> str:
        """Simple regime classification from price volatility."""
        if len(self.buffer._prices) < 20:
            return "unknown"
        prices = list(self.buffer._prices)[-60:]
        price_range = max(prices) - min(prices)
        avg_price = sum(prices) / len(prices) if prices else 1
        volatility_pct = (price_range / avg_price) * 100 if avg_price > 0 else 0
        if volatility_pct > 1.0:
            return "high_volatility"
        elif volatility_pct > 0.3:
            return "normal"
        return "low_volatility"
