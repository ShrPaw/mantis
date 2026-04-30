"""
MANTIS SPE — Layer 3: Displacement (Forced Move)

Detects structural displacement:
  - body_size ≥ rolling p85 of body distribution
  - move ≥ 15 bps
  - continuation within 3 candles
  - Optional: liquidation spike OR volume spike

This is NOT a signal. It's a structural condition that indicates
participants are being forced to act.
"""

import math
from collections import deque

from .config import DisplacementConfig
from ..context import EngineContext


class DisplacementDetector:
    """
    Detects forced-move displacement from tick-level data.
    """

    def __init__(self, config: DisplacementConfig, ctx: EngineContext):
        self.cfg = config
        self.ctx = ctx

        # Body size distribution for percentile calculation
        self._body_history: deque = deque(maxlen=200)

        # Displacement tracking
        self._displacement_start_price: float = 0.0
        self._displacement_start_time: float = 0.0
        self._displacement_direction: str = ""
        self._displacement_active: bool = False
        self._continuation_candles: int = 0

        # Volume baseline for spike detection
        self._volume_baseline: deque = deque(maxlen=100)

    def update(self, price: float, qty: float, delta: float,
               timestamp: float) -> dict:
        """
        Update displacement detector. Returns displacement analysis.
        """
        buffer = self.ctx.buffer

        # Get recent price action
        prices, volumes, deltas, timestamps = buffer.get_window(
            self.cfg.move_window_seconds, timestamp
        )

        if len(prices) < 5:
            return self._empty_result()

        # Compute body size (price range over window)
        window_high = max(prices)
        window_low = min(prices)
        avg_price = sum(prices) / len(prices) if prices else 1

        if avg_price <= 0:
            return self._empty_result()

        # Body in bps
        body_bps = ((window_high - window_low) / avg_price) * 10000

        # Store for percentile
        self._body_history.append(body_bps)

        # Percentile check
        if len(self._body_history) < 10:
            return self._empty_result()

        sorted_bodies = sorted(self._body_history)
        p85_idx = int(len(sorted_bodies) * self.cfg.body_percentile_threshold)
        p85 = sorted_bodies[min(p85_idx, len(sorted_bodies) - 1)]

        # Move magnitude check
        move_bps = body_bps
        if move_bps < self.cfg.min_move_bps:
            return self._empty_result()

        # Direction determination
        recent_price = prices[-1]
        early_price = prices[0]
        direction = "UP" if recent_price > early_price else "DOWN"

        # Body size check: must be >= p85
        body_ok = body_bps >= p85

        # Continuation check: price continuing in same direction
        continuation_ok = self._check_continuation(
            prices, direction, timestamp
        )

        # Volume spike check
        volume_spike = self._check_volume_spike(volumes, qty)

        # Displacement is confirmed if body >= p85 AND move >= threshold
        # AND continuation within candles
        displacement_confirmed = body_ok and move_bps >= self.cfg.min_move_bps

        if displacement_confirmed:
            if not self._displacement_active:
                self._displacement_start_price = early_price
                self._displacement_start_time = timestamps[0] if timestamps else timestamp
                self._displacement_direction = direction
                self._displacement_active = True

            # Update end price
            displacement_end = recent_price
            displacement_origin = self._displacement_start_price
        else:
            # Check if displacement expired
            if self._displacement_active:
                if timestamp - self._displacement_start_time > self.cfg.move_window_seconds * 2:
                    self._displacement_active = False
                    self._displacement_direction = ""

            displacement_end = 0.0
            displacement_origin = 0.0

        # Strength calculation
        strength = 0.0
        if displacement_confirmed:
            # Body size contribution (40%)
            body_score = min(body_bps / (p85 * 2), 1.0) * 40
            # Move magnitude contribution (30%)
            move_score = min(move_bps / (self.cfg.min_move_bps * 3), 1.0) * 30
            # Continuation contribution (20%)
            cont_score = 20 if continuation_ok else 0
            # Volume spike bonus (10%)
            vol_score = 10 if volume_spike else 0
            strength = body_score + move_score + cont_score + vol_score

        return {
            "displacement_detected": displacement_confirmed,
            "displacement_direction": direction if displacement_confirmed else "",
            "displacement_strength": min(strength, 100.0),
            "displacement_origin": self._displacement_start_price if displacement_confirmed else 0.0,
            "displacement_end": displacement_end,
            "displacement_body_bps": body_bps,
            "move_bps": move_bps,
            "body_percentile": body_bps / p85 if p85 > 0 else 0,
            "continuation_ok": continuation_ok,
            "volume_spike": volume_spike,
        }

    def _check_continuation(self, prices: list, direction: str,
                            timestamp: float) -> bool:
        """
        Check if price is continuing in displacement direction
        within the allowed candle window.
        """
        if len(prices) < 3:
            return False

        # Check last N segments for continuation
        segment_size = max(len(prices) // self.cfg.continuation_candles, 1)
        segments = []
        for i in range(0, len(prices), segment_size):
            segment = prices[i:i + segment_size]
            if segment:
                segments.append(segment)

        if len(segments) < 2:
            return False

        # Check if each segment is moving in same direction
        continuation_count = 0
        for i in range(1, len(segments)):
            prev_avg = sum(segments[i - 1]) / len(segments[i - 1])
            curr_avg = sum(segments[i]) / len(segments[i])
            change_bps = abs(curr_avg - prev_avg) / prev_avg * 10000 if prev_avg > 0 else 0

            if direction == "UP" and curr_avg > prev_avg and change_bps >= self.cfg.continuation_min_bps:
                continuation_count += 1
            elif direction == "DOWN" and curr_avg < prev_avg and change_bps >= self.cfg.continuation_min_bps:
                continuation_count += 1

        return continuation_count >= 1

    def _check_volume_spike(self, volumes: list, current_qty: float) -> bool:
        """Check if current volume is spiking vs baseline."""
        if not volumes:
            return False

        avg_vol = sum(volumes) / len(volumes) if volumes else 0
        if avg_vol <= 0:
            return False

        # Current trade vs average
        if current_qty > avg_vol * 3:
            return True

        # Recent volume vs overall
        if len(volumes) >= 5:
            recent = sum(volumes[-5:]) / 5
            if recent > avg_vol * 2:
                return True

        return False

    def _empty_result(self) -> dict:
        return {
            "displacement_detected": False,
            "displacement_direction": "",
            "displacement_strength": 0.0,
            "displacement_origin": 0.0,
            "displacement_end": 0.0,
            "displacement_body_bps": 0.0,
            "move_bps": 0.0,
            "body_percentile": 0.0,
            "continuation_ok": False,
            "volume_spike": False,
        }

    @property
    def is_active(self) -> bool:
        return self._displacement_active
