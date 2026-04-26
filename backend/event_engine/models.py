"""
MANTIS Event Engine — Event Models
Strict typed models for all 8 event types.
Every event is timestamped BEFORE outcome is known (no lookahead bias).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# Forward Outcome — filled ONLY after horizons pass
# ============================================================

@dataclass
class ForwardOutcome:
    """
    Measured after event fires. At creation time, all fields are None.
    Filled by OutcomeTracker after enough time passes.
    No lookahead bias.
    """
    future_return_10s: Optional[float] = None
    future_return_30s: Optional[float] = None
    future_return_60s: Optional[float] = None
    future_return_120s: Optional[float] = None
    future_return_300s: Optional[float] = None
    max_favorable_excursion_30s: Optional[float] = None
    max_adverse_excursion_30s: Optional[float] = None
    max_favorable_excursion_120s: Optional[float] = None
    max_adverse_excursion_120s: Optional[float] = None
    hit_tp_0_10pct: Optional[bool] = None
    hit_tp_0_20pct: Optional[bool] = None
    hit_sl_0_10pct: Optional[bool] = None
    hit_sl_0_20pct: Optional[bool] = None
    time_to_max_favorable: Optional[float] = None
    time_to_max_adverse: Optional[float] = None
    is_complete: bool = False

    def to_dict(self) -> dict:
        return {
            "future_return_10s": _r(self.future_return_10s),
            "future_return_30s": _r(self.future_return_30s),
            "future_return_60s": _r(self.future_return_60s),
            "future_return_120s": _r(self.future_return_120s),
            "future_return_300s": _r(self.future_return_300s),
            "max_favorable_excursion_30s": _r(self.max_favorable_excursion_30s),
            "max_adverse_excursion_30s": _r(self.max_adverse_excursion_30s),
            "max_favorable_excursion_120s": _r(self.max_favorable_excursion_120s),
            "max_adverse_excursion_120s": _r(self.max_adverse_excursion_120s),
            "hit_tp_0_10pct": self.hit_tp_0_10pct,
            "hit_tp_0_20pct": self.hit_tp_0_20pct,
            "hit_sl_0_10pct": self.hit_sl_0_10pct,
            "hit_sl_0_20pct": self.hit_sl_0_20pct,
            "time_to_max_favorable": _r(self.time_to_max_favorable),
            "time_to_max_adverse": _r(self.time_to_max_adverse),
            "is_complete": self.is_complete,
        }


# ============================================================
# Scoring Breakdown — explainable, not black-box
# ============================================================

@dataclass
class ScoreBreakdown:
    """Transparent scoring components. Every number is explainable."""
    strength_components: dict = field(default_factory=dict)
    confidence_components: dict = field(default_factory=dict)
    noise_components: dict = field(default_factory=dict)
    regime_score: float = 0.0

    strength_score: float = 0.0       # 0-1: how structurally strong
    confidence_score: float = 0.0     # 0-1: quality based on context
    noise_score: float = 0.0          # 0-1: probability of being meaningless
    composite_score: float = 0.0      # final usable score

    def to_dict(self) -> dict:
        return {
            "strength_components": {k: round(v, 4) for k, v in self.strength_components.items()},
            "confidence_components": {k: round(v, 4) for k, v in self.confidence_components.items()},
            "noise_components": {k: round(v, 4) for k, v in self.noise_components.items()},
            "regime_score": round(self.regime_score, 4),
            "strength_score": round(self.strength_score, 4),
            "confidence_score": round(self.confidence_score, 4),
            "noise_score": round(self.noise_score, 4),
            "composite_score": round(self.composite_score, 4),
        }


# ============================================================
# Base Event — all events inherit from this
# ============================================================

@dataclass
class MicrostructureEvent:
    """Base event model. Every event has these fields."""
    event_id: str = ""
    timestamp: float = 0.0
    symbol: str = "BTC"
    exchange: str = "hyperliquid"
    event_type: str = ""
    side: str = ""
    price: float = 0.0
    scores: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    raw_metrics: dict = field(default_factory=dict)
    context_metrics: dict = field(default_factory=dict)
    forward: ForwardOutcome = field(default_factory=ForwardOutcome)
    validation_tags: list[str] = field(default_factory=list)
    explanation: str = ""
    is_active: bool = True
    merged_into: Optional[str] = None  # event_id if merged

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
            "event_type": self.event_type,
            "side": self.side,
            "price": round(self.price, 2),
            "scores": self.scores.to_dict(),
            "raw_metrics": _round_dict(self.raw_metrics),
            "context_metrics": _round_dict(self.context_metrics),
            "forward": self.forward.to_dict(),
            "validation_tags": self.validation_tags,
            "explanation": self.explanation,
            "is_active": self.is_active,
            "merged_into": self.merged_into,
        }

    def strength_pct(self) -> int:
        return int(self.scores.strength_score * 100)

    def confidence_pct(self) -> int:
        return int(self.scores.confidence_score * 100)


# ============================================================
# Specific Event Types
# ============================================================

@dataclass
class AbsorptionEvent(MicrostructureEvent):
    event_type: str = "absorption"
    window_seconds: int = 30
    aggressive_volume: float = 0.0
    signed_delta: float = 0.0
    price_change_after_aggression: float = 0.0
    local_volume_percentile: float = 0.0
    delta_percentile: float = 0.0
    book_liquidity_context: float = 0.0
    vwap_distance: float = 0.0
    spread_context: float = 0.0
    regime_context: str = ""
    repeated_tests: int = 0

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "window_seconds": self.window_seconds,
            "aggressive_volume": round(self.aggressive_volume, 4),
            "signed_delta": round(self.signed_delta, 4),
            "price_change_after_aggression": round(self.price_change_after_aggression, 2),
            "local_volume_percentile": round(self.local_volume_percentile, 3),
            "delta_percentile": round(self.delta_percentile, 3),
            "book_liquidity_context": round(self.book_liquidity_context, 4),
            "vwap_distance": round(self.vwap_distance, 2),
            "spread_context": round(self.spread_context, 2),
            "regime_context": self.regime_context,
            "repeated_tests": self.repeated_tests,
        })
        return d


@dataclass
class ExhaustionEvent(MicrostructureEvent):
    event_type: str = "exhaustion"
    aggressive_volume: float = 0.0
    delta: float = 0.0
    bubble_count: int = 0
    price_impact_per_volume: float = 0.0
    continuation_failure_score: float = 0.0
    local_extreme_context: str = ""
    cvd_divergence_context: float = 0.0

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "aggressive_volume": round(self.aggressive_volume, 4),
            "delta": round(self.delta, 4),
            "bubble_count": self.bubble_count,
            "price_impact_per_volume": round(self.price_impact_per_volume, 6),
            "continuation_failure_score": round(self.continuation_failure_score, 3),
            "local_extreme_context": self.local_extreme_context,
            "cvd_divergence_context": round(self.cvd_divergence_context, 3),
        })
        return d


@dataclass
class LiquiditySweepEvent(MicrostructureEvent):
    event_type: str = "liquidity_sweep"
    swept_level: float = 0.0
    sweep_distance: float = 0.0
    sweep_volume: float = 0.0
    sweep_delta: float = 0.0
    reclaim_status: bool = False
    reversal_confirmation: bool = False
    time_to_reclaim: float = 0.0
    prior_touches: int = 0

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "swept_level": round(self.swept_level, 2),
            "sweep_distance": round(self.sweep_distance, 2),
            "sweep_volume": round(self.sweep_volume, 4),
            "sweep_delta": round(self.sweep_delta, 4),
            "reclaim_status": self.reclaim_status,
            "reversal_confirmation": self.reversal_confirmation,
            "time_to_reclaim": round(self.time_to_reclaim, 1),
            "prior_touches": self.prior_touches,
        })
        return d


@dataclass
class DeltaDivergenceEvent(MicrostructureEvent):
    event_type: str = "delta_divergence"
    price_structure: str = ""
    cvd_structure: str = ""
    divergence_window: int = 60
    price_at_detection: float = 0.0
    cvd_at_detection: float = 0.0
    local_trend_context: str = ""

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "price_structure": self.price_structure,
            "cvd_structure": self.cvd_structure,
            "divergence_window": self.divergence_window,
            "price_at_detection": round(self.price_at_detection, 2),
            "cvd_at_detection": round(self.cvd_at_detection, 4),
            "local_trend_context": self.local_trend_context,
        })
        return d


@dataclass
class ImbalanceEvent(MicrostructureEvent):
    event_type: str = "imbalance"
    volume_buy: float = 0.0
    volume_sell: float = 0.0
    delta: float = 0.0
    imbalance_ratio: float = 0.0
    price_response: float = 0.0
    continuation_score: float = 0.0
    failure_score: float = 0.0
    classification: str = ""  # continuation / absorption / exhaustion

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "volume_buy": round(self.volume_buy, 4),
            "volume_sell": round(self.volume_sell, 4),
            "delta": round(self.delta, 4),
            "imbalance_ratio": round(self.imbalance_ratio, 3),
            "price_response": round(self.price_response, 2),
            "continuation_score": round(self.continuation_score, 3),
            "failure_score": round(self.failure_score, 3),
            "classification": self.classification,
        })
        return d


@dataclass
class LargeTradeClusterEvent(MicrostructureEvent):
    event_type: str = "large_trade_cluster"
    total_cluster_volume: float = 0.0
    number_of_large_trades: int = 0
    average_trade_size: float = 0.0
    max_trade_size: float = 0.0
    local_percentile_rank: float = 0.0
    price_response_after_cluster: float = 0.0
    continuation_or_failure_label: str = ""

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "total_cluster_volume": round(self.total_cluster_volume, 4),
            "number_of_large_trades": self.number_of_large_trades,
            "average_trade_size": round(self.average_trade_size, 4),
            "max_trade_size": round(self.max_trade_size, 4),
            "local_percentile_rank": round(self.local_percentile_rank, 3),
            "price_response_after_cluster": round(self.price_response_after_cluster, 2),
            "continuation_or_failure_label": self.continuation_or_failure_label,
        })
        return d


@dataclass
class RangeBreakEvent(MicrostructureEvent):
    event_type: str = "range_break"
    range_high: float = 0.0
    range_low: float = 0.0
    break_distance: float = 0.0
    break_volume: float = 0.0
    break_delta: float = 0.0
    continuation_after_break: float = 0.0
    failed_break_status: bool = False
    reclaim_time: float = 0.0
    range_context_score: float = 0.0

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "range_high": round(self.range_high, 2),
            "range_low": round(self.range_low, 2),
            "break_distance": round(self.break_distance, 2),
            "break_volume": round(self.break_volume, 4),
            "break_delta": round(self.break_delta, 4),
            "continuation_after_break": round(self.continuation_after_break, 2),
            "failed_break_status": self.failed_break_status,
            "reclaim_time": round(self.reclaim_time, 1),
            "range_context_score": round(self.range_context_score, 3),
        })
        return d


@dataclass
class VWAPReactionEvent(MicrostructureEvent):
    event_type: str = "vwap_reaction"
    vwap: float = 0.0
    distance_to_vwap: float = 0.0
    reaction_type: str = ""  # reject / reclaim / hold / break
    delta_context: float = 0.0
    volume_context: float = 0.0
    follow_through: float = 0.0

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "vwap": round(self.vwap, 2),
            "distance_to_vwap": round(self.distance_to_vwap, 2),
            "reaction_type": self.reaction_type,
            "delta_context": round(self.delta_context, 4),
            "volume_context": round(self.volume_context, 4),
            "follow_through": round(self.follow_through, 2),
        })
        return d


# ============================================================
# Helpers
# ============================================================

def _r(v, decimals=6):
    """Round if numeric, pass through if None."""
    if v is None:
        return None
    return round(v, decimals)


def _round_dict(d: dict, decimals=4) -> dict:
    return {k: round(v, decimals) if isinstance(v, (int, float)) else v for k, v in d.items()}
