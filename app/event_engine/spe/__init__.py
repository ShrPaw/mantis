"""
MANTIS SPE — Structural Pressure Execution Module

Selective execution framework that detects forced positioning and structural imbalance.
NOT a strategy. NOT a signal generator. A high-integrity execution filter.

8-Layer Pipeline:
  L1  Context        — CASCADE/UNWIND state gate
  L2  Pressure       — Crowd positioning imbalance (funding proxy via OI + delta skew)
  L3  Displacement   — Forced move detection (body size, bps threshold, continuation)
  L4  Sweep          — Structural sweep / CRT reinterpretation
  L5  Trap           — Confirmation: opposite liquidity taken, failure to continue, reversal
  L6  Exec Filter    — Spread, depth, volatility quality gate
  L7  Entry          — Passive limit at 30–50% retrace
  L8  Exit           — TP at nearest liquidity, SL beyond displacement origin

All layers must pass for a STRUCTURAL_PRESSURE_EXECUTION event to emit.

Usage:
    from event_engine.spe import SPEOrchestrator

    orchestrator = SPEOrchestrator(ctx)

    # On every trade tick:
    events = orchestrator.on_trade(price, qty, delta, timestamp)

    # On book update:
    orchestrator.on_book(bids, asks)
"""

from app.event_engine.spe.orchestrator import SPEOrchestrator
from app.event_engine.spe.config import SPEConfig
from app.event_engine.spe.models import SPEEvent, SPESignal

__all__ = [
    "SPEOrchestrator",
    "SPEConfig",
    "SPEEvent",
    "SPESignal",
]
