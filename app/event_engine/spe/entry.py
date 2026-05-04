"""
MANTIS SPE — Layer 7: Entry Logic

Entry is NOT market. Entry is passive limit (maker).

Placement: 30–50% retrace of displacement.

ONLY IF all previous layers are satisfied:
  - context valid (Layer 1)
  - pressure detected (Layer 2)
  - displacement confirmed (Layer 3)
  - trap condition present (Layer 5)
  - execution clean (Layer 6)
"""

from app.event_engine.spe.config import EntryConfig
from app.event_engine.context import EngineContext


class EntryCalculator:
    """
    Calculates passive limit entry prices based on displacement retrace.
    """

    def __init__(self, config: EntryConfig, ctx: EngineContext):
        self.cfg = config
        self.ctx = ctx

    def calculate(self, direction: str, displacement_origin: float,
                  displacement_end: float, timestamp: float) -> dict:
        """
        Calculate entry price for passive limit order.

        Args:
            direction: LONG or SHORT
            displacement_origin: price at start of displacement
            displacement_end: price at end of displacement
            timestamp: current time

        Returns:
            dict with entry_price, entry_type, and placement details
        """
        if displacement_origin <= 0 or displacement_end <= 0:
            return self._empty_result()

        if direction not in ("LONG", "SHORT"):
            return self._empty_result()

        # Calculate displacement range
        if direction == "LONG":
            # LONG entry: displacement was DOWN (origin > end), retrace UP
            # Entry at 30-50% retrace from end back toward origin
            displacement_range = displacement_origin - displacement_end
            if displacement_range <= 0:
                return self._empty_result()

            # 30-50% retrace
            retrace_low = displacement_end + displacement_range * self.cfg.retrace_min_pct
            retrace_high = displacement_end + displacement_range * self.cfg.retrace_max_pct
            entry_price = (retrace_low + retrace_high) / 2

        else:
            # SHORT entry: displacement was UP (end > origin), retrace DOWN
            # Entry at 30-50% retrace from end back toward origin
            displacement_range = displacement_end - displacement_origin
            if displacement_range <= 0:
                return self._empty_result()

            # 30-50% retrace
            retrace_low = displacement_end - displacement_range * self.cfg.retrace_max_pct
            retrace_high = displacement_end - displacement_range * self.cfg.retrace_min_pct
            entry_price = (retrace_low + retrace_high) / 2

        # Validate entry is reasonable (not too far from current price)
        current_price = self.ctx.buffer.last_price
        if current_price <= 0:
            return self._empty_result()

        entry_distance_bps = abs(entry_price - current_price) / current_price * 10000

        # Entry should be within reasonable distance
        if entry_distance_bps > 50:  # More than 50 bps away
            return self._empty_result()

        return {
            "entry_price": round(entry_price, 2),
            "entry_type": self.cfg.entry_type,
            "retrace_pct": (self.cfg.retrace_min_pct + self.cfg.retrace_max_pct) / 2,
            "entry_distance_bps": round(entry_distance_bps, 2),
            "placement_zone_low": round(retrace_low, 2),
            "placement_zone_high": round(retrace_high, 2),
            "valid": True,
        }

    def _empty_result(self) -> dict:
        return {
            "entry_price": 0.0,
            "entry_type": "",
            "retrace_pct": 0.0,
            "entry_distance_bps": 0.0,
            "placement_zone_low": 0.0,
            "placement_zone_high": 0.0,
            "valid": False,
        }
