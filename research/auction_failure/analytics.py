"""
Auction Failure Research — Analytics

Computes all required statistics for the research report.
No ML. No optimization. Pure arithmetic on outcome data.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .models import AuctionEvent


@dataclass
class EventClassStats:
    """Statistics for one event class at one horizon."""
    event_class: str = ""
    horizon: str = ""
    n: int = 0
    n_complete: int = 0

    # Directional returns (favorable = positive)
    gross_return_bps: float = 0.0
    net_return_2bps: float = 0.0
    net_return_4bps: float = 0.0
    net_return_6bps: float = 0.0

    # Win/loss
    winrate_2bps: float = 0.0
    winrate_4bps: float = 0.0
    winrate_6bps: float = 0.0

    # Profit factor (at 4bps)
    profit_factor_4bps: float = 0.0

    # Excursion
    avg_mfe_30s: float = 0.0
    avg_mae_30s: float = 0.0
    mfe_mae_ratio_30s: float = 0.0

    # Timing
    avg_time_to_positive: float = 0.0
    median_time_to_positive: float = 0.0
    pct_positive_at_30s: float = 0.0

    # Invalidation
    invalidation_rate: float = 0.0


def compute_directional_returns(events: list[AuctionEvent], horizon: int) -> list[float]:
    """
    Get directional returns at a given horizon.
    Returns list of bps values (positive = favorable).
    """
    results = []
    for e in events:
        raw = None
        if horizon == 5:
            raw = e.future_return_5s
        elif horizon == 10:
            raw = e.future_return_10s
        elif horizon == 30:
            raw = e.future_return_30s
        elif horizon == 60:
            raw = e.future_return_60s
        elif horizon == 120:
            raw = e.future_return_120s
        elif horizon == 300:
            raw = e.future_return_300s

        if raw is not None:
            results.append(e.directional_return(raw))
    return results


def compute_stats_for_class(
    events: list[AuctionEvent],
    event_class: str,
    horizon: int,
) -> EventClassStats:
    """Compute full statistics for one event class at one horizon."""
    class_events = [e for e in events if e.event_class == event_class]
    complete = [e for e in class_events if e.is_complete]

    returns = compute_directional_returns(class_events, horizon)

    stats = EventClassStats(
        event_class=event_class,
        horizon=f"{horizon}s",
        n=len(class_events),
        n_complete=len(complete),
    )

    if not returns:
        return stats

    n = len(returns)
    gross = sum(returns) / n

    stats.gross_return_bps = round(gross, 2)
    stats.net_return_2bps = round(gross - 2, 2)
    stats.net_return_4bps = round(gross - 4, 2)
    stats.net_return_6bps = round(gross - 6, 2)

    # Winrates
    stats.winrate_2bps = round(sum(1 for r in returns if r - 2 > 0) / n, 4)
    stats.winrate_4bps = round(sum(1 for r in returns if r - 4 > 0) / n, 4)
    stats.winrate_6bps = round(sum(1 for r in returns if r - 6 > 0) / n, 4)

    # Profit factor at 4bps
    net4 = [r - 4 for r in returns]
    gross_profit = sum(r for r in net4 if r > 0)
    gross_loss = abs(sum(r for r in net4 if r < 0))
    stats.profit_factor_4bps = round(
        gross_profit / gross_loss if gross_loss > 0 else float('inf'), 3
    )

    # Excursion (from complete events with excursion data)
    mfe_30_vals = [e.mfe_30s for e in complete if e.mfe_30s is not None]
    mae_30_vals = [e.mae_30s for e in complete if e.mae_30s is not None]

    if mfe_30_vals:
        stats.avg_mfe_30s = round(sum(mfe_30_vals) / len(mfe_30_vals), 2)
    if mae_30_vals:
        stats.avg_mae_30s = round(sum(mae_30_vals) / len(mae_30_vals), 2)
    if stats.avg_mae_30s > 0:
        stats.mfe_mae_ratio_30s = round(stats.avg_mfe_30s / stats.avg_mae_30s, 2)

    # Timing
    ttp_vals = [e.time_to_positive for e in complete
                if e.time_to_positive is not None]
    if ttp_vals:
        stats.avg_time_to_positive = round(sum(ttp_vals) / len(ttp_vals), 1)
        sorted_ttp = sorted(ttp_vals)
        stats.median_time_to_positive = round(sorted_ttp[len(sorted_ttp) // 2], 1)
        stats.pct_positive_at_30s = round(
            sum(1 for t in ttp_vals if t <= 30) / len(ttp_vals), 4
        )

    # Invalidation
    invalidated = sum(1 for e in complete if e.invalidated)
    stats.invalidation_rate = round(invalidated / len(complete), 4) if complete else 0.0

    return stats


def compute_all_stats(events: list[AuctionEvent]) -> dict[str, list[EventClassStats]]:
    """
    Compute stats for all event classes at all horizons.
    Returns: {event_class: [stats_at_5s, stats_at_10s, ...]}
    """
    event_classes = list(set(e.event_class for e in events))
    horizons = [5, 10, 30, 60, 120, 300]

    result = {}
    for ec in sorted(event_classes):
        result[ec] = []
        for h in horizons:
            stats = compute_stats_for_class(events, ec, h)
            result[ec].append(stats)

    return result


def compute_time_split_stats(
    events: list[AuctionEvent],
    event_class: str,
    horizon: int = 60,
) -> dict:
    """Split events chronologically and compare."""
    class_events = sorted(
        [e for e in events if e.event_class == event_class],
        key=lambda e: e.timestamp,
    )

    if len(class_events) < 4:
        return {"error": "insufficient data for time split"}

    mid = len(class_events) // 2
    first_half = class_events[:mid]
    second_half = class_events[mid:]

    def _half_stats(evts):
        returns = compute_directional_returns(evts, horizon)
        if not returns:
            return {"n": 0}
        n = len(returns)
        gross = sum(returns) / n
        net4 = [r - 4 for r in returns]
        wins = sum(1 for r in net4 if r > 0)
        return {
            "n": n,
            "gross_bps": round(gross, 2),
            "net_4bps": round(gross - 4, 2),
            "winrate_4bps": round(wins / n, 4),
        }

    return {
        "first_half": _half_stats(first_half),
        "second_half": _half_stats(second_half),
    }


def compute_10min_blocks(
    events: list[AuctionEvent],
    event_class: str,
    horizon: int = 60,
    block_minutes: int = 10,
) -> dict:
    """Split performance into 10-minute blocks for decay analysis."""
    class_events = sorted(
        [e for e in events if e.event_class == event_class],
        key=lambda e: e.timestamp,
    )

    if not class_events:
        return {"blocks": [], "n_blocks": 0}

    t_start = class_events[0].timestamp
    t_end = class_events[-1].timestamp
    block_seconds = block_minutes * 60

    blocks = []
    block_start = t_start
    block_idx = 0

    while block_start < t_end:
        block_end = block_start + block_seconds
        block_events = [e for e in class_events
                        if block_start <= e.timestamp < block_end]

        if block_events:
            returns = compute_directional_returns(block_events, horizon)
            if returns:
                n = len(returns)
                gross = sum(returns) / n
                net4 = gross - 4
                wins = sum(1 for r in returns if r - 4 > 0)
                blocks.append({
                    "block_index": block_idx,
                    "minutes_from_start": round((block_start - t_start) / 60, 1),
                    "n": n,
                    "gross_bps": round(gross, 2),
                    "net_4bps": round(net4, 2),
                    "winrate_4bps": round(wins / n, 4) if n > 0 else 0,
                })

        block_start = block_end
        block_idx += 1

    # Decay: first third vs last third
    decay_detected = False
    if len(blocks) >= 3:
        third = len(blocks) // 3
        first_third = blocks[:max(third, 1)]
        last_third = blocks[-max(third, 1):]

        avg_first = sum(b["net_4bps"] for b in first_third) / len(first_third)
        avg_last = sum(b["net_4bps"] for b in last_third) / len(last_third)

        if avg_first > 0 and avg_last < avg_first * 0.5:
            decay_detected = True
        elif avg_first > 0 and avg_last < 0:
            decay_detected = True

    return {
        "blocks": blocks,
        "n_blocks": len(blocks),
        "decay_detected": decay_detected,
    }
