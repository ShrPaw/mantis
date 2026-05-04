"""
MANTIS Event Engine — Event Logger
Logs every event to JSONL (raw) and CSV (research).
Buffered writes, flush on interval or buffer full.
"""

import csv
import json
import os
import time
import threading
from collections import deque
from pathlib import Path

from app.event_engine.config import LoggerConfig
from app.event_engine.models import MicrostructureEvent


class EventLogger:
    """Logs events to disk in JSONL and CSV formats."""

    # CSV columns for research dataset
    CSV_COLUMNS = [
        "event_id", "timestamp", "symbol", "exchange", "event_type", "side",
        "price", "strength_score", "confidence_score", "noise_score", "composite_score",
        "explanation", "is_active", "regime",
        # Forward outcomes (filled later)
        "future_return_10s", "future_return_30s", "future_return_60s",
        "future_return_120s", "future_return_300s",
        "max_favorable_excursion_30s", "max_adverse_excursion_30s",
        "max_favorable_excursion_120s", "max_adverse_excursion_120s",
        "hit_tp_0_10pct", "hit_tp_0_20pct", "hit_sl_0_10pct", "hit_sl_0_20pct",
        "time_to_max_favorable", "time_to_max_adverse",
        # Costs
        "net_return_60s_2bps", "net_return_60s_4bps", "net_return_60s_6bps",
    ]

    def __init__(self, config: LoggerConfig):
        self.cfg = config
        self._buffer: deque[MicrostructureEvent] = deque(maxlen=config.max_buffer_size)
        self._last_flush: float = time.time()
        self._lock = threading.Lock()
        self._ensure_dirs()
        self._init_csv()

    def _ensure_dirs(self):
        for path in [self.cfg.jsonl_path, self.cfg.csv_path]:
            Path(path).parent.mkdir(parents=True, exist_ok=True)

    def _init_csv(self):
        """Write CSV header if file doesn't exist."""
        if not os.path.exists(self.cfg.csv_path):
            with open(self.cfg.csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_COLUMNS)

    def log(self, event: MicrostructureEvent):
        """Buffer an event for writing."""
        with self._lock:
            self._buffer.append(event)
            if (len(self._buffer) >= self.cfg.max_buffer_size or
                    time.time() - self._last_flush >= self.cfg.flush_interval_seconds):
                self._flush()

    def flush(self):
        """Force flush all buffered events."""
        with self._lock:
            self._flush()

    def _flush(self):
        """Write buffered events to disk."""
        if not self._buffer:
            return

        events = list(self._buffer)
        self._buffer.clear()
        self._last_flush = time.time()

        # Write JSONL
        try:
            with open(self.cfg.jsonl_path, "a") as f:
                for evt in events:
                    f.write(json.dumps(evt.to_dict()) + "\n")
        except Exception as e:
            print(f"[EventLogger] JSONL write error: {e}")

        # Write CSV
        try:
            with open(self.cfg.csv_path, "a", newline="") as f:
                writer = csv.writer(f)
                for evt in events:
                    writer.writerow(self._event_to_csv_row(evt))
        except Exception as e:
            print(f"[EventLogger] CSV write error: {e}")

    def _event_to_csv_row(self, evt: MicrostructureEvent) -> list:
        """Convert event to flat CSV row."""
        fwd = evt.forward
        scores = evt.scores
        # Net returns after costs
        net_2 = (fwd.future_return_60s or 0) - 4 if fwd.future_return_60s is not None else None
        net_4 = (fwd.future_return_60s or 0) - 8 if fwd.future_return_60s is not None else None
        net_6 = (fwd.future_return_60s or 0) - 12 if fwd.future_return_60s is not None else None

        return [
            evt.event_id, evt.timestamp, evt.symbol, evt.exchange,
            evt.event_type, evt.side, evt.price,
            scores.strength_score, scores.confidence_score, scores.noise_score,
            scores.composite_score, evt.explanation, evt.is_active,
            evt.context_metrics.get("regime", ""),
            fwd.future_return_10s, fwd.future_return_30s, fwd.future_return_60s,
            fwd.future_return_120s, fwd.future_return_300s,
            fwd.max_favorable_excursion_30s, fwd.max_adverse_excursion_30s,
            fwd.max_favorable_excursion_120s, fwd.max_adverse_excursion_120s,
            fwd.hit_tp_0_10pct, fwd.hit_tp_0_20pct,
            fwd.hit_sl_0_10pct, fwd.hit_sl_0_20pct,
            fwd.time_to_max_favorable, fwd.time_to_max_adverse,
            net_2, net_4, net_6,
        ]

    @property
    def buffered_count(self) -> int:
        return len(self._buffer)
