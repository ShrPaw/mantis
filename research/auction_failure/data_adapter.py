"""
Auction Failure Research — Data Adapter

Connects to MANTIS EngineContext's rolling buffer for data access.
Read-only. Does NOT modify the existing system.
Provides clean interface for the research detectors.
"""

import time
from collections import deque
from typing import Optional


class RollingWindow:
    """
    Sliding window of trade data for research use.
    Independent from MANTIS EngineContext — can run standalone
    or attach to existing buffer.
    """

    def __init__(self, max_age_seconds: float = 600.0):
        self.max_age = max_age_seconds
        self._prices: deque = deque(maxlen=200000)
        self._volumes: deque = deque(maxlen=200000)
        self._deltas: deque = deque(maxlen=200000)
        self._timestamps: deque = deque(maxlen=200000)
        self._cvd_running: float = 0.0
        self._cvd_values: deque = deque(maxlen=200000)

    def add(self, timestamp: float, price: float, qty: float, delta: float):
        """Add a trade tick."""
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

    def get_cvd_window(self, window_seconds: float, now: float) -> list:
        """Get CVD values within window."""
        cutoff = now - window_seconds
        result = []
        for i, ts in enumerate(self._timestamps):
            if ts >= cutoff:
                result.append(self._cvd_values[i])
        return result

    @property
    def last_price(self) -> float:
        return self._prices[-1] if self._prices else 0.0

    @property
    def count(self) -> int:
        return len(self._timestamps)

    @property
    def current_cvd(self) -> float:
        return self._cvd_running

    def percentile_delta(self, abs_delta: float, window: float,
                         now: float, lookback: int = 20) -> float:
        """Percentile rank of |delta| vs recent windows of same size."""
        scores = []
        for i in range(1, lookback + 1):
            offset = i * window
            _, _, w_deltas, _ = self.get_window(window, now - offset)
            if w_deltas:
                scores.append(abs(sum(w_deltas)))
        if not scores:
            return 0.5
        return sum(1 for s in scores if abs_delta > s) / len(scores)

    def percentile_volume(self, vol: float, window: float,
                          now: float, lookback: int = 20) -> float:
        """Percentile rank of volume vs recent windows of same size."""
        scores = []
        for i in range(1, lookback + 1):
            offset = i * window
            _, w_vols, _, _ = self.get_window(window, now - offset)
            if w_vols:
                scores.append(sum(w_vols))
        if not scores:
            return 0.5
        return sum(1 for s in scores if vol > s) / len(scores)


class LiveDataFeed:
    """
    Adapter to feed live trade data into the research window.
    Can attach to MANTIS EventManager or run standalone.
    """

    def __init__(self, buffer_depth_seconds: float = 600.0):
        self.window = RollingWindow(max_age_seconds=buffer_depth_seconds)
        self._trade_count: int = 0
        self._start_time: float = time.time()

    def on_trade(self, price: float, qty: float, delta: float, timestamp: float):
        """Process a single trade tick."""
        self.window.add(timestamp, price, qty, delta)
        self._trade_count += 1

    @property
    def trade_count(self) -> int:
        return self._trade_count

    @property
    def uptime(self) -> float:
        return time.time() - self._start_time

    def attach_to_mantis(self, mantis_ctx):
        """
        Attach to existing MANTIS EngineContext.
        Returns a callable that should be called on each trade.
        """
        def sync(price, qty, delta, timestamp):
            self.on_trade(price, qty, delta, timestamp)
        return sync
