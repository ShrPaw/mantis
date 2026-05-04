"""
MANTIS Event Engine — Candidate Watchlist Snapshot Storage

Stores full microstructure snapshots for watchlist event types.
Not tradeable. Diagnostic/observation only.

Watchlist events (sell_absorption, down_break, up_break) get:
  - timestamp, side, event_type, regime, scores
  - price path before/after
  - delta path before/after
  - CVD path before/after
  - volume path before/after
  - forward returns at all horizons
  - net returns at 2/4/6 bps
"""

import csv
import json
import os
import time
from collections import deque
from pathlib import Path
from typing import Optional

from app.event_engine.config import WatchlistConfig
from app.event_engine.context import EngineContext
from app.event_engine.models import MicrostructureEvent


class CandidateWatchlist:
    """
    Captures full microstructure snapshots for watchlist events.

    Usage:
      watchlist = CandidateWatchlist(config.watchlist, ctx)

      # After event detection, if event_type in watchlist:
      watchlist.capture(event)

      # Periodically, update forward outcomes:
      watchlist.update_outcomes(current_price, timestamp)

      # Export:
      watchlist.export_csv(path)
    """

    def __init__(self, config: WatchlistConfig, ctx: EngineContext):
        self.cfg = config
        self.ctx = ctx
        self._watchlist_types = config.event_types
        self._snapshots: deque = deque(maxlen=config.max_snapshots)
        self._pending_outcomes: list[dict] = []

    def is_watchlisted(self, event_type: str, side: str) -> bool:
        """Check if this event type is on the watchlist."""
        for wt in self._watchlist_types:
            if wt in event_type or wt in side:
                return True
        return False

    def capture(self, event: MicrostructureEvent):
        """
        Capture a full snapshot for a watchlist event.
        Called immediately after detection (before outcomes are known).
        """
        if not self.is_watchlisted(event.event_type, event.side):
            return

        ts = event.timestamp
        price = event.price

        # ── Price path before ───────────────────────────────
        before_prices, before_vols, before_deltas, before_ts = \
            self.ctx.buffer.get_window(self.cfg.path_before_seconds, ts)

        # Sample at intervals
        price_path_before = self._sample_path(
            before_prices, before_ts, ts, self.cfg.path_sample_interval, direction="before"
        )
        delta_path_before = self._sample_path(
            before_deltas, before_ts, ts, self.cfg.path_sample_interval, direction="before"
        )
        vol_path_before = self._sample_path(
            before_vols, before_ts, ts, self.cfg.path_sample_interval, direction="before"
        )

        # CVD path before
        cvd_list = self.ctx.buffer.get_cvd_window(self.cfg.path_before_seconds, ts)
        cvd_path_before = self._sample_cvd_path(
            cvd_list, before_ts, ts, self.cfg.path_sample_interval
        )

        # ── Build snapshot ──────────────────────────────────
        snapshot = {
            "event_id": event.event_id,
            "timestamp": ts,
            "price": price,
            "event_type": event.event_type,
            "side": event.side,
            "regime": event.context_metrics.get("regime", "unknown"),
            "original_score": event.scores.composite_score,
            "strength_score": event.scores.strength_score,
            "confidence_score": event.scores.confidence_score,
            "noise_score": event.scores.noise_score,
            "delta_ratio": event.raw_metrics.get("delta_ratio", event.raw_metrics.get("delta", 0)),
            "total_volume": event.raw_metrics.get("total_volume", event.raw_metrics.get("volume", 0)),
            "total_delta": event.raw_metrics.get("total_delta", event.raw_metrics.get("delta", 0)),
            # Paths (JSON strings for CSV storage)
            "price_path_before": json.dumps(price_path_before),
            "delta_path_before": json.dumps(delta_path_before),
            "cvd_path_before": json.dumps(cvd_path_before),
            "vol_path_before": json.dumps(vol_path_before),
            # Forward outcomes (filled later)
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

        # Register for outcome tracking
        self._pending_outcomes.append({
            "snapshot": snapshot,
            "initial_price": price,
            "created": ts,
            "measured_horizons": set(),
            "mfe_30s": 0.0,
            "mae_30s": 0.0,
        })

    def update_outcomes(self, current_price: float, now: float):
        """
        Update all pending snapshots with current price.
        Called on every trade tick.
        """
        still_pending = []
        for entry in self._pending_outcomes:
            snapshot = entry["snapshot"]
            initial = entry["initial_price"]
            created = entry["created"]

            if initial == 0:
                still_pending.append(entry)
                continue

            elapsed = now - created
            price_diff = current_price - initial
            return_bps = (price_diff / initial) * 10000

            # MFE/MAE
            if elapsed <= 30:
                entry["mfe_30s"] = max(entry["mfe_30s"], max(0, price_diff))
                entry["mae_30s"] = max(entry["mae_30s"], max(0, -price_diff))

            # Fill horizons
            all_done = True
            for horizon in self.cfg.horizons_seconds:
                if horizon in entry["measured_horizons"]:
                    continue
                if elapsed >= horizon:
                    key = f"future_return_{horizon}s"
                    if key in snapshot:
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

    def export_csv(self, path: str):
        """Export all snapshots to CSV."""
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

    def get_summary(self) -> dict:
        """Summary of watchlist captures."""
        by_type = {}
        complete = 0
        for snap in self._snapshots:
            t = snap["event_type"]
            by_type[t] = by_type.get(t, 0) + 1
            if snap["is_complete"]:
                complete += 1
        return {
            "total_snapshots": len(self._snapshots),
            "by_type": by_type,
            "complete": complete,
            "pending": len(self._pending_outcomes),
        }

    def _sample_path(self, values: list, timestamps: list,
                     event_ts: float, interval: int,
                     direction: str = "before") -> list[dict]:
        """Sample values at regular intervals."""
        if not values or not timestamps:
            return []

        samples = []
        if direction == "before":
            # Sample at -interval, -2*interval, etc. up to path_before_seconds
            for offset in range(interval, self.cfg.path_before_seconds + 1, interval):
                target_ts = event_ts - offset
                # Find closest timestamp
                best_idx = None
                best_diff = float('inf')
                for i, ts in enumerate(timestamps):
                    diff = abs(ts - target_ts)
                    if diff < best_diff:
                        best_diff = diff
                        best_idx = i
                if best_idx is not None and best_diff < interval:
                    samples.append({
                        "t": -offset,
                        "v": round(values[best_idx], 4) if isinstance(values[best_idx], (int, float)) else values[best_idx]
                    })
        return samples

    def _sample_cvd_path(self, cvd_list: list, timestamps: list,
                         event_ts: float, interval: int) -> list[dict]:
        """Sample CVD values at regular intervals."""
        if not cvd_list or not timestamps:
            return []
        # Match timestamps to CVD values
        samples = []
        for offset in range(interval, self.cfg.path_before_seconds + 1, interval):
            target_ts = event_ts - offset
            best_idx = None
            best_diff = float('inf')
            for i, ts in enumerate(timestamps):
                diff = abs(ts - target_ts)
                if diff < best_diff:
                    best_diff = diff
                    best_idx = i
            if best_idx is not None and best_diff < interval and best_idx < len(cvd_list):
                samples.append({
                    "t": -offset,
                    "v": round(cvd_list[best_idx], 4)
                })
        return samples

    @property
    def pending_count(self) -> int:
        return len(self._pending_outcomes)
