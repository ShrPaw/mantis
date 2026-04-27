"""
Auction Failure Research — Configuration

ALL thresholds are relative (percentile, ratio, bps).
NO fixed USD amounts.

IMPORTANT: These are structural starting assumptions, NOT proven constants.
They define what "strong aggression" and "failure to continue" mean
in relative terms. They are chosen based on market mechanics reasoning,
not optimized from data. They will NOT be tuned after results are observed.

If results show no edge at these thresholds, the conclusion is "no edge
at these assumptions" — NOT "try different thresholds."
"""

from dataclasses import dataclass, field


@dataclass
class AggressionConfig:
    """What constitutes 'strong aggression' in relative terms."""

    # Delta ratio threshold: |delta| / volume
    # 0.40 = 40% of volume is net aggressive in one direction
    # This is a STRUCTURAL condition (one side dominating), not a signal
    delta_ratio_threshold: float = 0.40

    # Delta percentile vs recent history
    # 0.85 = current |delta| exceeds 85% of recent windows
    delta_percentile_threshold: float = 0.85

    # Volume percentile vs recent history
    # 0.70 = current volume exceeds 70% of recent windows
    # Ensures we're in an active period, not dead air
    volume_percentile_threshold: float = 0.70

    # Minimum samples in detection window
    min_samples_in_window: int = 8

    # Rolling history depth for percentile computation (number of windows)
    percentile_lookback: int = 20


@dataclass
class FailureConfig:
    """What constitutes 'failure to continue' in relative terms."""

    # Maximum price movement in bps for "no response"
    # If aggression is strong but price moved < this, it's a failure
    max_move_bps: float = 3.0

    # Quick reclaim/reject window (seconds)
    # If price breaks level but returns within this window, it's a failure
    reclaim_window_seconds: float = 30.0

    # Reclaim threshold in bps
    # Price must return within this many bps of the level to count as reclaim
    reclaim_threshold_bps: float = 2.0


@dataclass
class BreakoutConfig:
    """What constitutes a 'breakout' in relative terms."""

    # Breakout distance in rolling range units
    # 0.10 = price exceeds range boundary by 10% of range height
    # This adapts to current volatility automatically
    break_distance_range_fraction: float = 0.10

    # Minimum range height in bps (prevents micro-ranges)
    min_range_height_bps: float = 5.0

    # Range lookback for establishing boundaries (seconds)
    range_lookback_seconds: float = 300.0

    # Exclusion zone: exclude last N seconds from range calculation
    # (these ticks are the "break" zone, not the "range" zone)
    range_exclude_recent_seconds: float = 15.0

    # Flow confirmation: delta must agree with break direction
    # delta_ratio must exceed this (with correct sign) for acceptance
    flow_confirmation_ratio: float = 0.25

    # Hold window: how long price must stay outside for "acceptance" (seconds)
    hold_window_seconds: float = 15.0

    # Rejection window: if price returns within this time, it's rejection
    rejection_window_seconds: float = 30.0


@dataclass
class OutcomeConfig:
    """Forward outcome measurement horizons."""

    horizons_seconds: list = field(default_factory=lambda: [5, 10, 30, 60, 120, 300])
    cost_assumptions_bps: list = field(default_factory=lambda: [2, 4, 6])


@dataclass
class DetectionConfig:
    """Detection window and buffer settings."""

    # Primary detection window (seconds)
    detection_window_seconds: float = 15.0

    # Rolling buffer depth (seconds)
    buffer_depth_seconds: float = 600.0

    # Cooldown between events of same type (seconds)
    cooldown_seconds: float = 10.0

    # Price cluster: merge events within this bps distance
    cluster_bps: float = 3.0


@dataclass
class AuctionFailureConfig:
    """Top-level config container."""
    aggression: AggressionConfig = field(default_factory=AggressionConfig)
    failure: FailureConfig = field(default_factory=FailureConfig)
    breakout: BreakoutConfig = field(default_factory=BreakoutConfig)
    outcome: OutcomeConfig = field(default_factory=OutcomeConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
