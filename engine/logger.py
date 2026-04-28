"""MANTIS Execution Engine — Event Logger.

Persists events to:
- JSONL for streaming reads
- CSV for analysis
- JSON snapshot for dashboard
"""

from __future__ import annotations

import csv
import json
import logging
import os
import time
from dataclasses import asdict
from pathlib import Path

from engine.models import EngineEvent, Alert

logger = logging.getLogger("mantis.logger")


class EventLogger:
    """Persists engine events to disk."""

    def __init__(self, config: dict):
        data_cfg = config.get("data", {})
        self._events_dir = Path(data_cfg.get("events_dir", "data/events"))
        self._metrics_dir = Path(data_cfg.get("metrics_dir", "data/metrics"))
        self._events_jsonl = Path(data_cfg.get("events_jsonl", "data/events/mantis_events.jsonl"))
        self._events_csv = Path(data_cfg.get("events_csv", "data/events/mantis_events.csv"))
        self._metrics_json = Path(data_cfg.get("metrics_json", "data/metrics/realtime_metrics.json"))
        self._save_interval = data_cfg.get("metrics_save_interval_seconds", 5)
        self._last_metrics_save = 0.0

        # Ensure directories
        self._events_dir.mkdir(parents=True, exist_ok=True)
        self._metrics_dir.mkdir(parents=True, exist_ok=True)

        # Init CSV with headers if not exists
        if not self._events_csv.exists():
            self._init_csv()

    def _init_csv(self):
        """Initialize CSV file with headers."""
        headers = [
            "timestamp", "market_state", "crowd_side", "crowd_severity",
            "cascade_direction", "cascade_intensity",
            "unwind_side", "unwind_maturity",
            "exhaustion_side", "exhaustion_confidence",
            "imbalance_score", "execution_quality_score", "risk_score",
            "trade_environment_score", "execution_mode",
            "funding_z", "oi_z", "liq_notional_z", "delta_z",
            "spread_bps", "alert_tier", "alert_reason",
        ]
        with open(self._events_csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

    def log_event(self, event: EngineEvent):
        """Log an engine event to JSONL and CSV."""
        # JSONL
        try:
            event_dict = self._serialize_event(event)
            with open(self._events_jsonl, "a") as f:
                f.write(json.dumps(event_dict) + "\n")
        except Exception as e:
            logger.error(f"Failed to write JSONL: {e}")

        # CSV
        try:
            self._append_csv(event)
        except Exception as e:
            logger.error(f"Failed to write CSV: {e}")

    def save_metrics_snapshot(self, event: EngineEvent):
        """Save current metrics as JSON snapshot for dashboard."""
        now = time.time()
        if now - self._last_metrics_save < self._save_interval:
            return
        self._last_metrics_save = now

        try:
            snapshot = {
                "timestamp": event.timestamp,
                "market_state": event.market_state.value,
                "scores": {
                    "imbalance": event.scores.imbalance,
                    "execution_quality": event.scores.execution_quality,
                    "risk": event.scores.risk,
                    "trade_environment": event.scores.trade_environment,
                },
                "execution_mode": event.execution_mode.value,
                "funding": asdict(event.funding),
                "oi": asdict(event.oi),
                "liquidation": asdict(event.liquidation),
                "trade_flow": asdict(event.trade_flow),
                "order_book": asdict(event.order_book),
                "crowd": asdict(event.crowd),
                "cascade": asdict(event.cascade),
                "unwind": asdict(event.unwind),
                "exhaustion": asdict(event.exhaustion),
            }
            with open(self._metrics_json, "w") as f:
                json.dump(snapshot, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metrics snapshot: {e}")

    def log_alert(self, alert: Alert):
        """Log an alert separately for alert history."""
        alerts_file = self._events_dir / "alerts.jsonl"
        try:
            with open(alerts_file, "a") as f:
                f.write(json.dumps(alert.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to write alert: {e}")

    def _serialize_event(self, event: EngineEvent) -> dict:
        """Serialize event to JSON-safe dict."""
        d = asdict(event)
        d["market_state"] = event.market_state.value
        d["execution_mode"] = event.execution_mode.value
        # Flatten scores for readability
        d["scores_flat"] = {
            "imbalance": event.scores.imbalance,
            "execution_quality": event.scores.execution_quality,
            "risk": event.scores.risk,
            "trade_environment": event.scores.trade_environment,
        }
        return d

    def _append_csv(self, event: EngineEvent):
        """Append event row to CSV."""
        row = [
            f"{event.timestamp:.3f}",
            event.market_state.value,
            event.crowd.crowd_side,
            f"{event.crowd.severity:.1f}",
            event.cascade.cascade_direction,
            f"{event.cascade.intensity:.1f}",
            event.unwind.unwind_side,
            event.unwind.maturity,
            event.exhaustion.side,
            f"{event.exhaustion.confidence:.1f}",
            f"{event.scores.imbalance:.1f}",
            f"{event.scores.execution_quality:.1f}",
            f"{event.scores.risk:.1f}",
            f"{event.scores.trade_environment:.1f}",
            event.execution_mode.value,
            f"{event.funding.z_score:.2f}",
            f"{event.oi.z_score:.2f}",
            f"{event.liquidation.notional_z:.2f}",
            f"{event.trade_flow.delta_z:.2f}",
            f"{event.order_book.spread_bps:.2f}",
            event.alert.tier if event.alert else "",
            event.alert.reason if event.alert else "",
        ]
        with open(self._events_csv, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(row)
