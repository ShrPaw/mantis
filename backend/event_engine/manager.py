"""
MANTIS Event Engine — Event Manager
Orchestrates all detectors, scoring, dedup, logging, and outcome tracking.
Single entry point: on_trade(), on_book(), on_large_trade().

SHADOW MODE — Blacklist/Watchlist:
  - Blacklisted event types: sell_exhaustion, sell_imbalance, sell_cluster
  - Watchlisted event types: sell_absorption, down_break, up_break
  - ALL events flow through the original live pipeline unchanged.
  - Blacklist/watchlist tags are SHADOW METADATA ONLY (diagnostic).
  - No score capping, no filtering, no blocking in production.
  - Candidate snapshots captured in parallel for validation.

SPE MODULE — Observation-Only Integration:
  - SPE (Structural Pressure Execution) is a passive context detector.
  - When SPE_OBSERVATION_ONLY=true (default), SPE emits events/logs only.
  - SPE NEVER places orders, NEVER calls trading endpoints.
  - SPE events stored separately from normal MANTIS events.
  - Feature-flagged via SPE_ENABLED and SPE_OBSERVATION_ONLY env vars.
"""

import csv
import json
import logging
import os
import time

from .config import EventEngineConfig
from .context import EngineContext
from .scoring import ScoringEngine
from .dedup import EventDeduplicator
from .event_logger import EventLogger
from .outcome_tracker import OutcomeTracker
from .models import MicrostructureEvent
from .detectors import ALL_DETECTORS
from .blacklist_watchlist import BlacklistWatchlistManager

logger = logging.getLogger(__name__)


