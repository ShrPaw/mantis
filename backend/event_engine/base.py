"""
MANTIS Event Engine — Base Detector Interface
Every detector must implement update() and return zero or more events.
"""

from abc import ABC, abstractmethod
from typing import Optional

from .models import MicrostructureEvent
from .context import EngineContext


class BaseEventDetector(ABC):
    """Abstract base class for all event detectors."""

    def __init__(self, context: EngineContext):
        self.ctx = context

    @abstractmethod
    def update(self, trade_price: float, trade_qty: float,
               trade_delta: float, timestamp: float) -> list[MicrostructureEvent]:
        """
        Called on every trade tick.
        Returns list of detected events (may be empty).
        Must NOT use any future data — only data up to `timestamp`.
        """
        pass

    @property
    @abstractmethod
    def event_type(self) -> str:
        """Return the event type string this detector produces."""
        pass

    def reset(self):
        """Optional: reset internal state."""
        pass
