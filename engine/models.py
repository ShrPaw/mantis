"""Shared data models for MANTIS Execution Engine."""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


# ── Enums ──────────────────────────────────────────────────────────────

class MarketState(Enum):
    IDLE = "IDLE"
    CROWD_BUILDUP = "CROWD_BUILDUP"
    LIQUIDATION_CASCADE = "LIQUIDATION_CASCADE"
    UNWIND = "UNWIND"
    EXHAUSTION_ABSORPTION = "EXHAUSTION_ABSORPTION"


class CrowdSide(Enum):
    LONGS = "LONGS"
    SHORTS = "SHORTS"


class CascadeDirection(Enum):
    DOWN = "DOWN"
    UP = "UP"


class UnwindSide(Enum):
    LONGS_EXITING = "LONGS_EXITING"
    SHORTS_EXITING = "SHORTS_EXITING"


class ExecutionMode(Enum):
    WAIT = "WAIT"
    MAKER_ONLY = "MAKER_ONLY"
    TAKER_ALLOWED = "TAKER_ALLOWED"
    NO_TRADE = "NO_TRADE"
    REDUCE_SIZE = "REDUCE_SIZE"


class AlertTier(Enum):
    WATCH = 1
    ACTIONABLE = 2
    DANGER = 3


class ExhaustionSide(Enum):
    SELL_EXHAUSTION = "SELL_EXHAUSTION"
    BUY_EXHAUSTION = "BUY_EXHAUSTION"


# ── Raw Data ───────────────────────────────────────────────────────────

@dataclass
class Trade:
    timestamp: float
    price: float
    qty: float
    side: str  # "buy" or "sell"
    value_usd: float = 0.0
    exchange: str = "hyperliquid"

    def __post_init__(self):
        if self.value_usd == 0.0:
            self.value_usd = self.price * self.qty


@dataclass
class BookLevel:
    price: float
    qty: float


@dataclass
class OrderBook:
    timestamp: float
    bids: list[BookLevel] = field(default_factory=list)
    asks: list[BookLevel] = field(default_factory=list)
    mid: float = 0.0
    spread_bps: float = 0.0

    def __post_init__(self):
        if self.bids and self.asks and self.mid == 0.0:
            self.mid = (self.bids[0].price + self.asks[0].price) / 2
        if self.bids and self.asks and self.spread_bps == 0.0:
            best_bid = self.bids[0].price
            best_ask = self.asks[0].price
            if best_bid > 0:
                self.spread_bps = (best_ask - best_bid) / best_bid * 10000


@dataclass
class Candle:
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    interval: str = "1m"


# ── Exchange Reference Data ────────────────────────────────────────────

@dataclass
class FundingRate:
    timestamp: float
    rate: float
    exchange: str = "hyperliquid"
    mark_price: float = 0.0
    index_price: float = 0.0


@dataclass
class OpenInterest:
    timestamp: float
    oi: float
    exchange: str = "hyperliquid"


@dataclass
class Liquidation:
    timestamp: float
    side: str  # "long" or "short" — the side being liquidated
    qty: float
    price: float
    notional_usd: float = 0.0
    exchange: str = "binance"

    def __post_init__(self):
        if self.notional_usd == 0.0:
            self.notional_usd = self.price * self.qty


# ── Computed Features ──────────────────────────────────────────────────

@dataclass
class FundingFeatures:
    current: float = 0.0
    rolling_mean: float = 0.0
    rolling_std: float = 0.0
    z_score: float = 0.0
    percentile: float = 0.0
    persistence: float = 0.0  # fraction of recent windows with same sign
    direction: int = 0  # +1, 0, -1
    positive_extreme: bool = False
    negative_extreme: bool = False


@dataclass
class OIFeatures:
    current: float = 0.0
    change_5m: float = 0.0
    change_15m: float = 0.0
    change_1h: float = 0.0
    z_score: float = 0.0
    percentile: float = 0.0
    acceleration: float = 0.0  # change_15m - change_5m normalized
    strong_rise: bool = False
    strong_fall: bool = False


@dataclass
class LiquidationFeatures:
    count_1m: int = 0
    count_5m: int = 0
    notional_1m: float = 0.0
    notional_5m: float = 0.0
    direction: str = "neutral"  # "long_liq", "short_liq", "neutral"
    notional_z: float = 0.0
    cascade_active: bool = False
    cascade_direction: str = "neutral"
    cluster_detected: bool = False


@dataclass
class TradeFlowFeatures:
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    delta: float = 0.0
    cum_delta: float = 0.0
    delta_z: float = 0.0
    buy_pressure: float = 0.5
    sell_pressure: float = 0.5
    strong_buy: bool = False
    strong_sell: bool = False
    volume_spike: bool = False
    trade_count: int = 0
    trade_frequency: float = 0.0


@dataclass
class OrderBookFeatures:
    spread_bps: float = 0.0
    bid_depth: float = 0.0
    ask_depth: float = 0.0
    book_imbalance: float = 0.0
    depth_imbalance: float = 0.0
    liquidity_thinning: bool = False
    spread_z: float = 0.0
    depth_z: float = 0.0
    sudden_depth_drop: bool = False


@dataclass
class ExecutionQualityFeatures:
    spread_bps: float = 0.0
    expected_slippage_bps: float = 0.0
    available_depth_usd: float = 0.0
    volatility_burst: bool = False
    book_stable: bool = True
    score: float = 100.0  # 0-100


# ── Detector Outputs ──────────────────────────────────────────────────

@dataclass
class CrowdBuildupState:
    active: bool = False
    crowd_side: str = "neutral"
    severity: float = 0.0
    trade_signal: bool = False
    message: str = ""


@dataclass
class LiquidationCascadeState:
    active: bool = False
    cascade_direction: str = "neutral"
    intensity: float = 0.0
    execution_mode: str = "NORMAL"
    message: str = ""


@dataclass
class UnwindState:
    active: bool = False
    unwind_side: str = "neutral"
    direction: str = "neutral"
    maturity: str = "EARLY"
    message: str = ""


@dataclass
class ExhaustionAbsorptionState:
    active: bool = False
    side: str = "neutral"
    confidence: float = 0.0
    trade_signal: bool = False
    message: str = ""


# ── Scores ─────────────────────────────────────────────────────────────

@dataclass
class Scores:
    imbalance: float = 0.0
    execution_quality: float = 0.0
    risk: float = 0.0
    trade_environment: float = 0.0


# ── Alert ──────────────────────────────────────────────────────────────

@dataclass
class Alert:
    timestamp: float
    tier: int
    state: str
    side: str
    severity: float
    reason: str
    do_not: str
    execution_recommendation: str
    scores: Scores = field(default_factory=Scores)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tier"] = self.tier
        return d


# ── Engine Event (full snapshot) ───────────────────────────────────────

@dataclass
class EngineEvent:
    timestamp: float
    market_state: MarketState
    crowd: CrowdBuildupState
    cascade: LiquidationCascadeState
    unwind: UnwindState
    exhaustion: ExhaustionAbsorptionState
    scores: Scores
    execution_mode: ExecutionMode
    alert: Optional[Alert] = None
    funding: FundingFeatures = field(default_factory=FundingFeatures)
    oi: OIFeatures = field(default_factory=OIFeatures)
    liquidation: LiquidationFeatures = field(default_factory=LiquidationFeatures)
    trade_flow: TradeFlowFeatures = field(default_factory=TradeFlowFeatures)
    order_book: OrderBookFeatures = field(default_factory=OrderBookFeatures)

    def to_dict(self) -> dict:
        return asdict(self)
