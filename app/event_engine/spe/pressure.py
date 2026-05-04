"""
MANTIS SPE — Layer 2: Positioning Pressure

Detects crowd imbalance through:
  - Delta skew z-score (funding proxy): extreme skew = crowd positioning
  - OI proxy: volume delta bias direction = whether positions are opening or closing

Outputs:
  - crowd_direction: LONG_CROWD, SHORT_CROWD, or NONE
  - pressure_strength: 0-100
  - funding_z: raw z-score
"""

import math
from collections import deque

from app.event_engine.spe.config import PressureConfig
from app.event_engine.context import EngineContext


class PressureDetector:
    """
    Detects positioning pressure from microstructure flow data.

    LONG CROWD:
      - funding z ≥ +1.5 (delta skew extremely buy-heavy)
      - OI proxy rising (sustained directional volume)

    SHORT CROWD:
      - funding z ≤ -1.5 (delta skew extremely sell-heavy)
      - OI proxy rising

    UNWIND (handled by Layer 1 state machine):
      - funding extreme + OI decreasing
    """

    def __init__(self, config: PressureConfig, ctx: EngineContext):
        self.cfg = config
        self.ctx = ctx

        # Rolling delta skew values for z-score
        self._skew_values: deque = deque(maxlen=500)
        self._skew_timestamps: deque = deque(maxlen=500)

        # Per-period aggregation
        self._period_deltas: deque = deque(maxlen=100)
        self._period_volumes: deque = deque(maxlen=100)
        self._period_timestamps: deque = deque(maxlen=100)
        self._current_period_delta: float = 0.0
        self._current_period_volume: float = 0.0
        self._current_period_start: float = 0.0
        self._period_duration: float = 15.0  # 15 second periods

    def update(self, price: float, qty: float, delta: float,
               timestamp: float) -> dict:
        """
        Update pressure detector. Returns pressure analysis.
        """
        # Aggregate into periods
        if self._current_period_start == 0:
            self._current_period_start = timestamp

        if timestamp - self._current_period_start > self._period_duration:
            # Flush period
            if self._current_period_volume > 0:
                skew = self._current_period_delta / self._current_period_volume
                self._skew_values.append(skew)
                self._skew_timestamps.append(timestamp)
                self._period_deltas.append(self._current_period_delta)
                self._period_volumes.append(self._current_period_volume)
                self._period_timestamps.append(timestamp)

            self._current_period_delta = 0.0
            self._current_period_volume = 0.0
            self._current_period_start = timestamp

        self._current_period_delta += delta
        self._current_period_volume += qty

        # Prune old data
        self._prune(timestamp)

        # Compute z-score
        funding_z = self._compute_z_score()

        # Compute OI proxy
        oi_proxy = self._compute_oi_proxy(timestamp)

        # Determine crowd direction
        crowd_direction = "NONE"
        pressure_strength = 0.0

        if funding_z >= self.cfg.funding_z_long_threshold and oi_proxy > self.cfg.oi_rising_delta_threshold:
            crowd_direction = "LONG_CROWD"
            pressure_strength = self._map_pressure_strength(funding_z)
        elif funding_z <= self.cfg.funding_z_short_threshold and oi_proxy > self.cfg.oi_rising_delta_threshold:
            crowd_direction = "SHORT_CROWD"
            pressure_strength = self._map_pressure_strength(abs(funding_z))

        return {
            "crowd_direction": crowd_direction,
            "pressure_strength": pressure_strength,
            "funding_z": funding_z,
            "oi_proxy": oi_proxy,
        }

    def _compute_z_score(self) -> float:
        """Compute z-score of recent delta skew vs historical."""
        if len(self._skew_values) < self.cfg.funding_z_lookback_periods:
            return 0.0

        values = list(self._skew_values)
        n = len(values)

        # Use full history for mean/std
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        std = math.sqrt(variance)

        if std < 0.001:
            return 0.0

        # Recent skew (last 3 periods)
        recent = values[-3:] if len(values) >= 3 else values
        recent_mean = sum(recent) / len(recent)

        return (recent_mean - mean) / std

    def _compute_oi_proxy(self, timestamp: float) -> float:
        """
        OI proxy: sustained directional volume bias.

        If delta/volume ratio is consistently high in one direction,
        it suggests positions are being opened (OI rising).
        If ratio is declining, positions are being closed (OI falling).

        Returns 0-1: 1 = strongly rising OI, 0 = declining OI.
        """
        if len(self._period_deltas) < 5:
            return 0.5  # neutral

        recent_deltas = list(self._period_deltas)[-10:]
        recent_volumes = list(self._period_volumes)[-10:]

        # Count periods with strong directional bias
        strong_periods = 0
        for d, v in zip(recent_deltas, recent_volumes):
            if v > 0 and abs(d) / v > 0.5:
                strong_periods += 1

        return strong_periods / len(recent_deltas) if recent_deltas else 0.5

    def _map_pressure_strength(self, z_abs: float) -> float:
        """Map absolute z-score to 0-100 pressure strength."""
        normalized = min(z_abs / self.cfg.pressure_max_z, 1.0)
        return normalized * 100.0

    def _prune(self, now: float):
        """Remove old data."""
        cutoff = now - self.cfg.funding_z_window_seconds * 2
        while self._skew_timestamps and self._skew_timestamps[0] < cutoff:
            self._skew_timestamps.popleft()
            self._skew_values.popleft()
        while self._period_timestamps and self._period_timestamps[0] < cutoff:
            self._period_timestamps.popleft()
            self._period_deltas.popleft()
            self._period_volumes.popleft()
