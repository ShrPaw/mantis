"""
MANTIS SPE — Event Models
Output structures for the Structural Pressure Execution module.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SPESignal:
    """Internal signal passed between SPE layers."""
    # Layer outputs
    mantis_state: str = "IDLE"                        # CASCADE, UNWIND, IDLE
    imbalance_score: float = 0.0                      # 0-100
    execution_quality: float = 0.0                    # 0-100
    risk_score: float = 0.0                           # 0-100

    # Layer 2: Pressure
    crowd_direction: str = ""                         # LONG_CROWD, SHORT_CROWD, NONE
    pressure_strength: float = 0.0                    # 0-100
    funding_z: float = 0.0                            # z-score
    oi_proxy: float = 0.0                             # OI direction proxy

    # Layer 3: Displacement
    displacement_direction: str = ""                  # UP, DOWN, NONE
    displacement_strength: float = 0.0                # 0-100
    displacement_origin: float = 0.0                  # price at displacement start
    displacement_end: float = 0.0                     # price at displacement end
    displacement_body_bps: float = 0.0                # body size in bps

    # Layer 4: Sweep
    sweep_detected: bool = False
    sweep_direction: str = ""                         # BEARISH, BULLISH
    sweep_level: float = 0.0                          # level that was swept
    sweep_reclaimed: bool = False

    # Layer 5: Trap
    trap_detected: bool = False
    trap_type: str = ""                               # LIQUIDITY_TAKEN, DIRECTION_FAIL, RAPID_REVERSAL

    # Layer 6: Execution
    spread_bps: float = 0.0
    depth_ok: bool = False
    volatility_ok: bool = False

    # Layer 7: Entry
    entry_price: float = 0.0
    entry_type: str = "limit_passive"

    # Layer 8: Exit
    stop_loss: float = 0.0
    tp_levels: list[float] = field(default_factory=list)

    # Confidence
    confidence_score: float = 0.0                     # 0-100

    # Direction
    direction: str = ""                               # LONG, SHORT

    def is_valid(self) -> bool:
        """Check if signal has minimum required fields."""
        return (
            self.direction != ""
            and self.entry_price > 0
            and self.stop_loss > 0
            and len(self.tp_levels) > 0
            and self.trap_detected
            and self.confidence_score > 0
        )


@dataclass
class SPEEvent:
    """
    Final output event: STRUCTURAL_PRESSURE_EXECUTION.
    Only emitted when ALL 8 layers pass.
    """
    event_id: str = ""
    timestamp: float = 0.0
    symbol: str = "BTC"
    exchange: str = "hyperliquid"

    # Core fields (from spec)
    direction: str = ""                               # LONG, SHORT
    mantis_state: str = ""                            # CASCADE, UNWIND
    imbalance_score: float = 0.0                      # 0-100
    execution_quality: float = 0.0                    # 0-100
    risk_score: float = 0.0                           # 0-100
    crowd_direction: str = ""                         # LONG_CROWD, SHORT_CROWD
    displacement_strength: float = 0.0                # 0-100
    trap_detected: bool = False
    entry_price: float = 0.0
    stop_loss: float = 0.0
    tp_levels: list[float] = field(default_factory=list)
    confidence_score: float = 0.0                     # 0-100

    # Extended fields
    pressure_strength: float = 0.0
    funding_z: float = 0.0
    sweep_detected: bool = False
    sweep_direction: str = ""
    spread_bps: float = 0.0
    displacement_origin: float = 0.0
    displacement_end: float = 0.0
    displacement_body_bps: float = 0.0

    # Validation
    validation_tags: list[str] = field(default_factory=list)
    explanation: str = ""

    def __post_init__(self):
        if not self.event_id:
            self.event_id = uuid.uuid4().hex[:12]
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "event_type": "structural_pressure_execution",
            "direction": self.direction,
            "mantis_state": self.mantis_state,
            "imbalance_score": round(self.imbalance_score, 2),
            "execution_quality": round(self.execution_quality, 2),
            "risk_score": round(self.risk_score, 2),
            "crowd_direction": self.crowd_direction,
            "displacement_strength": round(self.displacement_strength, 2),
            "trap_detected": self.trap_detected,
            "entry_price": round(self.entry_price, 2),
            "stop_loss": round(self.stop_loss, 2),
            "tp_levels": [round(tp, 2) for tp in self.tp_levels],
            "confidence_score": round(self.confidence_score, 2),
            "pressure_strength": round(self.pressure_strength, 2),
            "funding_z": round(self.funding_z, 4),
            "sweep_detected": self.sweep_detected,
            "sweep_direction": self.sweep_direction,
            "spread_bps": round(self.spread_bps, 2),
            "displacement_origin": round(self.displacement_origin, 2),
            "displacement_end": round(self.displacement_end, 2),
            "displacement_body_bps": round(self.displacement_body_bps, 2),
            "validation_tags": self.validation_tags,
            "explanation": self.explanation,
        }
