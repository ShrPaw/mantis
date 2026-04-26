"""
MANTIS Event Engine — Anti-Spam / Deduplication / Merging
Prevents flooding with repeated events in the same area.
Merges repeated detections into stronger events.
"""

import time
from collections import deque
from typing import Optional

from .config import DedupConfig
from .models import MicrostructureEvent


class EventDeduplicator:
    """Prevents event spam through cooldown, clustering, and merging."""

    def __init__(self, config: DedupConfig):
        self.cfg = config
        # Recent events by type for cooldown
        self._last_fire: dict[str, float] = {}
        # Recent events for clustering
        self._recent: deque[MicrostructureEvent] = deque(maxlen=100)
        # Per-minute counter
        self._minute_events: deque[float] = deque(maxlen=100)

    def should_fire(self, event: MicrostructureEvent) -> bool:
        """Check if event should fire (not a duplicate/spam)."""
        now = event.timestamp
        key = f"{event.event_type}:{event.side}"

        # Cooldown per event type+side
        last = self._last_fire.get(key, 0)
        if now - last < self.cfg.cooldown_seconds:
            return False

        # Rate limit per minute
        minute_cutoff = now - 60
        while self._minute_events and self._minute_events[0] < minute_cutoff:
            self._minute_events.popleft()
        if len(self._minute_events) >= self.cfg.max_events_per_minute:
            return False

        # Price cluster check — is there a recent event of same type near same price?
        merge_target = self._find_merge_target(event)
        if merge_target is not None:
            self._merge_event(merge_target, event)
            return False  # merged into existing, don't fire new

        # Passed all checks
        self._last_fire[key] = now
        self._minute_events.append(now)
        self._recent.append(event)
        return True

    def _find_merge_target(self, event: MicrostructureEvent) -> Optional[MicrostructureEvent]:
        """Find a recent event that should be merged with this one."""
        cutoff = event.timestamp - self.cfg.merge_window_seconds
        for existing in reversed(self._recent):
            if existing.timestamp < cutoff:
                break
            if existing.event_type != event.event_type:
                continue
            if existing.side != event.side:
                continue
            # Check price proximity
            if existing.price == 0 or event.price == 0:
                continue
            price_diff_bps = abs(existing.price - event.price) / existing.price * 10000
            if price_diff_bps <= self.cfg.price_cluster_bps:
                return existing
        return None

    def _merge_event(self, target: MicrostructureEvent, new: MicrostructureEvent):
        """Merge new event into existing target (update strength, count, etc)."""
        # Boost strength by averaging (stronger signal from repeated detection)
        target.scores.strength_score = (
            target.scores.strength_score * 0.7 + new.scores.strength_score * 0.3
        )
        target.scores.confidence_score = (
            target.scores.confidence_score * 0.7 + new.scores.confidence_score * 0.3
        )
        # Composite recompute
        target.scores.composite_score = (
            target.scores.strength_score * target.scores.confidence_score *
            (1.0 - target.scores.noise_score * 0.5)
        )
        # Track merge count in validation tags
        merge_count = sum(1 for t in target.validation_tags if t.startswith("merged:")) + 1
        target.validation_tags = [t for t in target.validation_tags if not t.startswith("merged:")]
        target.validation_tags.append(f"merged:{merge_count}")
        # Update explanation
        target.explanation += f" [Merged x{merge_count} — repeated at similar price]"

    def cleanup(self, now: float):
        """Remove stale entries."""
        cutoff = now - 300
        while self._recent and self._recent[0].timestamp < cutoff:
            self._recent.popleft()
