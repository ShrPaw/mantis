"""
Auction Failure Research — Outcome Tracker

Tracks forward outcomes for research events.
No lookahead bias. Outcomes filled only after horizons pass.
"""

import time
from collections import deque
from typing import Optional

from .config import OutcomeConfig
from .models import AuctionEvent


class OutcomeTracker:
    """
    After an event is detected, tracks forward outcomes.
    At event creation, future outcomes are empty/None.
    They are filled later ONLY after enough time has passed.
    """

    def __init__(self, config: OutcomeConfig):
        self.cfg = config
        self._pending: deque = deque(maxlen=5000)

    def register(self, event: AuctionEvent, initial_price: float):
        """Register an event for forward tracking."""
        self._pending.append({
            "event": event,
            "initial_price": initial_price,
            "created": event.timestamp,
            "measured_horizons": set(),
            "mfe_30s": 0.0,  # max favorable (directional, in bps)
            "mae_30s": 0.0,  # max adverse (directional, in bps)
            "mfe_60s": 0.0,
            "mae_60s": 0.0,
            "time_to_positive": None,
            "time_to_max_favorable": None,
            "first_positive_time": None,
            "invalidated": False,
            "invalidation_time": None,
        })

    def update(self, current_price: float, now: float):
        """
        Update all pending events with current price.
        Called on every trade tick.
        """
        still_pending = []

        for entry in self._pending:
            event: AuctionEvent = entry["event"]
            initial = entry["initial_price"]
            created = entry["created"]

            if initial <= 0:
                still_pending.append(entry)
                continue

            elapsed = now - created
            raw_return_bps = (current_price - initial) / initial * 10000
            directional_return = event.directional_return(raw_return_bps)

            # ── Continuous tracking ──
            # MFE/MAE at 30s
            if elapsed <= 30:
                if directional_return > 0:
                    entry["mfe_30s"] = max(entry["mfe_30s"], directional_return)
                if directional_return < 0:
                    entry["mae_30s"] = max(entry["mae_30s"], abs(directional_return))
                if entry["time_to_positive"] is None and directional_return > 0:
                    entry["time_to_positive"] = elapsed

            # MFE/MAE at 60s
            if elapsed <= 60:
                if directional_return > 0:
                    entry["mfe_60s"] = max(entry["mfe_60s"], directional_return)
                if directional_return < 0:
                    entry["mae_60s"] = max(entry["mae_60s"], abs(directional_return))
                if entry["time_to_max_favorable"] is None and directional_return > 0:
                    entry["time_to_max_favorable"] = elapsed

            # Invalidation check: MAE > 10bps before any positive
            if (not entry["invalidated"] and
                entry["mae_30s"] > 10.0 and
                entry["mfe_30s"] == 0.0):
                entry["invalidated"] = True
                entry["invalidation_time"] = elapsed

            # ── Horizon fills ──
            all_done = True
            for horizon in self.cfg.horizons_seconds:
                if horizon in entry["measured_horizons"]:
                    continue
                if elapsed >= horizon:
                    # Fill this horizon's outcome
                    if horizon == 5:
                        event.future_return_5s = raw_return_bps
                    elif horizon == 10:
                        event.future_return_10s = raw_return_bps
                    elif horizon == 30:
                        event.future_return_30s = raw_return_bps
                        event.mfe_30s = entry["mfe_30s"]
                        event.mae_30s = entry["mae_30s"]
                    elif horizon == 60:
                        event.future_return_60s = raw_return_bps
                        event.mfe_60s = entry["mfe_60s"]
                        event.mae_60s = entry["mae_60s"]
                    elif horizon == 120:
                        event.future_return_120s = raw_return_bps
                    elif horizon == 300:
                        event.future_return_300s = raw_return_bps

                    entry["measured_horizons"].add(horizon)
                else:
                    all_done = False

            # Fill timing and invalidation
            event.time_to_positive = entry["time_to_positive"]
            event.time_to_max_favorable = entry["time_to_max_favorable"]
            event.invalidated = entry["invalidated"]
            event.invalidation_time = entry["invalidation_time"]

            if all_done:
                event.is_complete = True
            else:
                still_pending.append(entry)

        self._pending = still_pending

    @property
    def pending_count(self) -> int:
        return len(self._pending)
