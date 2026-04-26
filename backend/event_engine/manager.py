"""
MANTIS Event Engine — Event Manager
Orchestrates all detectors, scoring, dedup, logging, and outcome tracking.
Single entry point: on_trade(), on_book(), on_large_trade().
"""

import logging
import time

from .config import EventEngineConfig
from .context import EngineContext
from .scoring import ScoringEngine
from .dedup import EventDeduplicator
from .event_logger import EventLogger
from .outcome_tracker import OutcomeTracker
from .models import MicrostructureEvent
from .detectors import ALL_DETECTORS

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

        # Event history for frontend
        self._event_history: list[MicrostructureEvent] = []
        self._max_history = self.config.max_event_history

        # Stats
        self._events_fired: int = 0
        self._events_deduped: int = 0

        logger.info(f"EventManager initialized with {len(self._detectors)} detectors")

    def on_trade(self, price: float, qty: float, delta: float, timestamp: float) -> list[dict]:
        """
        Main entry point: called on every trade tick.
        Returns list of new events as dicts (for WebSocket broadcast).
        """
        # Update shared context
        self.ctx.on_trade(price, qty, delta, timestamp)

        # Update outcome tracker
        self.outcomes.update(price, timestamp)

        # Run all detectors
        all_events: list[MicrostructureEvent] = []
        for detector in self._detectors:
            try:
                events = detector.update(price, qty, delta, timestamp)
                all_events.extend(events)
            except Exception as e:
                logger.error(f"Detector {detector.event_type} error: {e}")

        # Score, dedup, log
        new_events = []
        for event in all_events:
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

        # Periodic cleanup
        if self._events_fired % 100 == 0:
            self.dedup.cleanup(timestamp)
            self.logger.flush()

        return [e.to_dict() for e in new_events]

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
                "pending_outcomes": self.outcomes.pending_count,
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

        return {
            "total": len(events),
            "by_type": by_type,
            "by_side": by_side,
            "avg_strength": round(sum(strengths) / len(strengths), 3) if strengths else 0,
            "avg_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0,
            "measured_count": measured,
            "unmeasured_count": len(events) - measured,
            "fired": self._events_fired,
            "deduped": self._events_deduped,
            "pending_outcomes": self.outcomes.pending_count,
        }

    def get_active_events(self, limit: int = 20) -> list[dict]:
        """Get events that are still active (outcomes pending)."""
        active = [e for e in self._event_history if e.is_active]
        return [e.to_dict() for e in active[-limit:]]

    def flush(self):
        """Force flush logger."""
        self.logger.flush()
