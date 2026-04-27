"""
MANTIS Event Engine — Blacklist / Watchlist Enforcement Layer

Sits alongside the production EventManager. Does NOT modify detectors.
Does NOT change production scoring or filtering.

Blacklist:
  - sell_exhaustion, sell_imbalance, sell_cluster
  - Still logged. Never boost score. Never pass filter. Never tradeable.

Watchlist:
  - sell_absorption, down_break, up_break
  - Full snapshot capture (price/delta/CVD/volume paths)
  - Forward outcome tracking

This module is the SINGLE source of truth for blacklist/watchlist logic.
DirectionalBias and ConfidenceEngine import from here for consistency.
"""

import csv
import json
import logging
import os
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional

from .config import EventEngineConfig
from .context import EngineContext
from .models import MicrostructureEvent

logger = logging.getLogger(__name__)


# ============================================================
# Blacklist — event types that are structurally unsound
# ============================================================

BLACKLISTED_EVENT_TYPES = {
    "sell_exhaustion",
    "sell_imbalance",
    "sell_cluster",
}

# Side keywords that map to blacklisted types
BLACKLISTED_SIDE_KEYWORDS = {
    "sell_exhaustion": ["sell_exhaustion"],
    "sell_imbalance": ["sell_imbalance"],
    "sell_cluster": ["sell_cluster"],
}


def is_blacklisted(event_type: str, side: str) -> bool:
    """Check if an event is blacklisted by type or side."""
    for bl_type, keywords in BLACKLISTED_SIDE_KEYWORDS.items():
        for kw in keywords:
            if kw in event_type or kw in side:
                return True
    return False


# ============================================================
# Watchlist — candidate events tracked with full snapshots
# ============================================================

WATCHLISTED_EVENT_TYPES = {
    "sell_absorption",
    "down_break",
    "up_break",
}


def is_watchlisted(event_type: str, side: str) -> bool:
    """Check if an event is on the candidate watchlist."""
    for wt in WATCHLISTED_EVENT_TYPES:
        if wt in event_type or wt in side:
            return True
    return False


# ============================================================
# Enforcement Manager
# ============================================================

