"""
MANTIS SPE — Configuration
All thresholds in one place. No magic numbers in logic.
"""

from dataclasses import dataclass, field


@dataclass
class MantisStateConfig:
    """Layer 1: Context state machine thresholds."""
    # CASCADE: rapid directional move with liquidation cascade
    cascade_body_pct_threshold: float = 0.15        # body >= 15% of rolling range
    cascade_continuation_candles: int = 3            # continuation within N candles
    cascade_liquidation_spike_mult: float = 3.0      # liquidation > 3x baseline

    # UNWIND: forced position closure
    unwind_funding_z_threshold: float = 2.0          # funding z-score extreme
    unwind_oi_decrease_pct: float = 0.05             # OI declining > 5%

    # State duration limits
    max_state_age_seconds: float = 600.0             # 10 min max state validity
    state_cooldown_seconds: float = 120.0            # cooldown between state transitions


@dataclass
class PressureConfig:
    """Layer 2: Positioning pressure detection."""
    # Funding proxy: delta skew z-score
    funding_z_long_threshold: float = 1.5            # crowd long threshold
    funding_z_short_threshold: float = -1.5          # crowd short threshold
    funding_z_window_seconds: float = 300.0          # 5 min rolling window
    funding_z_lookback_periods: int = 20             # periods for z-score calc

    # OI proxy: cumulative volume delta divergence
    oi_rising_delta_threshold: float = 0.6           # delta bias > 60% = OI rising proxy
    oi_declining_delta_threshold: float = 0.35       # delta bias < 35% = OI declining proxy

    # Pressure strength mapping
    pressure_max_z: float = 4.0                      # z-score cap for 0-100 mapping


@dataclass
class DisplacementConfig:
    """Layer 3: Forced move / displacement detection."""
    # Body size
    body_percentile_threshold: float = 0.85           # body >= p85 of rolling distribution
    body_lookback_count: int = 60                     # candles for percentile

    # Move magnitude
    min_move_bps: float = 15.0                        # minimum 15 bps move
    move_window_seconds: float = 180.0                # within 3 minutes

    # Continuation
    continuation_candles: int = 3                     # within 3 candles
    continuation_min_bps: float = 5.0                 # at least 5 bps continuation

    # Optional confirmation
    liquidation_spike_mult: float = 3.0               # liquidation vs baseline
    volume_spike_percentile: float = 0.95             # volume vs rolling


@dataclass
class SweepConfig:
    """Layer 4: Structural sweep / CRT."""
    lookback_seconds: float = 600.0                   # 10 min lookback for levels
    min_sweep_distance_bps: float = 3.0               # minimum sweep distance
    reclaim_window_seconds: float = 60.0              # time to reclaim level
    min_prior_touches: int = 2                        # level must be tested ≥2x


@dataclass
class TrapConfig:
    """Layer 5: Trap / confirmation."""
    # Confirmation window
    confirmation_window_seconds: float = 120.0        # 2 min to confirm trap
    # Reversal magnitude
    min_reversal_bps: float = 5.0                     # minimum reversal after sweep
    # Volume on reversal
    reversal_volume_percentile: float = 0.7           # volume on reversal bar


@dataclass
class ExecutionFilterConfig:
    """Layer 6: Execution quality gates."""
    max_spread_bps: float = 3.0                       # max allowed spread
    min_depth_btc: float = 2.0                        # min book depth (top 5 levels)
    max_volatility_spike_mult: float = 4.0            # max vol spike (unless CASCADE)
    depth_levels: int = 5                             # levels to check


@dataclass
class EntryConfig:
    """Layer 7: Entry logic."""
    retrace_min_pct: float = 0.30                     # 30% retrace of displacement
    retrace_max_pct: float = 0.50                     # 50% retrace of displacement
    entry_type: str = "limit_passive"                 # maker-only
    entry_timeout_seconds: float = 120.0              # cancel if not filled


@dataclass
class ExitConfig:
    """Layer 8: Exit logic."""
    # TP: nearest liquidity/prior swing
    tp_lookback_seconds: float = 600.0                # swing lookback
    tp_min_distance_bps: float = 10.0                 # minimum TP distance
    # SL: beyond displacement origin
    sl_buffer_bps: float = 5.0                        # buffer beyond origin
    # Risk:reward
    min_rr_ratio: float = 1.5                         # minimum R:R


@dataclass
class ValidationConfig:
    """Mandatory validation parameters."""
    taker_cost_bps: float = 4.0                       # taker cost assumption
    maker_cost_bps: float = 0.5                       # maker cost (0-1 bps)
    min_profit_factor: float = 1.1                    # minimum PF
    min_net_return_bps: float = 0.0                   # must be positive after cost
    missed_fill_probability: float = 0.15             # 15% missed fills assumption
    adverse_selection_bps: float = 2.0                # adverse selection cost
    split_count: int = 5                              # cross-validation splits


@dataclass
class AlertConfig:
    """Alert rules."""
    min_confidence_score: float = 70.0                # minimum confidence to alert
    cooldown_seconds: float = 300.0                   # 5 min between alerts
    max_alerts_per_hour: int = 6                      # rate limit


@dataclass
class SPEConfig:
    """Master SPE configuration."""
    state: MantisStateConfig = field(default_factory=MantisStateConfig)
    pressure: PressureConfig = field(default_factory=PressureConfig)
    displacement: DisplacementConfig = field(default_factory=DisplacementConfig)
    sweep: SweepConfig = field(default_factory=SweepConfig)
    trap: TrapConfig = field(default_factory=TrapConfig)
    execution: ExecutionFilterConfig = field(default_factory=ExecutionFilterConfig)
    entry: EntryConfig = field(default_factory=EntryConfig)
    exit: ExitConfig = field(default_factory=ExitConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    alert: AlertConfig = field(default_factory=AlertConfig)

    # Global
    enabled: bool = True
    symbol: str = "BTC"
    min_imbalance_score: float = 70.0
    min_execution_quality: float = 70.0
    max_risk_score: float = 60.0                      # CASCADE can override
    cascade_risk_override: float = 80.0               # CASCADE allows higher risk
