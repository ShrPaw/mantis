"""
MANTIS SPE — Layer 4: Structural Sweep (CRT Reinterpreted)

Defines sweep event:
  BEARISH: high swept, close back below level
  BULLISH: low swept, close back above level

IMPORTANT: This is NOT a signal. This is a context enhancer.
Sweep detection feeds into Layer 5 (Trap) for confirmation.
"""

from collections import deque
from typing import Optional

from .config import SweepConfig
from ..context import EngineContext


class SweepDetector:
    """
    Detects structural sweeps of significant price levels.

    A sweep occurs when:
    1. Price penetrates a prior significant level (high/low)
    2. Price closes back below/above that level
    3. The level had been tested at least min_prior_touches times
    """

    def __init__(self, config: SweepConfig, ctx: EngineContext):
        self.cfg = config
        self.ctx = ctx

        # Track significant levels (session highs/lows that were tested)
        self._significant_levels: deque = deque(maxlen=50)
        self._level_touches: dict[float, int] = {}
        self._level_timestamps: dict[float, float] = {}

        # Current sweep state
        self._sweep_active: bool = False
        self._sweep_direction: str = ""
        self._sweep_level: float = 0.0
        self._sweep_time: float = 0.0
        self._sweep_high: float = 0.0
        self._sweep_low: float = 0.0

    def update(self, price: float, qty: float, delta: float,
               timestamp: float) -> dict:
        """
        Update sweep detector. Returns sweep analysis.
        """
        buffer = self.ctx.buffer
        session = self.ctx.session

        # Update significant levels from session data
        self._update_levels(session, timestamp)

        # Get recent prices for sweep detection
        prices, _, _, timestamps = buffer.get_window(
            self.cfg.reclaim_window_seconds * 2, timestamp
        )

        if len(prices) < 5:
            return self._empty_result()

        # Check for sweep of each significant level
        for level_price in list(self._significant_levels):
            touches = self._level_touches.get(level_price, 0)
            if touches < self.cfg.min_prior_touches:
                continue

            # BEARISH sweep: price went above level, then closed below
            sweep_result = self._check_bearish_sweep(
                prices, level_price, timestamp
            )
            if sweep_result:
                return sweep_result

            # BULLISH sweep: price went below level, then closed above
            sweep_result = self._check_bullish_sweep(
                prices, level_price, timestamp
            )
            if sweep_result:
                return sweep_result

        # Check if active sweep has expired
        if self._sweep_active:
            if timestamp - self._sweep_time > self.cfg.reclaim_window_seconds:
                self._sweep_active = False

        return self._empty_result()

    def _check_bearish_sweep(self, prices: list, level: float,
                             timestamp: float) -> Optional[dict]:
        """
        BEARISH sweep:
        - Recent high > level (swept above)
        - Current price < level (closed back below)
        - Sweep distance > minimum
        """
        recent_high = max(prices[-10:]) if len(prices) >= 10 else max(prices)
        current_price = prices[-1]

        if recent_high <= level:
            return None  # Level not swept

        if current_price >= level:
            return None  # Not reclaimed yet

        # Check sweep distance
        avg_price = sum(prices) / len(prices) if prices else level
        sweep_distance_bps = ((recent_high - level) / avg_price) * 10000 if avg_price > 0 else 0

        if sweep_distance_bps < self.cfg.min_sweep_distance_bps:
            return None

        # Check reclaim timing
        # Find when price went above level
        above_time = None
        below_time = None
        for i, p in enumerate(prices):
            if p > level and above_time is None:
                above_time = i
            if above_time is not None and p < level:
                below_time = i
                break

        reclaimed = below_time is not None and above_time is not None

        if not reclaimed:
            return None

        self._sweep_active = True
        self._sweep_direction = "BEARISH"
        self._sweep_level = level
        self._sweep_time = timestamp

        return {
            "sweep_detected": True,
            "sweep_direction": "BEARISH",
            "sweep_level": level,
            "sweep_reclaimed": True,
            "sweep_distance_bps": sweep_distance_bps,
            "sweep_high": recent_high,
            "sweep_low": current_price,
            "prior_touches": self._level_touches.get(level, 0),
        }

    def _check_bullish_sweep(self, prices: list, level: float,
                             timestamp: float) -> Optional[dict]:
        """
        BULLISH sweep:
        - Recent low < level (swept below)
        - Current price > level (closed back above)
        - Sweep distance > minimum
        """
        recent_low = min(prices[-10:]) if len(prices) >= 10 else min(prices)
        current_price = prices[-1]

        if recent_low >= level:
            return None  # Level not swept

        if current_price <= level:
            return None  # Not reclaimed yet

        # Check sweep distance
        avg_price = sum(prices) / len(prices) if prices else level
        sweep_distance_bps = ((level - recent_low) / avg_price) * 10000 if avg_price > 0 else 0

        if sweep_distance_bps < self.cfg.min_sweep_distance_bps:
            return None

        # Check reclaim timing
        below_time = None
        above_time = None
        for i, p in enumerate(prices):
            if p < level and below_time is None:
                below_time = i
            if below_time is not None and p > level:
                above_time = i
                break

        reclaimed = above_time is not None and below_time is not None

        if not reclaimed:
            return None

        self._sweep_active = True
        self._sweep_direction = "BULLISH"
        self._sweep_level = level
        self._sweep_time = timestamp

        return {
            "sweep_detected": True,
            "sweep_direction": "BULLISH",
            "sweep_level": level,
            "sweep_reclaimed": True,
            "sweep_distance_bps": sweep_distance_bps,
            "sweep_high": current_price,
            "sweep_low": recent_low,
            "prior_touches": self._level_touches.get(level, 0),
        }

    def _update_levels(self, session, timestamp: float):
        """Update significant price levels from session data."""
        # Session high
        if session.session_high > 0:
            level = round(session.session_high, 1)
            if level not in self._level_touches:
                self._significant_levels.append(level)
                self._level_touches[level] = 0
                self._level_timestamps[level] = timestamp
            self._level_touches[level] = self._level_touches.get(level, 0) + 1

        # Session low
        if session.session_low_safe > 0:
            level = round(session.session_low_safe, 1)
            if level not in self._level_touches:
                self._significant_levels.append(level)
                self._level_touches[level] = 0
                self._level_timestamps[level] = timestamp
            self._level_touches[level] = self._level_touches.get(level, 0) + 1

        # VWAP
        if session.vwap > 0:
            level = round(session.vwap, 1)
            if level not in self._level_touches:
                self._significant_levels.append(level)
                self._level_touches[level] = 0
                self._level_timestamps[level] = timestamp

        # Prune old levels
        cutoff = timestamp - self.cfg.lookback_seconds
        while (self._significant_levels and
               self._level_timestamps.get(self._significant_levels[0], 0) < cutoff):
            old_level = self._significant_levels.popleft()
            self._level_touches.pop(old_level, None)
            self._level_timestamps.pop(old_level, None)

    def _empty_result(self) -> dict:
        return {
            "sweep_detected": False,
            "sweep_direction": "",
            "sweep_level": 0.0,
            "sweep_reclaimed": False,
            "sweep_distance_bps": 0.0,
            "sweep_high": 0.0,
            "sweep_low": 0.0,
            "prior_touches": 0,
        }
