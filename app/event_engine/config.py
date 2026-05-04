"""
MANTIS Event Engine — Configuration
All tunable thresholds in one place. No magic numbers scattered in code.
Each detector reads from this config. Override via environment or constructor.
"""

from dataclasses import dataclass, field


@dataclass
class AbsorptionConfig:
    window_seconds: int = 30
    min_volume_btc: float = 2.0
    min_delta_percentile: float = 0.85
    max_price_continuation_bps: float = 5.0
    min_repeated_tests: int = 1
    book_depth_levels: int = 10


@dataclass
class ExhaustionConfig:
    window_seconds: int = 60
    min_volume_btc: float = 3.0
    bubble_window_seconds: int = 120
    min_bubble_count: int = 2
    impact_decline_ratio: float = 0.6
    near_extreme_threshold_bps: float = 10.0


@dataclass
class SweepConfig:
    lookback_seconds: int = 300
    reclaim_window_seconds: int = 60
    min_sweep_distance_usd: float = 10.0
    max_sweep_distance_usd: float = 150.0
    min_prior_touches: int = 2


@dataclass
class DivergenceConfig:
    window_seconds: int = 60
    min_price_move_usd: float = 30.0
    min_cvd_opposite_move: float = 0.0


@dataclass
class ImbalanceConfig:
    window_seconds: int = 15
    min_ratio: float = 3.0
    min_volume_btc: float = 1.0
    classification_window_seconds: int = 5


@dataclass
class LargeTradeClusterConfig:
    cluster_window_seconds: int = 30
    min_cluster_count: int = 3
    percentile_threshold: float = 0.95
    min_cluster_volume_btc: float = 5.0


@dataclass
class RangeBreakConfig:
    lookback_seconds: int = 600
    min_range_height_usd: float = 50.0
    min_range_touches: int = 3
    break_threshold_bps: float = 3.0
    reclaim_window_seconds: int = 60
    failed_break_reclaim_bps: float = 2.0


@dataclass
class VWAPConfig:
    reaction_window_seconds: int = 30
    proximity_threshold_usd: float = 15.0
    min_volume_for_reaction: float = 1.0
    min_delta_for_reaction: float = 0.5
    break_confirm_seconds: int = 10


@dataclass
class ScoringConfig:
    # Weights for each scoring component (must sum to 1.0 per category)
    strength_weights: dict = field(default_factory=lambda: {
        "volume": 0.25,
        "delta": 0.25,
        "price_action": 0.25,
        "repetition": 0.25,
    })
    confidence_weights: dict = field(default_factory=lambda: {
        "regime": 0.3,
        "liquidity": 0.25,
        "spread": 0.2,
        "sample_size": 0.25,
    })
    noise_penalty_weights: dict = field(default_factory=lambda: {
        "low_volume": 0.3,
        "wide_spread": 0.2,
        "low_volatility": 0.2,
        "cluster_duplicate": 0.3,
    })


@dataclass
class DedupConfig:
    cooldown_seconds: float = 10.0
    price_cluster_bps: float = 2.0
    merge_window_seconds: float = 5.0
    max_events_per_minute: int = 10


@dataclass
class LoggerConfig:
    jsonl_path: str = "data/events/events_raw.jsonl"
    csv_path: str = "data/events/events_summary.csv"
    parquet_path: str = "data/events/events_validated.parquet"
    max_buffer_size: int = 100
    flush_interval_seconds: float = 5.0


@dataclass
class OutcomeConfig:
    horizons_seconds: list = field(default_factory=lambda: [10, 30, 60, 120, 300])
    tp_levels_bps: list = field(default_factory=lambda: [10, 20])
    sl_levels_bps: list = field(default_factory=lambda: [10, 20])
    cost_assumptions_bps: list = field(default_factory=lambda: [2, 4, 6])


@dataclass
class BlacklistConfig:
    """
    Blacklisted event types: still logged, never boost score,
    never pass directional filter, never trigger tradeable state.
    """
    event_types: set = field(default_factory=lambda: {
        "sell_exhaustion",
        "sell_imbalance",
        "sell_cluster",
    })
    # Blacklisted events get this reliability cap in confidence scoring
    reliability_cap: float = 0.10
    # Blacklisted events get this maximum composite score
    max_composite_score: float = 0.15


@dataclass
class WatchlistConfig:
    """
    Candidate watchlist: events tracked with full snapshots.
    Not tradeable. Diagnostic/observation only.
    """
    event_types: set = field(default_factory=lambda: {
        "sell_absorption",
        "down_break",
        "up_break",
    })
    # Snapshot settings
    snapshot_path: str = "data/events/candidate_watchlist.csv"
    max_snapshots: int = 5000
    # Forward return horizons for snapshot validation
    horizons_seconds: list = field(default_factory=lambda: [10, 30, 60, 120, 300])
    # Price/delta/CVD path windows (seconds before/after event)
    path_before_seconds: int = 30
    path_after_seconds: int = 60
    path_sample_interval: int = 5  # sample every N seconds


@dataclass
class EventEngineConfig:
    absorption: AbsorptionConfig = field(default_factory=AbsorptionConfig)
    exhaustion: ExhaustionConfig = field(default_factory=ExhaustionConfig)
    sweep: SweepConfig = field(default_factory=SweepConfig)
    divergence: DivergenceConfig = field(default_factory=DivergenceConfig)
    imbalance: ImbalanceConfig = field(default_factory=ImbalanceConfig)
    large_trade_cluster: LargeTradeClusterConfig = field(default_factory=LargeTradeClusterConfig)
    range_break: RangeBreakConfig = field(default_factory=RangeBreakConfig)
    vwap: VWAPConfig = field(default_factory=VWAPConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    dedup: DedupConfig = field(default_factory=DedupConfig)
    logger: LoggerConfig = field(default_factory=LoggerConfig)
    outcome: OutcomeConfig = field(default_factory=OutcomeConfig)
    blacklist: BlacklistConfig = field(default_factory=BlacklistConfig)
    watchlist: WatchlistConfig = field(default_factory=WatchlistConfig)

    # Global settings
    symbol: str = "BTC"
    exchange: str = "hyperliquid"
    max_event_history: int = 1000
    rolling_buffer_seconds: float = 600.0