class EventManager:
    """
    Central orchestrator for the MANTIS Event Engine.
    Receives live data, runs detectors, scores/deduplicates/logs events,
    and tracks forward outcomes.
    """

    def __init__(self, config: EventEngineConfig | None = None):
        self.config = config or EventEngineConfig()
        self.ctx = EngineContext(self.config.rolling_buffer_seconds)
        self.ctx.config = self.config  # attach config to context

        self.scoring = ScoringEngine(self.config)
        self.ctx.scoring = self.scoring  # attach scoring to context

        self.dedup = EventDeduplicator(self.config.dedup)
        self.logger = EventLogger(self.config.logger)
        self.outcomes = OutcomeTracker(self.config.outcome)

        # Initialize all detectors
        self._detectors = [cls(self.ctx) for cls in ALL_DETECTORS]

        # Blacklist / Watchlist enforcement
        self.bw_manager = BlacklistWatchlistManager(self.config, self.ctx)

        # Event history for frontend
        self._event_history: list[MicrostructureEvent] = []
        self._max_history = self.config.max_event_history

        # Stats
        self._events_fired: int = 0
        self._events_deduped: int = 0
        self._events_blacklisted: int = 0
        self._events_watchlisted: int = 0

        # ── SPE Module (feature-flagged, observation-only) ──
        self.spe_enabled = os.environ.get("SPE_ENABLED", "true").lower() in ("true", "1", "yes")
        self.spe_observation_only = os.environ.get("SPE_OBSERVATION_ONLY", "true").lower() in ("true", "1", "yes")
        self.spe = None
        self._spe_event_history: list[dict] = []
        self._spe_max_history = 200
        self._spe_evaluations: int = 0
        self._spe_emitted: int = 0
        self._spe_suppressed_dupes: int = 0
        self._spe_cooldown_hits: int = 0

        if self.spe_enabled:
            try:
                from .spe import SPEOrchestrator
                self.spe = SPEOrchestrator(self.ctx)
                logger.info("SPE Module: ENABLED (observation_only=%s)", self.spe_observation_only)
                self._ensure_spe_dirs()
            except Exception as e:
                logger.warning(f"SPE Module: FAILED TO LOAD — {e}")
                self.spe = None
        else:
            logger.info("SPE Module: DISABLED (SPE_ENABLED=false)")

        logger.info(f"EventManager initialized with {len(self._detectors)} detectors")
        logger.info(f"Blacklist: {self.config.blacklist.event_types}")
        logger.info(f"Watchlist: {self.config.watchlist.event_types}")

    def on_trade(self, price: float, qty: float, delta: float, timestamp: float) -> list[dict]:
        """
        Main entry point: called on every trade tick.
        Returns list of new events as dicts (for WebSocket broadcast).
        """
        # Update shared context
        self.ctx.on_trade(price, qty, delta, timestamp)

        # Update outcome tracker
        self.outcomes.update(price, timestamp)

        # Update watchlist outcomes
        self.bw_manager.update_outcomes(price, timestamp)

        # Run all detectors
        all_events: list[MicrostructureEvent] = []
        for detector in self._detectors:
            try:
                events = detector.update(price, qty, delta, timestamp)
                all_events.extend(events)
            except Exception as e:
                logger.error(f"Detector {detector.event_type} error: {e}")

        # Score, dedup, log — all events flow through unchanged
        new_events = []
        for event in all_events:
            # ── SHADOW METADATA (diagnostic only, does NOT affect pipeline) ──
            if self.bw_manager.check_blacklisted(event):
                event.event_type_blacklisted = True
                event.blacklist_reason = f"blacklisted:{event.event_type}:{event.side}"
                event.shadow_tradeable_allowed = False
                self.bw_manager.log_shadow_blacklisted(event)
                self._events_blacklisted += 1

            if self.bw_manager.check_watchlisted(event):
                event.event_type_watchlisted = True
                event.watchlist_reason = f"watchlisted:{event.event_type}:{event.side}"
                self.bw_manager.capture_snapshot(event)
                self._events_watchlisted += 1

            # Dedup check
            if not self.dedup.should_fire(event):
                self._events_deduped += 1
                continue

            # Register for outcome tracking
            self.outcomes.register(event, price)

            # Log to disk
            self.logger.log(event)

            # Store in history
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history:]

            self._events_fired += 1
            new_events.append(event)

        # ── SPE Hook (observation-only, non-breaking) ──
        if self.spe is not None:
            try:
                spe_events = self.spe.on_trade(price, qty, delta, timestamp)
                self._spe_evaluations += 1

                for evt_dict in spe_events:
                    # Mark as observation-only
                    evt_dict["observation_only"] = True

                    # Dedup check against recent SPE events
                    if self._is_spe_duplicate(evt_dict):
                        self._spe_suppressed_dupes += 1
                        continue

                    self._spe_emitted += 1
                    self._spe_event_history.append(evt_dict)
                    if len(self._spe_event_history) > self._spe_max_history:
                        self._spe_event_history = self._spe_event_history[-self._spe_max_history:]

                    # Log SPE event to separate files
                    self._log_spe_event(evt_dict)

                    # Wrap for broadcast
                    new_events.append(evt_dict)

            except Exception as e:
                logger.debug(f"SPE error (non-fatal): {e}")

        # Periodic cleanup
        if self._events_fired % 100 == 0:
            self.dedup.cleanup(timestamp)
            self.logger.flush()
            # Export shadow snapshots periodically (parallel logging)
            self.bw_manager.export_watchlist_csv(
                self.config.watchlist.snapshot_path
            )
            self.bw_manager.export_blacklist_report_csv(
                self.config.watchlist.snapshot_path.replace("candidate_watchlist", "blacklist_watchlist_report")
            )
            # Flush SPE metrics periodically (even when no events fire)
            if self.spe is not None:
                self.flush_spe_metrics()

        return [e.to_dict() if hasattr(e, 'to_dict') else e for e in new_events]

    def on_book(self, bids: list[tuple[float, float]], asks: list[tuple[float, float]]):
        """Called on every order book update."""
        self.ctx.on_book(bids, asks)

    def on_large_trade(self, price: float, qty: float, side: str, timestamp: float):
        """Called when a large trade is detected by the metrics engine."""
        self.ctx.on_large_trade(price, qty, side, timestamp)

    def on_session_update(self, vwap: float, session_high: float, session_low: float):
        """Update session-level stats."""
        self.ctx.session.vwap = vwap
        self.ctx.session.session_high = session_high
        if session_low > 0:
            self.ctx.session.session_low = session_low

    # --- Query API ---

    def get_events(self, limit: int = 50) -> list[dict]:
        """Get recent events as dicts."""
        return [e.to_dict() for e in self._event_history[-limit:]]

    def get_event_stats(self) -> dict:
        """Get event statistics."""
        events = self._event_history
        if not events:
            return {
                "total": 0, "by_type": {}, "by_side": {},
                "avg_strength": 0, "avg_confidence": 0,
                "measured_count": 0, "unmeasured_count": 0,
                "fired": self._events_fired, "deduped": self._events_deduped,
                "blacklisted": self._events_blacklisted,
                "watchlisted": self._events_watchlisted,
                "pending_outcomes": self.outcomes.pending_count,
                "blacklist_detail": self.bw_manager.export_blacklist_stats(),
                "watchlist_summary": self.bw_manager.get_summary()["watchlist"],
            }

        by_type = {}
        by_side = {}
        strengths = []
        confidences = []
        measured = 0

        for e in events:
            by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
            by_side[e.side] = by_side.get(e.side, 0) + 1
            strengths.append(e.scores.strength_score)
            confidences.append(e.scores.confidence_score)
            if e.forward.is_complete:
                measured += 1

        result = {
            "total": len(events),
            "by_type": by_type,
            "by_side": by_side,
            "avg_strength": round(sum(strengths) / len(strengths), 3) if strengths else 0,
            "avg_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0,
            "measured_count": measured,
            "unmeasured_count": len(events) - measured,
            "fired": self._events_fired,
            "deduped": self._events_deduped,
            "blacklisted": self._events_blacklisted,
            "watchlisted": self._events_watchlisted,
            "pending_outcomes": self.outcomes.pending_count,
            "blacklist_detail": self.bw_manager.export_blacklist_stats(),
            "watchlist_summary": self.bw_manager.get_summary()["watchlist"],
        }

        # Add SPE stats if active
        if self.spe is not None:
            result["spe"] = self.spe.get_stats()
            result["spe"]["observation_only"] = self.spe_observation_only

        return result

    def get_active_events(self, limit: int = 20) -> list[dict]:
        """Get events that are still active (outcomes pending)."""
        active = [e for e in self._event_history if e.is_active]
        return [e.to_dict() for e in active[-limit:]]

    # --- SPE Helpers ---

    def _ensure_spe_dirs(self):
        """Create SPE event/metrics directories."""
        os.makedirs("data/events", exist_ok=True)
        os.makedirs("data/metrics", exist_ok=True)

    def _is_spe_duplicate(self, evt_dict: dict) -> bool:
        """Check if SPE event is a duplicate of a recent event."""
        if not self._spe_event_history:
            return False

        recent = self._spe_event_history[-5:]
        for old in recent:
            # Same direction + same state within cooldown = duplicate
            if (old.get("direction") == evt_dict.get("direction") and
                old.get("mantis_state") == evt_dict.get("mantis_state") and
                abs(old.get("timestamp", 0) - evt_dict.get("timestamp", 0)) < 300):
                return True
        return False

    def _log_spe_event(self, evt_dict: dict):
        """Log SPE event to separate JSONL and CSV files."""
        # JSONL
        try:
            with open("data/events/spe_events.jsonl", "a") as f:
                f.write(json.dumps(evt_dict) + "\n")
        except Exception as e:
            logger.debug(f"SPE JSONL write error: {e}")

        # CSV
        try:
            csv_path = "data/events/spe_events.csv"
            write_header = not os.path.exists(csv_path)
            with open(csv_path, "a", newline="") as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow([
                        "timestamp", "symbol", "direction_context", "mantis_state",
                        "imbalance_score", "execution_quality", "risk_score",
                        "crowd_direction", "pressure_strength", "displacement_direction",
                        "displacement_strength", "sweep_detected", "trap_detected",
                        "execution_filter_passed", "entry_zone", "invalidation_level",
                        "tp_levels", "confidence_score", "layer_pass_status",
                        "observation_only",
                    ])
                writer.writerow([
                    evt_dict.get("timestamp", ""),
                    evt_dict.get("symbol", "BTC"),
                    evt_dict.get("direction", ""),
                    evt_dict.get("mantis_state", ""),
                    evt_dict.get("imbalance_score", 0),
                    evt_dict.get("execution_quality", 0),
                    evt_dict.get("risk_score", 0),
                    evt_dict.get("crowd_direction", ""),
                    evt_dict.get("pressure_strength", 0),
                    evt_dict.get("displacement_direction", ""),
                    evt_dict.get("displacement_strength", 0),
                    evt_dict.get("sweep_detected", False),
                    evt_dict.get("trap_detected", False),
                    evt_dict.get("execution_quality", 0) >= 70,
                    evt_dict.get("entry_price", 0),
                    evt_dict.get("stop_loss", 0),
                    "|".join(str(tp) for tp in evt_dict.get("tp_levels", [])),
                    evt_dict.get("confidence_score", 0),
                    "FULL_8L_PASS",
                    True,
                ])
        except Exception as e:
            logger.debug(f"SPE CSV write error: {e}")

    def get_spe_events(self, limit: int = 50) -> list[dict]:
        """Get recent SPE events."""
        return self._spe_event_history[-limit:]

    def get_spe_layer_stats(self) -> dict:
        """Get SPE layer pass/fail/not_evaluated statistics from orchestrator."""
        if self.spe is None:
            return {}

        metrics = self.spe.get_layer_metrics()
        return {
            "layer_pass_fail": metrics["layer_counts"],
            "raw_evaluations": self._spe_evaluations,
            "full_8_layer_passes": metrics["full_8_layer_passes"],
            "emitted_events": self._spe_emitted,
            "suppressed_duplicates": self._spe_suppressed_dupes,
            "cooldown_hits": self._spe_cooldown_hits,
            "current_state": metrics["current_state"],
            "observation_only": self.spe_observation_only,
        }

    def flush_spe_metrics(self):
        """Flush SPE metrics to disk. Always persists, even when no events fire."""
        if self.spe is None:
            return
        try:
            layer_metrics = self.spe.get_layer_metrics()
            metrics = {
                "timestamp": time.time(),
                "spe_enabled": True,
                "observation_only": self.spe_observation_only,
                "current_state": layer_metrics["current_state"],
                "raw_evaluations": self._spe_evaluations,
                "layer_counts": layer_metrics["layer_counts"],
                "full_8_layer_passes": layer_metrics["full_8_layer_passes"],
                "emitted_events": self._spe_emitted,
                "suppressed_duplicates": self._spe_suppressed_dupes,
                "cooldown_hits": self._spe_cooldown_hits,
            }
            os.makedirs("data/metrics", exist_ok=True)
            with open("data/metrics/spe_metrics.json", "w") as f:
                json.dump(metrics, f, indent=2)
        except Exception as e:
            logger.debug(f"SPE metrics flush error: {e}")

    def flush(self):
        """Force flush logger and export shadow snapshots."""
        self.logger.flush()
        self.bw_manager.export_watchlist_csv(
            self.config.watchlist.snapshot_path
        )
        self.bw_manager.export_blacklist_report_csv(
            self.config.watchlist.snapshot_path.replace("candidate_watchlist", "blacklist_watchlist_report")
        )
        # Flush SPE metrics
        if self.spe is not None:
            self.flush_spe_metrics()
