"""
MANTIS SPE — Layer 8: Exit Logic

TP: nearest liquidity level / prior swing level
SL: beyond displacement origin

Ensures minimum R:R ratio before allowing signal.
"""

from collections import deque

from .config import ExitConfig
from ..context import EngineContext


class ExitCalculator:
    """
    Calculates TP and SL levels for SPE signals.
    """

    def __init__(self, config: ExitConfig, ctx: EngineContext):
        self.cfg = config
        self.ctx = ctx

        # Track swing levels
        self._swing_highs: deque = deque(maxlen=50)
        self._swing_lows: deque = deque(maxlen=50)
        self._swing_timestamps: deque = deque(maxlen=50)

    def calculate(self, direction: str, entry_price: float,
                  displacement_origin: float, displacement_end: float,
                  timestamp: float) -> dict:
        """
        Calculate TP and SL levels.

        Args:
            direction: LONG or SHORT
            entry_price: planned entry price
            displacement_origin: price at start of displacement
            displacement_end: price at end of displacement
            timestamp: current time

        Returns:
            dict with stop_loss, tp_levels, and R:R ratio
        """
        if entry_price <= 0 or displacement_origin <= 0:
            return self._empty_result()

        # Update swing levels
        self._update_swings(timestamp)

        # Calculate SL: beyond displacement origin with buffer
        sl_buffer = displacement_origin * self.cfg.sl_buffer_bps / 10000

        if direction == "LONG":
            # SL below displacement origin
            stop_loss = displacement_origin - sl_buffer
        else:
            # SL above displacement origin
            stop_loss = displacement_origin + sl_buffer

        # Calculate TP: nearest liquidity/swing level
        tp_levels = self._find_tp_levels(
            direction, entry_price, displacement_end, timestamp
        )

        if not tp_levels:
            return self._empty_result()

        # Calculate R:R
        risk = abs(entry_price - stop_loss)
        if risk <= 0:
            return self._empty_result()

        # Use first TP for R:R calculation
        reward = abs(tp_levels[0] - entry_price)
        rr_ratio = reward / risk if risk > 0 else 0

        # Check minimum R:R
        if rr_ratio < self.cfg.min_rr_ratio:
            return self._empty_result()

        return {
            "stop_loss": round(stop_loss, 2),
            "tp_levels": [round(tp, 2) for tp in tp_levels],
            "rr_ratio": round(rr_ratio, 2),
            "risk_bps": round(risk / entry_price * 10000, 2),
            "reward_bps": round(reward / entry_price * 10000, 2),
            "valid": True,
        }

    def _find_tp_levels(self, direction: str, entry_price: float,
                        displacement_end: float,
                        timestamp: float) -> list[float]:
        """
        Find TP levels at nearest liquidity/swing points.
        """
        buffer = self.ctx.buffer
        session = self.ctx.session

        tp_candidates = []

        # 1. Session high/low as TP
        if direction == "LONG":
            if session.session_high > entry_price:
                tp_candidates.append(session.session_high)
        else:
            if session.session_low_safe < entry_price and session.session_low_safe > 0:
                tp_candidates.append(session.session_low_safe)

        # 2. VWAP as TP
        if session.vwap > 0:
            if direction == "LONG" and session.vwap > entry_price:
                tp_candidates.append(session.vwap)
            elif direction == "SHORT" and session.vwap < entry_price:
                tp_candidates.append(session.vwap)

        # 3. Swing levels from recent price action
        prices, _, _, _ = buffer.get_window(
            self.cfg.tp_lookback_seconds, timestamp
        )

        if len(prices) >= 10:
            # Find local extremes
            for i in range(2, len(prices) - 2):
                # Local high
                if prices[i] > prices[i-1] and prices[i] > prices[i-2] and \
                   prices[i] > prices[i+1] and prices[i] > prices[i+2]:
                    if direction == "LONG" and prices[i] > entry_price:
                        tp_candidates.append(prices[i])

                # Local low
                if prices[i] < prices[i-1] and prices[i] < prices[i-2] and \
                   prices[i] < prices[i+1] and prices[i] < prices[i+2]:
                    if direction == "SHORT" and prices[i] < entry_price:
                        tp_candidates.append(prices[i])

        # 4. Displacement end as TP
        if direction == "LONG" and displacement_end > entry_price:
            tp_candidates.append(displacement_end)
        elif direction == "SHORT" and displacement_end < entry_price:
            tp_candidates.append(displacement_end)

        # Filter and sort TP levels
        if direction == "LONG":
            # LONG: TPs above entry, sorted ascending
            valid_tps = [tp for tp in tp_candidates if tp > entry_price]
            valid_tps.sort()

            # Check minimum distance
            min_distance = entry_price * self.cfg.tp_min_distance_bps / 10000
            valid_tps = [tp for tp in valid_tps if tp - entry_price >= min_distance]
        else:
            # SHORT: TPs below entry, sorted descending
            valid_tps = [tp for tp in tp_candidates if tp < entry_price]
            valid_tps.sort(reverse=True)

            # Check minimum distance
            min_distance = entry_price * self.cfg.tp_min_distance_bps / 10000
            valid_tps = [tp for tp in valid_tps if entry_price - tp >= min_distance]

        # Return up to 3 TP levels
        return valid_tps[:3]

    def _update_swings(self, timestamp: float):
        """Update swing high/low tracking."""
        buffer = self.ctx.buffer
        prices, _, _, timestamps = buffer.get_window(300, timestamp)

        if len(prices) < 10:
            return

        # Find swing points
        for i in range(2, len(prices) - 2):
            if i >= len(timestamps):
                break

            # Swing high
            if prices[i] > prices[i-1] and prices[i] > prices[i-2] and \
               prices[i] > prices[i+1] and prices[i] > prices[i+2]:
                if not self._swing_highs or abs(prices[i] - self._swing_highs[-1]) > 5:
                    self._swing_highs.append(prices[i])
                    self._swing_timestamps.append(timestamps[i])

            # Swing low
            if prices[i] < prices[i-1] and prices[i] < prices[i-2] and \
               prices[i] < prices[i+1] and prices[i] < prices[i+2]:
                if not self._swing_lows or abs(prices[i] - self._swing_lows[-1]) > 5:
                    self._swing_lows.append(prices[i])
                    self._swing_timestamps.append(timestamps[i])

    def _empty_result(self) -> dict:
        return {
            "stop_loss": 0.0,
            "tp_levels": [],
            "rr_ratio": 0.0,
            "risk_bps": 0.0,
            "reward_bps": 0.0,
            "valid": False,
        }