class BlacklistWatchlistManager:
    """
    Enforcement layer for blacklist and watchlist.

    Usage in manager.py (shadow integration):
      self.bw_manager = BlacklistWatchlistManager(self.config, self.ctx)

    Then in on_trade(), after event detection:
      for event in all_events:
          if self.bw_manager.is_blacklisted(event):
              # Log but do not score/filter as tradeable
              self.bw_manager.log_blacklisted(event)
              continue

          if self.bw_manager.is_watchlisted(event):
              self.bw_manager.capture_snapshot(event)
    """

    def __init__(self, config: EventEngineConfig, ctx: EngineContext):
        self.config = config
        self.ctx = ctx

        # Blacklist stats
        self._blacklisted_count: int = 0
        self._blacklisted_by_type: dict[str, int] = defaultdict(int)

        # Watchlist snapshots
        self._snapshots: deque = deque(maxlen=config.watchlist.max_snapshots)
        self._pending_outcomes: list[dict] = []
        self._watchlist_stats: dict[str, int] = defaultdict(int)

    # ── Blacklist ───────────────────────────────────────────

    def check_blacklisted(self, event: MicrostructureEvent) -> bool:
        """Is this event blacklisted?"""
        return is_blacklisted(event.event_type, event.side)

    def log_blacklisted(self, event: MicrostructureEvent):
        """
        Log a blacklisted event. It is still recorded for diagnostics,
        but with a BLACKLISTED tag and capped score.
        """
        self._blacklisted_count += 1
        self._blacklisted_by_type[f"{event.event_type}:{event.side}"] += 1

        # Tag the event
        event.validation_tags.append("BLACKLISTED")

        # Cap the composite score
        max_score = self.config.blacklist.max_composite_score
        if event.scores.composite_score > max_score:
            event.scores.composite_score = max_score

        # Cap reliability in confidence components
        if "event_reliability" in event.scores.confidence_components:
            event.scores.confidence_components["event_reliability"] = \
                min(event.scores.confidence_components["event_reliability"],
                    self.config.blacklist.reliability_cap)

        logger.debug(f"Blacklisted event: {event.event_type}:{event.side} "
                     f"(score capped to {max_score})")

    # ── Watchlist ───────────────────────────────────────────

    def check_watchlisted(self, event: MicrostructureEvent) -> bool:
        """Is this event on the watchlist?"""
        return is_watchlisted(event.event_type, event.side)

    def capture_snapshot(self, event: MicrostructureEvent):
        """
        Capture a full microstructure snapshot for a watchlist event.
        Called immediately after detection (before outcomes are known).
        """
        ts = event.timestamp
        price = event.price
        buf = self.ctx.buffer

        # ── Price/delta/volume paths BEFORE event ───────────
        before_sec = self.config.watchlist.path_before_seconds
        interval = self.config.watchlist.path_sample_interval

        prices, volumes, deltas, timestamps = buf.get_window(before_sec, ts)
        cvd_list = buf.get_cvd_window(before_sec, ts)

        price_path = self._sample_path(prices, timestamps, ts, interval)
        delta_path = self._sample_path(deltas, timestamps, ts, interval)
        vol_path = self._sample_path(volumes, timestamps, ts, interval)
        cvd_path = self._sample_cvd_path(cvd_list, timestamps, ts, interval)

        # ── Build snapshot ──────────────────────────────────
        snapshot = {
            "event_id": event.event_id,
            "timestamp": ts,
            "price": price,
            "event_type": event.event_type,
            "side": event.side,
            "regime": event.context_metrics.get("regime", "unknown"),
            "original_score": round(event.scores.composite_score, 4),
            "strength_score": round(event.scores.strength_score, 4),
            "confidence_score": round(event.scores.confidence_score, 4),
            "noise_score": round(event.scores.noise_score, 4),
            # Raw metrics
            "delta_ratio": round(event.raw_metrics.get("delta_ratio", 0), 4),
            "total_volume": round(event.raw_metrics.get("total_volume", 0), 4),
            "total_delta": round(event.raw_metrics.get("total_delta", 0), 4),
            # Paths (JSON strings)
            "price_path_before": json.dumps(price_path),
            "delta_path_before": json.dumps(delta_path),
            "cvd_path_before": json.dumps(cvd_path),
            "vol_path_before": json.dumps(vol_path),
            # Forward outcomes (filled by update_outcomes)
            "future_return_10s": None,
            "future_return_30s": None,
            "future_return_60s": None,
            "future_return_120s": None,
            "future_return_300s": None,
            "net_return_2bps": None,
            "net_return_4bps": None,
            "net_return_6bps": None,
            "mfe_30s": None,
            "mae_30s": None,
            "is_complete": False,
        }

        self._snapshots.append(snapshot)
        self._watchlist_stats[f"{event.event_type}:{event.side}"] += 1

        # Register for outcome tracking
        self._pending_outcomes.append({
            "snapshot": snapshot,
            "initial_price": price,
            "created": ts,
            "measured_horizons": set(),
            "mfe_30s": 0.0,
            "mae_30s": 0.0,
        })

        logger.debug(f"Watchlist snapshot captured: {event.event_type}:{event.side} "
                     f"at {price:.2f}")

    def update_outcomes(self, current_price: float, now: float):
        """
        Update all pending watchlist snapshots with current price.
        Called on every trade tick.
        """
        still_pending = []
        horizons = self.config.watchlist.horizons_seconds

        for entry in self._pending_outcomes:
            snapshot = entry["snapshot"]
            initial = entry["initial_price"]
            created = entry["created"]

            if initial == 0:
                still_pending.append(entry)
                continue

            elapsed = now - created
            return_bps = (current_price - initial) / initial * 10000

            # MFE/MAE
            if elapsed <= 30:
                entry["mfe_30s"] = max(entry["mfe_30s"], max(0, current_price - initial))
                entry["mae_30s"] = max(entry["mae_30s"], max(0, initial - current_price))

            # Fill horizons
            all_done = True
            for horizon in horizons:
                if horizon in entry["measured_horizons"]:
                    continue
                if elapsed >= horizon:
                    key = f"future_return_{horizon}s"
                    snapshot[key] = round(return_bps, 4)
                    entry["measured_horizons"].add(horizon)
                else:
                    all_done = False

            # Fill MFE/MAE at 30s
            if 30 in entry["measured_horizons"]:
                snapshot["mfe_30s"] = round(entry["mfe_30s"], 4)
                snapshot["mae_30s"] = round(entry["mae_30s"], 4)

            # Fill net returns when 60s is available
            if 60 in entry["measured_horizons"] and snapshot.get("future_return_60s") is not None:
                r60 = snapshot["future_return_60s"]
                snapshot["net_return_2bps"] = round(r60 - 2, 4)
                snapshot["net_return_4bps"] = round(r60 - 4, 4)
                snapshot["net_return_6bps"] = round(r60 - 6, 4)

            if all_done:
                snapshot["is_complete"] = True
            else:
                still_pending.append(entry)

        self._pending_outcomes = still_pending

    # ── Export ──────────────────────────────────────────────

    def export_watchlist_csv(self, path: str):
        """Export watchlist snapshots to CSV."""
        if not self._snapshots:
            return
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        fields = [
            "event_id", "timestamp", "price", "event_type", "side", "regime",
            "original_score", "strength_score", "confidence_score", "noise_score",
            "delta_ratio", "total_volume", "total_delta",
            "price_path_before", "delta_path_before", "cvd_path_before", "vol_path_before",
            "future_return_10s", "future_return_30s", "future_return_60s",
            "future_return_120s", "future_return_300s",
            "net_return_2bps", "net_return_4bps", "net_return_6bps",
            "mfe_30s", "mae_30s", "is_complete",
        ]

        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for snap in self._snapshots:
                row = {}
                for k in fields:
                    v = snap.get(k)
                    if isinstance(v, bool):
                        row[k] = str(v)
                    elif v is None:
                        row[k] = ''
                    else:
                        row[k] = v
                writer.writerow(row)

        logger.info(f"Watchlist exported {len(self._snapshots)} snapshots to {path}")

    def export_blacklist_stats(self) -> dict:
        """Return blacklist enforcement statistics."""
        return {
            "total_blacklisted": self._blacklisted_count,
            "by_type": dict(self._blacklisted_by_type),
        }

    def get_summary(self) -> dict:
        """Summary of both blacklist and watchlist."""
        by_type = {}
        complete = 0
        for snap in self._snapshots:
            t = snap["event_type"]
            by_type[t] = by_type.get(t, 0) + 1
            if snap["is_complete"]:
                complete += 1
        return {
            "blacklist": self.export_blacklist_stats(),
            "watchlist": {
                "total_snapshots": len(self._snapshots),
                "by_type": by_type,
                "complete": complete,
                "pending": len(self._pending_outcomes),
            },
        }

    # ── Internal ────────────────────────────────────────────

    def _sample_path(self, values: list, timestamps: list,
                     event_ts: float, interval: int) -> list[dict]:
        if not values or not timestamps:
            return []
        samples = []
        before_sec = self.config.watchlist.path_before_seconds
        for offset in range(interval, before_sec + 1, interval):
            target_ts = event_ts - offset
            best_idx = None
            best_diff = float('inf')
            for i, ts in enumerate(timestamps):
                diff = abs(ts - target_ts)
                if diff < best_diff:
                    best_diff = diff
                    best_idx = i
            if best_idx is not None and best_diff < interval:
                v = values[best_idx]
                samples.append({"t": -offset, "v": round(v, 4) if isinstance(v, (int, float)) else v})
        return samples

    def _sample_cvd_path(self, cvd_list: list, timestamps: list,
                         event_ts: float, interval: int) -> list[dict]:
        if not cvd_list or not timestamps:
            return []
        samples = []
        before_sec = self.config.watchlist.path_before_seconds
        for offset in range(interval, before_sec + 1, interval):
            target_ts = event_ts - offset
            best_idx = None
            best_diff = float('inf')
            for i, ts in enumerate(timestamps):
                diff = abs(ts - target_ts)
                if diff < best_diff:
                    best_diff = diff
                    best_idx = i
            if best_idx is not None and best_diff < interval and best_idx < len(cvd_list):
                samples.append({"t": -offset, "v": round(cvd_list[best_idx], 4)})
        return samples

    @property
    def pending_count(self) -> int:
        return len(self._pending_outcomes)
