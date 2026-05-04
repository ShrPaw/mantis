"""
MANTIS SPE — Layer 5: Trap Detection (Confirmation)

Requires ONE of:
  1. Opposite liquidity taken after displacement
  2. Price fails to continue in crowd direction
  3. Rapid reversal within displacement range

This defines the "trap condition" — the critical confirmation
that a structural move has exhausted and reversal is likely.
"""

from collections import deque

from app.event_engine.spe.config import TrapConfig
from app.event_engine.context import EngineContext


class TrapDetector:
    """
    Detects trap conditions that confirm structural pressure events.

    A trap is when the market moves in one direction (the crowd direction),
    takes out liquidity, and then fails to continue — trapping participants.
    """

    def __init__(self, config: TrapConfig, ctx: EngineContext):
        self.cfg = config
        self.ctx = ctx

        # Track price action around displacement
        self._price_window: deque = deque(maxlen=200)
        self._delta_window: deque = deque(maxlen=200)
        self._timestamp_window: deque = deque(maxlen=200)

        # Volume tracking for confirmation
        self._volume_window: deque = deque(maxlen=200)

    def update(self, price: float, qty: float, delta: float,
               timestamp: float, crowd_direction: str,
               displacement_direction: str,
               displacement_origin: float,
               displacement_end: float) -> dict:
        """
        Update trap detector with current trade data and context.

        Args:
            crowd_direction: LONG_CROWD or SHORT_CROWD
            displacement_direction: UP or DOWN
            displacement_origin: price at start of displacement
            displacement_end: price at end of displacement
        """
        # Store data
        self._price_window.append(price)
        self._delta_window.append(delta)
        self._timestamp_window.append(timestamp)
        self._volume_window.append(qty)

        # Prune old data
        self._prune(timestamp)

        # Need sufficient data
        if len(self._price_window) < 10:
            return self._empty_result()

        # Check each trap condition
        trap_1 = self._check_liquidity_taken(
            crowd_direction, displacement_direction, timestamp
        )
        trap_2 = self._check_direction_failure(
            crowd_direction, displacement_direction, timestamp
        )
        trap_3 = self._check_rapid_reversal(
            displacement_origin, displacement_end, timestamp
        )

        trap_detected = trap_1 or trap_2 or trap_3
        trap_type = ""
        if trap_1:
            trap_type = "LIQUIDITY_TAKEN"
        elif trap_2:
            trap_type = "DIRECTION_FAIL"
        elif trap_3:
            trap_type = "RAPID_REVERSAL"

        return {
            "trap_detected": trap_detected,
            "trap_type": trap_type,
            "liquidity_taken": trap_1,
            "direction_failure": trap_2,
            "rapid_reversal": trap_3,
        }

    def _check_liquidity_taken(self, crowd_direction: str,
                               displacement_direction: str,
                               timestamp: float) -> bool:
        """
        Condition 1: Opposite liquidity taken after displacement.

        If crowd is LONG and displacement was UP, check if ask-side
        liquidity was aggressively consumed (large sell delta after up move).
        This indicates the move was used to fill orders, not to trend.
        """
        if not crowd_direction or not displacement_direction:
            return False

        # Get recent delta after displacement
        recent_deltas = list(self._delta_window)[-20:]
        if len(recent_deltas) < 5:
            return False

        recent_delta_sum = sum(recent_deltas)

        # LONG crowd + UP displacement: look for aggressive selling (negative delta)
        if crowd_direction == "LONG_CROWD" and displacement_direction == "UP":
            if recent_delta_sum < -abs(sum(recent_deltas[:5])) * 0.5:
                return True

        # SHORT crowd + DOWN displacement: look for aggressive buying (positive delta)
        if crowd_direction == "SHORT_CROWD" and displacement_direction == "DOWN":
            if recent_delta_sum > abs(sum(recent_deltas[:5])) * 0.5:
                return True

        return False

    def _check_direction_failure(self, crowd_direction: str,
                                 displacement_direction: str,
                                 timestamp: float) -> bool:
        """
        Condition 2: Price fails to continue in crowd direction.

        After displacement, price should continue if crowd is right.
        Failure to continue = crowd is trapped.
        """
        if len(self._price_window) < 15:
            return False

        prices = list(self._price_window)
        recent_prices = prices[-10:]
        older_prices = prices[-20:-10] if len(prices) >= 20 else prices[:10]

        if not older_prices or not recent_prices:
            return False

        recent_avg = sum(recent_prices) / len(recent_prices)
        older_avg = sum(older_prices) / len(older_prices)

        # Price change in bps
        price_change_bps = ((recent_avg - older_avg) / older_avg) * 10000 if older_avg > 0 else 0

        # LONG crowd expects UP: if price is flat or down, it's a failure
        if crowd_direction == "LONG_CROWD" and displacement_direction == "UP":
            if price_change_bps < -2:  # Price dropped after up displacement
                return True

        # SHORT crowd expects DOWN: if price is flat or up, it's a failure
        if crowd_direction == "SHORT_CROWD" and displacement_direction == "DOWN":
            if price_change_bps > 2:  # Price rose after down displacement
                return True

        return False

    def _check_rapid_reversal(self, displacement_origin: float,
                              displacement_end: float,
                              timestamp: float) -> bool:
        """
        Condition 3: Rapid reversal within displacement range.

        Price moves back through a significant portion of the displacement
        within the confirmation window, indicating the move was rejected.
        """
        if displacement_origin <= 0 or displacement_end <= 0:
            return False

        if len(self._price_window) < 5:
            return False

        prices = list(self._price_window)
        current_price = prices[-1]

        displacement_range = abs(displacement_end - displacement_origin)
        if displacement_range <= 0:
            return False

        # How far has price reversed back into the displacement?
        if displacement_end > displacement_origin:
            # UP displacement: reversal = price falling back
            reversal_distance = displacement_end - current_price
        else:
            # DOWN displacement: reversal = price rising back
            reversal_distance = current_price - displacement_origin

        reversal_pct = reversal_distance / displacement_range if displacement_range > 0 else 0

        # Rapid reversal: price reversed > 50% of displacement within window
        if reversal_pct > 0.5:
            # Check if this happened quickly
            timestamps = list(self._timestamp_window)
            if len(timestamps) >= 2:
                time_elapsed = timestamps[-1] - timestamps[0]
                if time_elapsed < self.cfg.confirmation_window_seconds:
                    # Check reversal magnitude in bps
                    avg_price = sum(prices) / len(prices) if prices else 1
                    reversal_bps = (reversal_distance / avg_price) * 10000 if avg_price > 0 else 0
                    if reversal_bps >= self.cfg.min_reversal_bps:
                        return True

        return False

    def _prune(self, now: float):
        """Remove old data."""
        cutoff = now - self.cfg.confirmation_window_seconds * 2
        while self._timestamp_window and self._timestamp_window[0] < cutoff:
            self._timestamp_window.popleft()
            self._price_window.popleft()
            self._delta_window.popleft()
            self._volume_window.popleft()

    def _empty_result(self) -> dict:
        return {
            "trap_detected": False,
            "trap_type": "",
            "liquidity_taken": False,
            "direction_failure": False,
            "rapid_reversal": False,
        }
