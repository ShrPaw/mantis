"""
MANTIS Event Engine — Outcome Tracker
Tracks forward outcomes for events WITHOUT lookahead bias.
At creation time, all outcomes are None. Filled only after horizons pass.
"""

import time
from collections import deque

from .config import OutcomeConfig
from .models import MicrostructureEvent


class OutcomeTracker:
    """
    After an event is detected, tracks forward outcomes.
    At event creation, future outcomes are empty/None.
    They are filled later ONLY after enough time has passed.
    """

    def __init__(self, config: OutcomeConfig):
        self.cfg = config
        self._pending: deque[dict] = deque(maxlen=2000)

    def register(self, event: MicrostructureEvent, initial_price: float):
        """Register an event for forward tracking."""
        self._pending.append({
            "event": event,
            "initial_price": initial_price,
            "created": event.timestamp,
            "measured_horizons": set(),
            "tp_hits": {},    # (horizon, level) -> bool
            "sl_hits": {},    # (horizon, level) -> bool
            "mfe_30s": 0.0,
            "mae_30s": 0.0,
            "mfe_120s": 0.0,
            "mae_120s": 0.0,
            "time_to_mf": None,
            "time_to_ma": None,
            "last_price": initial_price,
        })

    def update(self, current_price: float, now: float):
        """
        Update all pending events with current price.
        Called on every trade tick.
        Fills in outcomes as horizons are reached.
        """
        still_pending = []
        for entry in self._pending:
            event: MicrostructureEvent = entry["event"]
            initial = entry["initial_price"]
            created = entry["created"]
            fwd = event.forward

            if initial == 0:
                still_pending.append(entry)
                continue

            elapsed = now - created
            price_diff = current_price - initial
            return_bps = (price_diff / initial) * 10000

            # Update continuous metrics
            entry["last_price"] = current_price

            # MFE/MAE at 30s window
            if elapsed <= 30:
                entry["mfe_30s"] = max(entry["mfe_30s"], abs(price_diff) if price_diff > 0 else 0)
                entry["mae_30s"] = max(entry["mae_30s"], abs(price_diff) if price_diff < 0 else 0)
                if entry["time_to_mf"] is None and price_diff > 0:
                    entry["time_to_mf"] = elapsed
                if entry["time_to_ma"] is None and price_diff < 0:
                    entry["time_to_ma"] = elapsed

            # MFE/MAE at 120s window
            if elapsed <= 120:
                entry["mfe_120s"] = max(entry["mfe_120s"], abs(price_diff) if price_diff > 0 else 0)
                entry["mae_120s"] = max(entry["mae_120s"], abs(price_diff) if price_diff < 0 else 0)

            # Check each horizon
            all_done = True
            for horizon in self.cfg.horizons_seconds:
                if horizon in entry["measured_horizons"]:
                    continue
                if elapsed >= horizon:
                    # Fill this horizon's outcome
                    if horizon == 10:
                        fwd.future_return_10s = return_bps
                    elif horizon == 30:
                        fwd.future_return_30s = return_bps
                        fwd.max_favorable_excursion_30s = entry["mfe_30s"]
                        fwd.max_adverse_excursion_30s = entry["mae_30s"]
                    elif horizon == 60:
                        fwd.future_return_60s = return_bps
                    elif horizon == 120:
                        fwd.future_return_120s = return_bps
                        fwd.max_favorable_excursion_120s = entry["mfe_120s"]
                        fwd.max_adverse_excursion_120s = entry["mae_120s"]
                    elif horizon == 300:
                        fwd.future_return_300s = return_bps

                    # Check TP/SL levels
                    for tp_bps in self.cfg.tp_levels_bps:
                        key = f"tp_{tp_bps}"
                        if key not in entry["tp_hits"]:
                            tp_price = initial * (1 + tp_bps / 10000)
                            entry["tp_hits"][key] = current_price >= tp_price
                        # Also check if it was hit at any point (use MFE)
                        if entry["mfe_30s"] > 0:
                            mfe_bps = (entry["mfe_30s"] / initial) * 10000
                            if mfe_bps >= tp_bps:
                                entry["tp_hits"][key] = True

                    for sl_bps in self.cfg.sl_levels_bps:
                        key = f"sl_{sl_bps}"
                        if key not in entry["sl_hits"]:
                            sl_price = initial * (1 - sl_bps / 10000)
                            entry["sl_hits"][key] = current_price <= sl_price
                        if entry["mae_30s"] > 0:
                            mae_bps = (entry["mae_30s"] / initial) * 10000
                            if mae_bps >= sl_bps:
                                entry["sl_hits"][key] = True

                    entry["measured_horizons"].add(horizon)
                else:
                    all_done = False

            # Fill TP/SL and timing into forward outcome
            if 30 in entry["measured_horizons"]:
                fwd.hit_tp_0_10pct = entry["tp_hits"].get("tp_10", False)
                fwd.hit_tp_0_20pct = entry["tp_hits"].get("tp_20", False)
                fwd.hit_sl_0_10pct = entry["sl_hits"].get("sl_10", False)
                fwd.hit_sl_0_20pct = entry["sl_hits"].get("sl_20", False)
                fwd.time_to_max_favorable = entry["time_to_mf"]
                fwd.time_to_max_adverse = entry["time_to_ma"]

            if all_done:
                fwd.is_complete = True
                event.is_active = False
            else:
                still_pending.append(entry)

        self._pending = still_pending

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def get_pending_summary(self) -> dict:
        """Summary of pending outcome tracking."""
        return {
            "pending": len(self._pending),
            "oldest_age": max(
                (time.time() - e["created"] for e in self._pending), default=0
            ),
        }
