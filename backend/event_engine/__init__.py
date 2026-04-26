"""
MANTIS Event Engine — Real-time structural event detection for crypto microstructure.

Usage:
    from event_engine import EventManager

    manager = EventManager()

    # On every trade:
    events = manager.on_trade(price, qty, delta, timestamp)

    # On book update:
    manager.on_book(bids, asks)

    # On large trade:
    manager.on_large_trade(price, qty, side, timestamp)

    # Query:
    recent = manager.get_events(limit=50)
    stats = manager.get_event_stats()
"""

from .manager import EventManager
from .config import EventEngineConfig
from .models import (
    MicrostructureEvent,
    AbsorptionEvent,
    ExhaustionEvent,
    LiquiditySweepEvent,
    DeltaDivergenceEvent,
    ImbalanceEvent,
    LargeTradeClusterEvent,
    RangeBreakEvent,
    VWAPReactionEvent,
    ForwardOutcome,
    ScoreBreakdown,
)

__all__ = [
    "EventManager",
    "EventEngineConfig",
    "MicrostructureEvent",
    "AbsorptionEvent",
    "ExhaustionEvent",
    "LiquiditySweepEvent",
    "DeltaDivergenceEvent",
    "ImbalanceEvent",
    "LargeTradeClusterEvent",
    "RangeBreakEvent",
    "VWAPReactionEvent",
    "ForwardOutcome",
    "ScoreBreakdown",
]
