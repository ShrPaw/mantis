"""
Auction Failure Research — Data Structures

Clean data models for research events.
No connection to existing MicrostructureEvent model.
"""

from dataclasses import dataclass, field
from typing import Optional
import uuid
import time


@dataclass
class AuctionEvent:
    """
    A single auction failure / breakout event.
    Created at detection time. Outcomes filled later.
    """

    # Identity
    event_id: str = ""
    timestamp: float = 0.0
    event_class: str = ""  # failed_aggressive_sell, failed_aggressive_buy,
                           # breakout_acceptance, breakout_rejection

    # Price context at detection
    price: float = 0.0
    side: str = ""  # sell_pressure / buy_pressure / upside_break / downside_break

    # Detection metrics (all relative)
    delta_ratio: float = 0.0          # signed delta / volume
    delta_percentile: float = 0.0     # vs recent history
    volume_percentile: float = 0.0    # vs recent history
    price_move_bps: float = 0.0       # price change in detection window
    distance_to_level_bps: float = 0.0  # distance to relevant level (prior H/L, range boundary)

    # Breakout-specific
    range_high: float = 0.0
    range_low: float = 0.0
    range_height_bps: float = 0.0
    break_distance_bps: float = 0.0
    held_outside: bool = False
    reclaimed: bool = False

    # Explanation
    explanation: str = ""

    # Forward outcomes (filled AFTER detection by outcome tracker)
    future_return_5s: Optional[float] = None
    future_return_10s: Optional[float] = None
    future_return_30s: Optional[float] = None
    future_return_60s: Optional[float] = None
    future_return_120s: Optional[float] = None
    future_return_300s: Optional[float] = None

    # Excursion
    mfe_30s: Optional[float] = None   # max favorable excursion (bps, signed)
    mae_30s: Optional[float] = None   # max adverse excursion (bps, signed)
    mfe_60s: Optional[float] = None
    mae_60s: Optional[float] = None

    # Timing
    time_to_positive: Optional[float] = None  # seconds until return > 0
    time_to_max_favorable: Optional[float] = None

    # Invalidation
    invalidated: bool = False         # true if MAE exceeds threshold before MFE
    invalidation_time: Optional[float] = None

    # Completion
    is_complete: bool = False

    def __post_init__(self):
        if not self.event_id:
            self.event_id = uuid.uuid4().hex[:12]
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def directional_return(self, raw_return_bps: float) -> float:
        """
        Convert raw return to directional return (positive = favorable).

        failed_aggressive_sell: sell aggression FAILED → expected move UP
          (buyers absorbed selling, price should rise)
          favorable = +raw

        failed_aggressive_buy: buy aggression FAILED → expected move DOWN
          (sellers absorbed buying, price should fall)
          favorable = -raw

        breakout_acceptance: breakout holds → continuation
          upside_break → favorable = +raw
          downside_break → favorable = -raw

        breakout_rejection: breakout failed → reversal
          upside break rejected → favorable = -raw (price falls back)
          downside break rejected → favorable = +raw (price bounces back)
        """
        if self.event_class == "failed_aggressive_sell":
            # Sell failed → expect UP → price rising is favorable
            return raw_return_bps
        elif self.event_class == "failed_aggressive_buy":
            # Buy failed → expect DOWN → price falling is favorable
            return -raw_return_bps
        elif self.event_class == "breakout_acceptance":
            # Continuation: follow break direction
            if self.side == "downside_break":
                return -raw_return_bps
            else:
                return raw_return_bps
        elif self.event_class == "breakout_rejection":
            # Reversal: opposite of break direction
            if self.side == "buy_pressure":
                # Downside break rejected → expect UP
                return raw_return_bps
            else:
                # Upside break rejected → expect DOWN
                return -raw_return_bps
        else:
            # Default: treat as long
            return raw_return_bps

    def to_csv_row(self) -> dict:
        """Flatten to CSV-friendly dict."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_class": self.event_class,
            "side": self.side,
            "price": self.price,
            "delta_ratio": round(self.delta_ratio, 4),
            "delta_percentile": round(self.delta_percentile, 4),
            "volume_percentile": round(self.volume_percentile, 4),
            "price_move_bps": round(self.price_move_bps, 4),
            "distance_to_level_bps": round(self.distance_to_level_bps, 4),
            "range_high": round(self.range_high, 2),
            "range_low": round(self.range_low, 2),
            "range_height_bps": round(self.range_height_bps, 4),
            "break_distance_bps": round(self.break_distance_bps, 4),
            "held_outside": self.held_outside,
            "reclaimed": self.reclaimed,
            "explanation": self.explanation,
            # Outcomes
            "future_return_5s": _opt(self.future_return_5s),
            "future_return_10s": _opt(self.future_return_10s),
            "future_return_30s": _opt(self.future_return_30s),
            "future_return_60s": _opt(self.future_return_60s),
            "future_return_120s": _opt(self.future_return_120s),
            "future_return_300s": _opt(self.future_return_300s),
            "mfe_30s": _opt(self.mfe_30s),
            "mae_30s": _opt(self.mae_30s),
            "mfe_60s": _opt(self.mfe_60s),
            "mae_60s": _opt(self.mae_60s),
            "time_to_positive": _opt(self.time_to_positive),
            "time_to_max_favorable": _opt(self.time_to_max_favorable),
            "invalidated": self.invalidated,
            "invalidation_time": _opt(self.invalidation_time),
            "is_complete": self.is_complete,
        }


def _opt(v):
    """Optional value to CSV-safe format."""
    if v is None:
        return ""
    return round(v, 4) if isinstance(v, float) else v


# CSV field order
CSV_FIELDS = [
    "event_id", "timestamp", "event_class", "side", "price",
    "delta_ratio", "delta_percentile", "volume_percentile",
    "price_move_bps", "distance_to_level_bps",
    "range_high", "range_low", "range_height_bps", "break_distance_bps",
    "held_outside", "reclaimed", "explanation",
    "future_return_5s", "future_return_10s", "future_return_30s",
    "future_return_60s", "future_return_120s", "future_return_300s",
    "mfe_30s", "mae_30s", "mfe_60s", "mae_60s",
    "time_to_positive", "time_to_max_favorable",
    "invalidated", "invalidation_time", "is_complete",
]
