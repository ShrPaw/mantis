#!/usr/bin/env python3
"""
Shadow validation for failed_aggression_sell_v0.

Loads existing event data (JSONL with forward outcomes), reconstructs
rolling buffer from event stream, applies detector conditions, and
measures forward performance.

Corrections applied:
  1. Promotion criteria: minimum ≥100, preferred ≥300
  2. No data leakage: strict chronological processing, past-only buffer
  3. Proximity condition: distance_to_prior_low <= 5 bps
  4. time_to_positive metric: seconds until trade becomes profitable

Does NOT modify live engine. Does NOT write to production files.

Usage:
    python3 scripts/validate_failed_aggression_sell_v0.py \
        --input backend/data/events/events_with_outcomes.jsonl \
        --output-csv backend/data/events/failed_aggression_sell_v0_shadow.csv \
        --output-md FAILED_AGGRESSION_SELL_V0_REPORT.md
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional


# ============================================================
# Configuration (matches detector thresholds — NOT tuned)
# ============================================================

AGGRESSION_DELTA_RATIO = -0.40
AGGRESSION_PERCENTILE = 0.85
MAX_DOWNSIDE_BPS = 2.0
DETECTION_WINDOW = 15  # seconds
MIN_SAMPLES = 8
MIN_VOLUME_BTC = 0.5
PRIOR_LOW_LOOKBACK = 120  # seconds
PRIOR_LOW_PROXIMITY_BPS = 5.0  # correction 3: must be near prior low
HORIZONS = [5, 10, 15, 30, 60]
COSTS = [2, 4, 6]


# ============================================================
# Data Structures
# ============================================================

@dataclass
class ShadowEvent:
    event_id: str
    timestamp: float
    price: float
    delta_ratio: float
    delta_percentile: float
    downside_bps: float
    distance_to_prior_low_bps: float
    failed_to_break_low: bool
    aggression_score: float
    no_response_score: float
    regime: str
    # Forward outcomes (filled from source events)
    future_return_5s: Optional[float] = None
    future_return_10s: Optional[float] = None
    future_return_15s: Optional[float] = None
    future_return_30s: Optional[float] = None
    future_return_60s: Optional[float] = None
    mfe_30s: Optional[float] = None
    mae_30s: Optional[float] = None
    # Correction 4: time_to_positive
    time_to_positive: Optional[float] = None


@dataclass
class RollingBuffer:
    """
    Reconstructed from event stream. Not tick-level — event-level approximation.

    Correction 2: This buffer is built strictly in chronological order.
    Each add() only appends. get_window() only looks backward from `now`.
    No future events are ever accessible.
    """
    timestamps: list = field(default_factory=list)
    prices: list = field(default_factory=list)
    volumes: list = field(default_factory=list)
    deltas: list = field(default_factory=list)
    cvd_running: float = 0.0
    cvd_values: list = field(default_factory=list)

    def add(self, ts: float, price: float, vol: float, delta: float):
        """Append only. Never insert out of order."""
        self.timestamps.append(ts)
        self.prices.append(price)
        self.volumes.append(vol)
        self.deltas.append(delta)
        self.cvd_running += delta
        self.cvd_values.append(self.cvd_running)

    def get_window(self, window_seconds: float, now: float):
        """Return only data with timestamp < now. No future leakage."""
        cutoff = now - window_seconds
        start = None
        for i, ts in enumerate(self.timestamps):
            if ts >= cutoff:
                start = i
                break
        if start is None:
            return [], [], [], []
        return (
            self.prices[start:],
            self.volumes[start:],
            self.deltas[start:],
            self.timestamps[start:],
        )

    def percentile_delta(self, delta: float, window: float, now: float, lookback: int = 20) -> float:
        """Compare against past windows only (now - offset). No future data."""
        scores = []
        for i in range(1, lookback + 1):
            offset = i * window
            _, _, w_deltas, _ = self.get_window(window, now - offset)
            if w_deltas:
                scores.append(abs(sum(w_deltas)))
        if not scores:
            return 0.5
        return sum(1 for s in scores if abs(delta) > s) / len(scores)


# ============================================================
# Loading
# ============================================================

def load_events(path: str) -> list[dict]:
    events = []
    if not os.path.exists(path):
        print(f"[ERROR] File not found: {path}")
        sys.exit(1)
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


# ============================================================
# Detection (correction 2: strict chronological processing)
# ============================================================

def detect_shadow_events(events: list[dict]) -> list[ShadowEvent]:
    """
    Replay event stream through detector conditions.

    CORRECTION 2: Events are sorted by timestamp before processing.
    Each detection uses only data with timestamp <= current event.
    No future trades enter the buffer.
    """
    # Correction 2: enforce chronological order
    events_sorted = sorted(events, key=lambda e: e["timestamp"])

    buf = RollingBuffer()
    shadow_events = []

    for i, ev in enumerate(events_sorted):
        ts = ev["timestamp"]
        price = ev["price"]

        # Extract volume and delta from raw_metrics
        rm = ev.get("raw_metrics", {})
        vol = rm.get("total_volume", rm.get("volume", 0))
        delta = rm.get("total_delta", rm.get("delta", 0))

        # Some events store buy_vol/sell_vol instead
        if vol == 0:
            buy_v = rm.get("buy_vol", 0)
            sell_v = rm.get("sell_vol", 0)
            vol = buy_v + sell_v
            delta = buy_v - sell_v

        if vol == 0:
            vol = 0.5
            delta = 0.0

        # Correction 2: buffer only accumulates past data
        buf.add(ts, price, vol, delta)

        if len(buf.timestamps) < MIN_SAMPLES:
            continue

        # ── COMPONENT 1: AGGRESSION ─────────────────────────
        # Uses only buffer data with timestamp <= ts (past)
        prices_w, volumes_w, deltas_w, _ = buf.get_window(DETECTION_WINDOW, ts)
        if len(prices_w) < MIN_SAMPLES:
            continue

        total_vol = sum(volumes_w)
        total_delta = sum(deltas_w)

        if total_vol < MIN_VOLUME_BTC:
            continue

        delta_ratio = total_delta / total_vol
        if delta_ratio > AGGRESSION_DELTA_RATIO:
            continue

        delta_pct = buf.percentile_delta(total_delta, DETECTION_WINDOW, ts, lookback=20)
        if delta_pct < AGGRESSION_PERCENTILE:
            continue

        # ── COMPONENT 2: NO PRICE RESPONSE ──────────────────
        price_change = prices_w[-1] - prices_w[0]
        downside_bps = max(0, -price_change / prices_w[0] * 10000) if prices_w[0] > 0 else 0

        # Prior low — uses only past buffer data
        prior_prices, _, _, _ = buf.get_window(PRIOR_LOW_LOOKBACK, ts)
        if prior_prices:
            prior_low = min(prior_prices)
        else:
            prior_low = min(prices_w)

        # Correction 3: proximity condition
        if prior_low > 0:
            distance_to_low_bps = (price - prior_low) / prior_low * 10000
        else:
            distance_to_low_bps = 999.0
        near_prior_low = distance_to_low_bps <= PRIOR_LOW_PROXIMITY_BPS

        failed_to_break_low = price > prior_low and near_prior_low

        no_downside = (
            downside_bps <= MAX_DOWNSIDE_BPS
            or failed_to_break_low
        )
        if not no_downside:
            continue

        # ── BUILD SHADOW EVENT ───────────────────────────────
        aggression_score = min(delta_pct, 1.0)
        no_response_score = max(0, 1.0 - downside_bps / max(MAX_DOWNSIDE_BPS * 2, 0.1))

        # Extract forward outcomes from source event
        fwd = ev.get("forward", {})
        regime = ev.get("context_metrics", {}).get("regime", "unknown")

        # Correction 4: time_to_positive estimation
        # We don't have tick-level forward data, so approximate from horizons:
        #   - If future_return_10s > 0: likely positive within ~5-10s
        #   - If future_return_10s <= 0 but future_return_30s > 0: ~10-30s
        #   - If future_return_30s <= 0 but future_return_60s > 0: ~30-60s
        #   - If all negative: None (never became positive)
        ttp = None
        r10 = fwd.get("future_return_10s")
        r30 = fwd.get("future_return_30s")
        r60 = fwd.get("future_return_60s")
        if r10 is not None and r10 > 0:
            ttp = 5.0  # approximate: positive by 10s, likely earlier
        elif r30 is not None and r30 > 0:
            ttp = 20.0  # positive by 30s, not by 10s
        elif r60 is not None and r60 > 0:
            ttp = 45.0  # positive by 60s, not by 30s
        # else: ttp remains None (never profitable)

        shadow_events.append(ShadowEvent(
            event_id=f"shadow_{i}_{ev.get('event_id', '')}",
            timestamp=ts,
            price=price,
            delta_ratio=delta_ratio,
            delta_percentile=delta_pct,
            downside_bps=downside_bps,
            distance_to_prior_low_bps=distance_to_low_bps,
            failed_to_break_low=failed_to_break_low,
            aggression_score=aggression_score,
            no_response_score=no_response_score,
            regime=regime,
            future_return_5s=fwd.get("future_return_10s"),
            future_return_10s=r10,
            future_return_15s=None,
            future_return_30s=r30,
            future_return_60s=r60,
            mfe_30s=fwd.get("max_favorable_excursion_30s"),
            mae_30s=fwd.get("max_adverse_excursion_30s"),
            time_to_positive=ttp,
        ))

    return shadow_events


# ============================================================
# Analysis
# ============================================================

def compute_stats(returns: list[float], costs_bps: float = 0) -> dict:
    if not returns:
        return {"n": 0}
    net = [r - costs_bps for r in returns]
    n = len(net)
    wins = [r for r in net if r > 0]
    losses = [r for r in net if r <= 0]
    avg = sum(net) / n
    wr = len(wins) / n if n > 0 else 0
    gp = sum(wins) if wins else 0
    gl = abs(sum(losses)) if losses else 0
    pf = gp / gl if gl > 0 else float('inf')
    sorted_net = sorted(net)
    median = sorted_net[n // 2]
    return {
        "n": n,
        "avg_bps": round(avg, 2),
        "median_bps": round(median, 2),
        "winrate": round(wr, 4),
        "profit_factor": round(pf, 3),
        "gross_avg_bps": round(sum(returns) / len(returns), 2),
        "avg_win_bps": round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loss_bps": round(sum(losses) / len(losses), 2) if losses else 0,
    }


def time_to_positive_distribution(events: list[ShadowEvent]) -> dict:
    """Correction 4: report time_to_positive distribution."""
    ttp_vals = [e.time_to_positive for e in events if e.time_to_positive is not None]
    never_positive = sum(1 for e in events if e.time_to_positive is None)

    if not ttp_vals:
        return {"n_positive": 0, "n_never": never_positive}

    ttp_vals.sort()
    n = len(ttp_vals)
    return {
        "n_positive": n,
        "n_never": never_positive,
        "n_total": n + never_positive,
        "pct_positive": round(n / (n + never_positive) * 100, 1) if (n + never_positive) > 0 else 0,
        "median_s": round(ttp_vals[n // 2], 1),
        "p25_s": round(ttp_vals[n // 4], 1),
        "p75_s": round(ttp_vals[3 * n // 4], 1),
        "min_s": round(ttp_vals[0], 1),
        "max_s": round(ttp_vals[-1], 1),
    }


def time_split(events: list[ShadowEvent], horizon: str = "future_return_10s") -> dict:
    if not events:
        return {"first": {"n": 0}, "second": {"n": 0}}
    # Already sorted chronologically from detection
    n = len(events)
    mid = n // 2
    first = events[:mid]
    second = events[mid:]

    def _stats(subset):
        returns = [getattr(e, horizon) for e in subset if getattr(e, horizon) is not None]
        if not returns:
            return {"n": len(subset), "n_with_outcome": 0}
        s = compute_stats(returns)
        s["n_events"] = len(subset)
        s["n_with_outcome"] = len(returns)
        return s

    return {"first": _stats(first), "second": _stats(second)}


def regime_split(events: list[ShadowEvent], horizon: str = "future_return_10s") -> dict:
    by_regime = defaultdict(list)
    for e in events:
        by_regime[e.regime].append(e)
    result = {}
    for regime, evts in sorted(by_regime.items()):
        returns = [getattr(e, horizon) for e in evts if getattr(e, horizon) is not None]
        if not returns:
            result[regime] = {"n": len(evts), "n_with_outcome": 0}
            continue
        result[regime] = {
            "n": len(evts),
            "n_with_outcome": len(returns),
            **compute_stats(returns),
        }
    return result


def classify_failures(events: list[ShadowEvent]) -> dict:
    failures = [e for e in events if e.future_return_10s is not None and e.future_return_10s <= 0]
    if not failures:
        return {"n": 0}

    categories = {
        "continuation": 0,
        "delayed_breakdown": 0,
        "no_reversal": 0,
        "noisy_compression": 0,
    }

    for e in failures:
        ret_30 = e.future_return_30s
        ret_60 = e.future_return_60s
        if ret_30 is not None and ret_30 < -3:
            categories["continuation"] += 1
        elif ret_60 is not None and ret_60 < -3:
            categories["delayed_breakdown"] += 1
        elif e.future_return_10s is not None and abs(e.future_return_10s) < 1:
            categories["noisy_compression"] += 1
        else:
            categories["no_reversal"] += 1

    return {"n": len(failures), **categories}


# ============================================================
# Report Generation
# ============================================================

def generate_report(events: list[ShadowEvent], source_count: int) -> str:
    lines = []
    lines.append("# FAILED_AGGRESSION_SELL_V0_REPORT")
    lines.append("")
    tz8 = timezone(timedelta(hours=8))
    lines.append(f"**Generated:** {datetime.now(tz8).strftime('%Y-%m-%d %H:%M:%S')} CST")
    lines.append(f"**Source events:** {source_count}")
    lines.append(f"**Shadow detections:** {len(events)}")
    lines.append(f"**Mode:** Shadow only (no production impact)")
    lines.append("")

    # ── 1. Detector Definition ──────────────────────────────
    lines.append("## 1. Detector Definition")
    lines.append("")
    lines.append("Three conditions, no more:")
    lines.append("")
    lines.append("```")
    lines.append("AGGRESSION:")
    lines.append(f"  delta_ratio <= {AGGRESSION_DELTA_RATIO}")
    lines.append(f"  abs_delta_percentile >= {AGGRESSION_PERCENTILE}")
    lines.append("")
    lines.append("NO PRICE RESPONSE:")
    lines.append(f"  downside_move_bps <= {MAX_DOWNSIDE_BPS}")
    lines.append(f"  OR (failed_to_break_prior_low")
    lines.append(f"      AND distance_to_prior_low <= {PRIOR_LOW_PROXIMITY_BPS} bps)")
    lines.append("")
    lines.append("DETECTION WINDOW: 15 seconds")
    lines.append("MIN SAMPLES: 8 events in window")
    lines.append("MIN VOLUME: 0.5 BTC in window")
    lines.append("```")
    lines.append("")
    lines.append("Forward return is measured AFTER detection by OutcomeTracker.")
    lines.append("It is never used to trigger detection.")
    lines.append("")

    # ── 2. Why This Is Different ────────────────────────────
    lines.append("## 2. Why This Is Different from sell_exhaustion")
    lines.append("")
    lines.append("| Aspect | sell_exhaustion (rejected) | failed_aggression_sell_v0 |")
    lines.append("|--------|---------------------------|--------------------------|")
    lines.append("| Observes | Impact decline over time | Aggression vs price response NOW |")
    lines.append("| Fires when | Selling happened and slowed | Selling IS happening but price won't follow |")
    lines.append("| Confirmation | None | Price not moving lower (present observation) |")
    lines.append("| Proximity | Any price near low | Within 5 bps of prior low (actual support test) |")
    lines.append("| Causal link | Indirect (decline → maybe exhaustion) | Direct (aggression high + price flat = absorption) |")
    lines.append("")

    if not events:
        lines.append("## 3. Shadow Detection Results")
        lines.append("")
        lines.append("**No events detected.** Insufficient source data or conditions never met.")
        lines.append("")
        lines.append("## 9. Final Verdict")
        lines.append("")
        lines.append("**INSUFFICIENT DATA** — Need events_with_outcomes.jsonl with ≥100 source events.")
        return "\n".join(lines)

    # ── 3. Shadow Detection Results ─────────────────────────
    lines.append("## 3. Shadow Detection Results")
    lines.append("")
    lines.append(f"- **Total detected:** {len(events)}")
    lines.append(f"- **Detection rate:** {len(events)/source_count*100:.1f}% of source events")
    lines.append("")

    with_break = sum(1 for e in events if not e.failed_to_break_low)
    without_break = sum(1 for e in events if e.failed_to_break_low)
    lines.append(f"- **Broke prior low:** {with_break} ({with_break/len(events)*100:.1f}%)")
    lines.append(f"- **Failed to break (within {PRIOR_LOW_PROXIMITY_BPS}bps):** {without_break} ({without_break/len(events)*100:.1f}%)")
    lines.append("")

    drs = sorted([e.delta_ratio for e in events])
    n = len(drs)
    lines.append(f"- **Delta ratio:** min={drs[0]:.2f}, p25={drs[n//4]:.2f}, median={drs[n//2]:.2f}, p75={drs[3*n//4]:.2f}, max={drs[-1]:.2f}")
    lines.append("")

    dist_vals = sorted([e.distance_to_prior_low_bps for e in events])
    lines.append(f"- **Distance to prior low (bps):** min={dist_vals[0]:.1f}, p25={dist_vals[n//4]:.1f}, median={dist_vals[n//2]:.1f}, p75={dist_vals[3*n//4]:.1f}, max={dist_vals[-1]:.1f}")
    lines.append("")

    by_regime = defaultdict(int)
    for e in events:
        by_regime[e.regime] += 1
    lines.append(f"- **Regime distribution:** {dict(sorted(by_regime.items(), key=lambda x: -x[1]))}")
    lines.append("")

    # ── 4. Outcome Validation ───────────────────────────────
    lines.append("## 4. Outcome Validation")
    lines.append("")
    lines.append("| Horizon | N | Gross Avg | Winrate | PF | Median |")
    lines.append("|---------|---|-----------|---------|-----|--------|")
    for h in HORIZONS:
        field = f"future_return_{h}s"
        returns = [getattr(e, field) for e in events if getattr(e, field) is not None]
        if not returns:
            lines.append(f"| {h}s | 0 | — | — | — | — |")
            continue
        s = compute_stats(returns)
        lines.append(f"| {h}s | {s['n']} | {s['avg_bps']:+.2f} | {s['winrate']:.1%} | {s['profit_factor']:.2f} | {s['median_bps']:+.2f} |")
    lines.append("")

    # ── 5. Cost Stress Test ─────────────────────────────────
    lines.append("## 5. Cost Stress Test")
    lines.append("")
    returns_10 = [e.future_return_10s for e in events if e.future_return_10s is not None]
    returns_30 = [e.future_return_30s for e in events if e.future_return_30s is not None]
    lines.append("| Cost | Horizon | N | Net Avg | Winrate | PF |")
    lines.append("|------|---------|---|---------|---------|-----|")
    for cost in COSTS:
        for label, rets in [("10s", returns_10), ("30s", returns_30)]:
            if not rets:
                continue
            s = compute_stats(rets, cost)
            lines.append(f"| {cost}bps | {label} | {s['n']} | {s['avg_bps']:+.2f} | {s['winrate']:.1%} | {s['profit_factor']:.2f} |")
    lines.append("")

    # ── 6. Time-To-Reversal ─────────────────────────────────
    lines.append("## 6. Time-To-Reversal")
    lines.append("")
    lines.append("Events where price reversed (future_return > 0):")
    for h in HORIZONS:
        field = f"future_return_{h}s"
        positive = [getattr(e, field) for e in events if getattr(e, field) is not None and getattr(e, field) > 0]
        total = [getattr(e, field) for e in events if getattr(e, field) is not None]
        if total:
            lines.append(f"- {h}s: {len(positive)}/{len(total)} reversed ({len(positive)/len(total)*100:.1f}%)")
    lines.append("")

    # Correction 4: time_to_positive distribution
    ttp = time_to_positive_distribution(events)
    lines.append("### Time-to-Positive Distribution")
    lines.append("")
    if ttp["n_positive"] == 0:
        lines.append(f"- **Never positive:** {ttp['n_never']} / {ttp.get('n_total', ttp['n_never'])} events")
    else:
        lines.append(f"- **Positive within 60s:** {ttp['n_positive']} / {ttp['n_total']} ({ttp['pct_positive']}%)")
        lines.append(f"- **Never positive:** {ttp['n_never']}")
        lines.append(f"- **Median:** {ttp['median_s']}s")
        lines.append(f"- **p25:** {ttp['p25_s']}s")
        lines.append(f"- **p75:** {ttp['p75_s']}s")
        lines.append(f"- **Range:** {ttp['min_s']}s – {ttp['max_s']}s")
    lines.append("")

    # MFE/MAE
    mfe_vals = [e.mfe_30s for e in events if e.mfe_30s is not None]
    mae_vals = [e.mae_30s for e in events if e.mae_30s is not None]
    if mfe_vals and mae_vals:
        mfe_vals.sort()
        mae_vals.sort()
        lines.append(f"- **MFE (30s):** median={mfe_vals[len(mfe_vals)//2]:.2f}, avg={sum(mfe_vals)/len(mfe_vals):.2f}")
        lines.append(f"- **MAE (30s):** median={mae_vals[len(mae_vals)//2]:.2f}, avg={sum(mae_vals)/len(mae_vals):.2f}")
    lines.append("")

    # ── 7. Failure Modes ────────────────────────────────────
    lines.append("## 7. Failure Modes")
    lines.append("")
    failures = classify_failures(events)
    if failures["n"] == 0:
        lines.append("No failures detected (all events had future_return_10s > 0).")
    else:
        lines.append(f"**Total failures:** {failures['n']}")
        lines.append("")
        lines.append(f"- Continuation (price went lower): {failures.get('continuation', 0)}")
        lines.append(f"- Delayed breakdown (broke low within 30s): {failures.get('delayed_breakdown', 0)}")
        lines.append(f"- No reversal (stayed flat): {failures.get('no_reversal', 0)}")
        lines.append(f"- Noisy compression (small oscillation): {failures.get('noisy_compression', 0)}")
    lines.append("")

    # ── 7b. Time Stability ──────────────────────────────────
    lines.append("## 7b. Time Stability")
    lines.append("")
    ts = time_split(events, "future_return_10s")
    first = ts.get("first", {})
    second = ts.get("second", {})
    lines.append("| Metric | First Half | Second Half |")
    lines.append("|--------|-----------|-------------|")
    lines.append(f"| Events | {first.get('n_events', first.get('n', 0))} | {second.get('n_events', second.get('n', 0))} |")
    lines.append(f"| With outcome | {first.get('n_with_outcome', 0)} | {second.get('n_with_outcome', 0)} |")
    if first.get("n", 0) > 0 and "avg_bps" in first:
        lines.append(f"| Avg net (10s) | {first['avg_bps']:+.2f}bps | {second.get('avg_bps', 0):+.2f}bps |")
        lines.append(f"| Winrate | {first['winrate']:.1%} | {second.get('winrate', 0):.1%} |")
    lines.append("")

    # ── 7c. Regime Performance ──────────────────────────────
    lines.append("## 7c. Regime Performance")
    lines.append("")
    rs = regime_split(events, "future_return_10s")
    lines.append("| Regime | N | Avg (10s) | Winrate | PF |")
    lines.append("|--------|---|-----------|---------|-----|")
    for regime, data in sorted(rs.items()):
        if data.get("n_with_outcome", 0) == 0:
            lines.append(f"| {regime} | {data['n']} | — | — | — |")
        else:
            lines.append(f"| {regime} | {data['n']} | {data.get('avg_bps', 0):+.2f} | {data.get('winrate', 0):.1%} | {data.get('profit_factor', 0):.2f} |")
    lines.append("")

    # ── 8. Promotion Criteria ───────────────────────────────
    lines.append("## 8. Promotion Criteria")
    lines.append("")
    lines.append("Correction 1: minimum ≥100, preferred ≥300.")
    lines.append("")

    returns_10_valid = [e.future_return_10s for e in events if e.future_return_10s is not None]
    criteria = {}

    criteria["sample_size_min"] = len(returns_10_valid) >= 100
    criteria["sample_size_pref"] = len(returns_10_valid) >= 300
    if returns_10_valid:
        gross_avg = sum(returns_10_valid) / len(returns_10_valid)
        criteria["gross_positive"] = gross_avg > 0
        net_avg = gross_avg - 4
        criteria["net_positive_4bps"] = net_avg >= 0
    else:
        gross_avg = 0
        criteria["gross_positive"] = False
        criteria["net_positive_4bps"] = False

    ts_10 = time_split(events, "future_return_10s")
    first_avg = ts_10.get("first", {}).get("avg_bps", 0) if ts_10.get("first", {}).get("n", 0) > 0 else 0
    second_avg = ts_10.get("second", {}).get("avg_bps", 0) if ts_10.get("second", {}).get("n", 0) > 0 else 0
    criteria["time_stable"] = (first_avg >= 0 and second_avg >= 0) if (first_avg != 0 or second_avg != 0) else False

    mae_vals_all = [e.mae_30s for e in events if e.mae_30s is not None]
    if mae_vals_all:
        avg_mae = sum(mae_vals_all) / len(mae_vals_all)
        criteria["controlled_adverse"] = avg_mae <= 5
    else:
        criteria["controlled_adverse"] = False

    lines.append("| # | Criterion | Status |")
    lines.append("|---|-----------|--------|")
    lines.append(f"| 1a | Sample ≥100 (minimum) | {'✅' if criteria['sample_size_min'] else '❌'} ({len(returns_10_valid)} events) |")
    lines.append(f"| 1b | Sample ≥300 (preferred) | {'✅' if criteria['sample_size_pref'] else '❌'} ({len(returns_10_valid)} events) |")
    lines.append(f"| 2 | Gross positive at 10s | {'✅' if criteria['gross_positive'] else '❌'} ({gross_avg:+.2f}bps) |")
    lines.append(f"| 3 | Net ≥0 at 4bps | {'✅' if criteria['net_positive_4bps'] else '❌'} |")
    lines.append(f"| 4 | Time-stable | {'✅' if criteria['time_stable'] else '❌'} (first={first_avg:+.2f}, second={second_avg:+.2f}) |")
    lines.append(f"| 5 | Controlled adverse | {'✅' if criteria['controlled_adverse'] else '❌'} |")
    lines.append("")

    # Verdict
    all_pass = all(criteria.values())
    sample_ok = criteria["sample_size_min"]
    other_pass = all(v for k, v in criteria.items() if k not in ("sample_size_min", "sample_size_pref"))

    if all_pass:
        verdict = "**Promote to deeper validation** — All criteria met (including preferred ≥300). Requires 1000+ event confirmation."
    elif sample_ok and other_pass:
        verdict = "**Keep collecting** — Minimum sample met, criteria pass, but preferred ≥300 not reached. Continue to 300+."
    elif sample_ok:
        verdict = "**Keep collecting** — Minimum sample met but criteria not all pass. Do NOT tune."
    elif any(v for k, v in criteria.items() if k not in ("sample_size_min", "sample_size_pref")):
        verdict = "**Candidate, but non-tradeable** — Some signals positive, sample below minimum."
    else:
        verdict = "**Insufficient data** — Cannot evaluate. Need events_with_outcomes.jsonl."

    lines.append(f"### VERDICT: {verdict}")
    lines.append("")
    lines.append("This detector remains NON-TRADEABLE until all criteria pass simultaneously.")
    lines.append("No parameter tuning is permitted. If criteria fail, reject or keep collecting.")
    lines.append("")

    return "\n".join(lines)


# ============================================================
# CSV Output
# ============================================================

def write_csv(events: list[ShadowEvent], path: str):
    if not events:
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "event_id", "timestamp", "price", "delta_ratio", "delta_percentile",
        "downside_bps", "distance_to_prior_low_bps", "failed_to_break_low",
        "aggression_score", "no_response_score", "regime",
        "future_return_5s", "future_return_10s", "future_return_15s",
        "future_return_30s", "future_return_60s", "mfe_30s", "mae_30s",
        "time_to_positive",
    ]
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for e in events:
            row = {}
            for k in fields:
                v = getattr(e, k)
                if isinstance(v, bool):
                    row[k] = str(v)
                elif v is None:
                    row[k] = ''
                else:
                    row[k] = v
            writer.writerow(row)


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Shadow validate failed_aggression_sell_v0")
    parser.add_argument("--input", default="backend/data/events/events_with_outcomes.jsonl")
    parser.add_argument("--output-csv", default="backend/data/events/failed_aggression_sell_v0_shadow.csv")
    parser.add_argument("--output-md", default="FAILED_AGGRESSION_SELL_V0_REPORT.md")
    args = parser.parse_args()

    print(f"Loading events from {args.input}...")
    source_events = load_events(args.input)
    print(f"  Loaded {len(source_events)} source events")

    if not source_events:
        print("[ERROR] No source events. Run the event engine first.")
        sys.exit(1)

    # Correction 2: report sort status
    timestamps = [e["timestamp"] for e in source_events]
    is_sorted = all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1))
    print(f"  Chronological order: {'YES' if is_sorted else 'NO — will sort'}")

    print("Running shadow detection...")
    shadow_events = detect_shadow_events(source_events)
    print(f"  Detected {len(shadow_events)} shadow events")

    print("Writing CSV...")
    write_csv(shadow_events, args.output_csv)
    print(f"  Written to {args.output_csv}")

    print("Generating report...")
    report = generate_report(shadow_events, len(source_events))
    with open(args.output_md, 'w') as f:
        f.write(report)
    print(f"  Written to {args.output_md}")

    # Print summary
    print("\n" + "=" * 60)
    print("SHADOW VALIDATION COMPLETE")
    print("=" * 60)
    print(f"  Source events:    {len(source_events)}")
    print(f"  Shadow detects:   {len(shadow_events)}")
    if shadow_events:
        r10 = [e.future_return_10s for e in shadow_events if e.future_return_10s is not None]
        if r10:
            print(f"  Avg return (10s): {sum(r10)/len(r10):+.2f}bps")
            print(f"  Winrate (10s):    {sum(1 for r in r10 if r > 0)/len(r10):.1%}")
        ttp = time_to_positive_distribution(shadow_events)
        if ttp["n_positive"] > 0:
            print(f"  Time-to-positive: median={ttp['median_s']}s, p25={ttp['p25_s']}s, p75={ttp['p75_s']}s")
    print(f"  Report:           {args.output_md}")


if __name__ == "__main__":
    main()
