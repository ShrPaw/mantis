"""
MANTIS SPE — Layer 1: Mantis State Machine

Defines the market context state:
  CASCADE  — Rapid directional move with liquidation cascade
  UNWIND   — Forced position closure (extreme funding + OI declining)
  IDLE     — No structural context (default)

A trade window exists ONLY IF state IN (CASCADE, UNWIND)
OR (imbalance_score ≥ 70 AND execution_quality ≥ 70 AND risk_score ≤ 60).

This is the mandatory gate. Nothing passes without context.
"""

import time
from collections import deque
from typing import Optional

from .config import MantisStateConfig
from ..context import EngineContext


class MantisStateMachine:
    """
    Detects CASCADE and UNWIND market states from microstructure data.

    CASCADE: price moving aggressively in one direction, liquidations spiking,
             continuation within N candles. Market is in forced-move mode.

    UNWIND:  funding proxy extreme (delta skew z-score), OI proxy declining
             (volume delta bias dropping). Crowd is being forced out.
    """

    def __init__(self, config: MantisStateConfig, ctx: EngineContext):
        self.cfg = config
        self.ctx = ctx
        self._state: str = "IDLE"
        self._state_since: float = 0.0
        self._last_state_change: float = 0.0

        # Rolling delta skew for funding z-score proxy
        self._delta_skew_window: deque = deque(maxlen=500)
        self._delta_skew_timestamps: deque = deque(maxlen=500)

        # Body size history for percentile
        self._body_sizes: deque = deque(maxlen=200)

        # Liquidation baseline
        self._volume_baseline: deque = deque(maxlen=100)

    def update(self, price: float, qty: float, delta: float,
               timestamp: float) -> str:
        """
        Update state machine on every trade tick.
        Returns current state: CASCADE, UNWIND, or IDLE.
        """
        # Update delta skew
        skew = delta / max(qty, 0.0001)
        self._delta_skew_window.append(skew)
        self._delta_skew_timestamps.append(timestamp)
        self._prune_skew(timestamp)

        # Update volume baseline
        self._volume_baseline.append(qty)

        # Check state transitions
        now = timestamp
        cascade = self._detect_cascade(price, qty, delta, timestamp)
        unwind = self._detect_unwind(price, qty, delta, timestamp)

        # State transition logic with cooldown
        if cascade and self._state != "CASCADE":
            if now - self._last_state_change > self.cfg.state_cooldown_seconds:
                self._state = "CASCADE"
                self._state_since = now
                self._last_state_change = now

        elif unwind and self._state != "UNWIND":
            if now - self._last_state_change > self.cfg.state_cooldown_seconds:
                self._state = "UNWIND"
                self._state_since = now
                self._last_state_change = now

        elif not cascade and not unwind:
            # Check if state should expire
            if self._state != "IDLE":
                if now - self._state_since > self.cfg.max_state_age_seconds:
                    self._state = "IDLE"
                    self._last_state_change = now

        return self._state

    def _detect_cascade(self, price: float, qty: float, delta: float,
                        timestamp: float) -> bool:
        """
        CASCADE detection:
        - Body size ≥ p85 of rolling distribution
        - Move ≥ 15 bps within recent window
        - Continuation: price continuing in same direction
        - Volume spike (liquidation proxy)
        """
        buffer = self.ctx.buffer
        prices, volumes, deltas, timestamps = buffer.get_window(
            self.cfg.cascade_continuation_candles * 60, timestamp
        )

        if len(prices) < 10:
            return False

        # Body size check
        body = abs(prices[-1] - prices[0])
        avg_price = sum(prices) / len(prices) if prices else 1
        body_bps = (body / avg_price) * 10000 if avg_price > 0 else 0

        # Store body size for percentile
        self._body_sizes.append(body_bps)
        if len(self._body_sizes) < 10:
            return False

        sorted_bodies = sorted(self._body_sizes)
        p85_idx = int(len(sorted_bodies) * 0.85)
        p85 = sorted_bodies[p85_idx] if p85_idx < len(sorted_bodies) else sorted_bodies[-1]

        if body_bps < p85:
            return False

        # Move magnitude check
        if body_bps < self.cfg.cascade_body_pct_threshold * 100:
            return False

        # Continuation: last few prices going same direction
        if len(prices) >= 5:
            recent_direction = 1 if prices[-1] > prices[-5] else -1
            move_direction = 1 if prices[-1] > prices[0] else -1
            if recent_direction != move_direction:
                return False

        # Volume spike: current volume vs baseline
        if self._volume_baseline:
            avg_vol = sum(self._volume_baseline) / len(self._volume_baseline)
            if avg_vol > 0 and qty > avg_vol * self.cfg.cascade_liquidation_spike_mult:
                return True

        # Also check aggregate volume spike in window
        if volumes:
            total_vol = sum(volumes)
            window_count = len(volumes)
            if window_count > 0:
                avg_window_vol = total_vol / window_count
                if avg_window_vol > 0:
                    # Check if recent volume is spiking
                    recent_vol = sum(volumes[-5:]) / max(len(volumes[-5:]), 1)
                    if recent_vol > avg_window_vol * 2:
                        return True

        return False

    def _detect_unwind(self, price: float, qty: float, delta: float,
                       timestamp: float) -> bool:
        """
        UNWIND detection:
        - Funding proxy z-score extreme (delta skew)
        - OI proxy declining (volume delta bias dropping)
        """
        if len(self._delta_skew_window) < self.cfg.unwind_funding_z_threshold * 10:
            return False

        # Calculate z-score of recent delta skew
        skew_values = list(self._delta_skew_window)
        if len(skew_values) < 20:
            return False

        mean = sum(skew_values) / len(skew_values)
        variance = sum((s - mean) ** 2 for s in skew_values) / len(skew_values)
        std = variance ** 0.5

        if std < 0.001:
            return False

        recent_skew = sum(skew_values[-10:]) / 10
        z_score = (recent_skew - mean) / std

        # Funding z extreme check
        if abs(z_score) < self.cfg.unwind_funding_z_threshold:
            return False

        # OI proxy declining: check if delta bias is decreasing
        # (volume delta becoming less extreme = positions closing)
        buffer = self.ctx.buffer
        _, _, deltas_recent, _ = buffer.get_window(120, timestamp)
        _, _, deltas_older, _ = buffer.get_window(300, timestamp)

        if len(deltas_recent) < 10 or len(deltas_older) < 20:
            return False

        recent_bias = abs(sum(deltas_recent)) / max(sum(abs(d) for d in deltas_recent), 0.0001)
        # Compare with older window
        mid_point = len(deltas_older) // 2
        older_bias = abs(sum(deltas_older[:mid_point])) / max(
            sum(abs(d) for d in deltas_older[:mid_point]), 0.0001
        )

        # UNWIND: bias was extreme, now declining
        if older_bias > 0.6 and recent_bias < self.cfg.unwind_oi_decrease_pct + 0.3:
            return True

        return False

    def _prune_skew(self, now: float):
        """Remove old skew values."""
        cutoff = now - 600  # 10 min
        while self._delta_skew_timestamps and self._delta_skew_timestamps[0] < cutoff:
            self._delta_skew_timestamps.popleft()
            self._delta_skew_window.popleft()

    @property
    def state(self) -> str:
        return self._state

    @property
    def state_age(self) -> float:
        return time.time() - self._state_since if self._state_since > 0 else 0
