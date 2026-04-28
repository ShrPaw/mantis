"""
Funding / Positioning Pressure Research — Single-file Analysis

Hypothesis: extreme funding rates create exploitable price behavior
(mean reversion or continuation).

Reads: btcusdt_funding.csv + btcusdt_1m.csv
Outputs: FUNDING_POSITIONING_REPORT.md

No tuning. No ML. No optimization. Fixed definitions.

Usage:
  python3 -m research.funding_positioning.analyze
"""

import argparse
import csv
import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

# ============================================================
# FIXED CONFIGURATION
# ============================================================

FUNDING_LOOKBACK_HOURS = 24       # rolling window for funding stats
FUNDING_EXTREME_STD = 2.0         # mean ± 2*std = extreme
PERSISTENCE_INTERVALS = [1, 2, 3] # consecutive funding intervals (each = 8h)

OUTCOME_HORIZONS_HOURS = [1, 4, 8, 24, 48]
COST_LEVELS_BPS = [2, 4, 6]
PRIMARY_COST_BPS = 4

MIN_OCCURRENCES = 100
MIN_PROFIT_FACTOR = 1.10
MAX_OUTLIER_DEPENDENCE = 0.30


# ============================================================
# DATA LOADING
# ============================================================
@dataclass
class FundingRecord:
    timestamp: float
    rate: float


@dataclass
class Bar:
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float


def load_funding(path):
    records = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                records.append(FundingRecord(
                    timestamp=float(row["timestamp"]),
                    rate=float(row["funding_rate"]),
                ))
            except (ValueError, KeyError):
                continue
    records.sort(key=lambda r: r.timestamp)
    return records


def load_bars(path):
    bars = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                bars.append(Bar(
                    timestamp=float(row["timestamp"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                ))
            except (ValueError, KeyError):
                continue
    bars.sort(key=lambda b: b.timestamp)
    return bars


# ============================================================
# FUNDING EXTREME DETECTION
# ============================================================
@dataclass
class FundingEvent:
    eid: str
    event_type: str        # "long_crowded" or "short_crowded"
    timestamp: float
    funding_rate: float
    rolling_mean: float
    rolling_std: float
    z_score: float
    persistence: int       # consecutive intervals at extreme
    # Outcomes
    fwd: dict = field(default_factory=dict)
    fwd_net: dict = field(default_factory=dict)
    mfe: float = 0.0
    mae: float = 0.0
    ttp: Optional[float] = None


def detect_funding_extremes(records):
    """
    Detect funding rate extremes using rolling z-scores.

    LONG CROWDED: funding > mean + 2*std (positive extreme — longs pay shorts)
    SHORT CROWDED: funding < mean - 2*std (negative extreme — shorts pay longs)
    """
    events = []
    counter = 0

    # Funding is every 8h, so lookback in records
    lookback = FUNDING_LOOKBACK_HOURS // 8  # 3 intervals for 24h

    for i in range(lookback, len(records)):
        # Compute rolling stats
        window = [records[j].rate for j in range(i - lookback, i)]
        mean = sum(window) / len(window)
        std = (sum((r - mean)**2 for r in window) / len(window)) ** 0.5

        if std < 1e-10:
            continue

        cur = records[i]
        z = (cur.rate - mean) / std

        # Check persistence (how many consecutive intervals at extreme)
        persistence = 1
        if z > FUNDING_EXTREME_STD:
            for p in range(1, min(4, i + 1)):
                if i - p >= 0:
                    prev_z = (records[i-p].rate - mean) / std
                    if prev_z > FUNDING_EXTREME_STD:
                        persistence += 1
                    else:
                        break
        elif z < -FUNDING_EXTREME_STD:
            for p in range(1, min(4, i + 1)):
                if i - p >= 0:
                    prev_z = (records[i-p].rate - mean) / std
                    if prev_z < -FUNDING_EXTREME_STD:
                        persistence += 1
                    else:
                        break

        # Create events for each persistence threshold
        for min_persist in PERSISTENCE_INTERVALS:
            if persistence >= min_persist:
                if z > FUNDING_EXTREME_STD:
                    counter += 1
                    events.append(FundingEvent(
                        eid=f"f{counter:06d}",
                        event_type="long_crowded",
                        timestamp=cur.timestamp,
                        funding_rate=cur.rate,
                        rolling_mean=mean,
                        rolling_std=std,
                        z_score=z,
                        persistence=persistence,
                    ))
                elif z < -FUNDING_EXTREME_STD:
                    counter += 1
                    events.append(FundingEvent(
                        eid=f"f{counter:06d}",
                        event_type="short_crowded",
                        timestamp=cur.timestamp,
                        funding_rate=cur.rate,
                        rolling_mean=mean,
                        rolling_std=std,
                        z_score=z,
                        persistence=persistence,
                    ))

    return events


# ============================================================
# OUTCOME MEASUREMENT
# ============================================================
def find_closest_bar(bars, target_ts):
    """Binary search for closest bar to target timestamp."""
    lo, hi = 0, len(bars) - 1
    best = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        if abs(bars[mid].timestamp - target_ts) < abs(bars[best].timestamp - target_ts):
            best = mid
        if bars[mid].timestamp < target_ts:
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def measure_outcomes(events, bars):
    """Measure forward returns for funding events."""
    if not bars:
        return

    max_h = max(OUTCOME_HORIZONS_HOURS) * 3600

    for ev in events:
        # Find entry bar (closest to event timestamp)
        entry_idx = find_closest_bar(bars, ev.timestamp)
        entry_px = bars[entry_idx].close
        if entry_px <= 0:
            continue

        end_idx = find_closest_bar(bars, ev.timestamp + max_h + 3600)

        for i in range(entry_idx, min(end_idx + 1, len(bars))):
            bar = bars[i]
            elapsed_s = bar.timestamp - ev.timestamp
            elapsed_h = elapsed_s / 3600

            # For funding events:
            # LONG CROWDED (positive funding) → expect mean reversion DOWN
            # SHORT CROWDED (negative funding) → expect mean reversion UP
            # Test BOTH hypotheses:
            # H1 (mean reversion): long_crowded → short, short_crowded → long
            # H2 (continuation): long_crowded → long, short_crowded → short

            if ev.event_type == "long_crowded":
                # Mean reversion: price should fall
                reversion_ret = ((entry_px - bar.close) / entry_px) * 10000
                # Continuation: price should rise
                continuation_ret = ((bar.close - entry_px) / entry_px) * 10000
            else:
                # Mean reversion: price should rise
                reversion_ret = ((bar.close - entry_px) / entry_px) * 10000
                # Continuation: price should fall
                continuation_ret = ((entry_px - bar.close) / entry_px) * 10000

            # MFE/MAE for mean reversion hypothesis
            if ev.event_type == "long_crowded":
                high_ret = ((entry_px - bar.low) / entry_px) * 10000   # best for short
                low_ret = ((entry_px - bar.high) / entry_px) * 10000   # worst for short
            else:
                high_ret = ((bar.high - entry_px) / entry_px) * 10000  # best for long
                low_ret = ((bar.low - entry_px) / entry_px) * 10000    # worst for long

            ev.mfe = max(ev.mfe, high_ret)
            ev.mae = min(ev.mae, low_ret)

            for h in OUTCOME_HORIZONS_HOURS:
                if elapsed_h >= h and h not in ev.fwd:
                    ev.fwd[h] = {
                        "reversion": reversion_ret,
                        "continuation": continuation_ret,
                    }
                    for c in COST_LEVELS_BPS:
                        ev.fwd_net[(h, c)] = {
                            "reversion": reversion_ret - c,
                            "continuation": continuation_ret - c,
                        }

            if ev.ttp is None and reversion_ret > 0:
                ev.ttp = elapsed_h


# ============================================================
# BASELINES
# ============================================================
def compute_baselines(bars, events):
    import random
    random.seed(42)

    if len(bars) < 100 or not events:
        return {}

    n_samples = min(5000, len(events) * 10)
    horizons = OUTCOME_HORIZONS_HOURS
    max_h_s = max(horizons) * 3600

    bar_times = [(b.timestamp, b.close) for b in bars]
    bar_times.sort(key=lambda x: x[0])

    def forward_return(entry_ts, entry_px, direction, horizon_h):
        target_ts = entry_ts + horizon_h * 3600
        idx = find_closest_bar(bars, target_ts)
        exit_px = bars[idx].close
        if entry_px <= 0:
            return 0.0
        if direction == "long":
            return ((exit_px - entry_px) / entry_px) * 10000
        else:
            return ((entry_px - exit_px) / entry_px) * 10000

    # Baseline A: Random timestamps
    baselines = {"random": {h: [] for h in horizons}}
    valid_bars = [(t, p) for t, p in bar_times if t < bar_times[-1][0] - max_h_s]
    if valid_bars:
        for _ in range(n_samples):
            ts, px = random.choice(valid_bars)
            d = random.choice(["long", "short"])
            for h in horizons:
                baselines["random"][h].append(forward_return(ts, px, d, h))

    # Baseline B: Same volatility
    baselines["same_vol"] = {h: [] for h in horizons}
    # Use 24h realized vol as proxy
    vol_cache = {}
    for i in range(1440, len(bars)):
        prices = [bars[j].close for j in range(i-1440, i)]
        rets = []
        for k in range(1, len(prices)):
            if prices[k-1] > 0:
                rets.append(math.log(prices[k] / prices[k-1]))
        if rets:
            m = sum(rets) / len(rets)
            vol_cache[bars[i].timestamp] = (sum((r-m)**2 for r in rets) / len(rets)) ** 0.5

    event_vols = []
    for ev in events:
        closest = find_closest_bar(bars, ev.timestamp)
        if bars[closest].timestamp in vol_cache:
            event_vols.append(vol_cache[bars[closest].timestamp])

    if event_vols and vol_cache:
        vol_items = list(vol_cache.items())
        for _ in range(n_samples):
            target_vol = random.choice(event_vols)
            candidates = [(t, v) for t, v in vol_items if abs(v - target_vol) < target_vol * 0.5]
            if candidates:
                t, _ = random.choice(candidates)
                idx = find_closest_bar(bars, t)
                px = bars[idx].close
                d = random.choice(["long", "short"])
                for h in horizons:
                    baselines["same_vol"][h].append(forward_return(t, px, d, h))

    # Baseline C: Opposite hypothesis
    baselines["opposite"] = {h: [] for h in horizons}
    for ev in events:
        idx = find_closest_bar(bars, ev.timestamp)
        px = bars[idx].close
        # Test continuation (opposite of mean reversion)
        for h in horizons:
            if ev.event_type == "long_crowded":
                r = forward_return(ev.timestamp, px, "long", h)
            else:
                r = forward_return(ev.timestamp, px, "short", h)
            baselines["opposite"][h].append(r)

    # Compute means
    result = {}
    for name, data in baselines.items():
        result[name] = {}
        for h in horizons:
            vals = data[h]
            if vals:
                result[name][h] = {"mean": sum(vals)/len(vals), "count": len(vals)}
            else:
                result[name][h] = {"mean": 0, "count": 0}
    return result


# ============================================================
# ANALYTICS
# ============================================================
def safe_mean(xs):
    return sum(xs) / len(xs) if xs else 0

def safe_median(xs):
    if not xs:
        return 0
    s = sorted(xs)
    n = len(s)
    if n % 2:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2

def percentile(xs, p):
    if not xs:
        return 0
    s = sorted(xs)
    idx = int(len(s) * p / 100)
    return s[min(idx, len(s) - 1)]

def profit_factor(returns):
    gains = sum(r for r in returns if r > 0)
    losses = abs(sum(r for r in returns if r < 0))
    return gains / losses if losses > 0 else (999.0 if gains > 0 else 0.0)


def analyze_family(events, hypothesis="reversion", event_type="all", persistence_min=1):
    """Analyze funding events."""
    if event_type != "all":
        es = [e for e in events if e.event_type == event_type and e.persistence >= persistence_min]
    else:
        es = [e for e in events if e.persistence >= persistence_min]

    count = len(es)
    if count == 0:
        return None

    result = {"count": count, "hypothesis": hypothesis, "event_type": event_type, "persistence": persistence_min}

    for h in OUTCOME_HORIZONS_HOURS:
        gross = [e.fwd[h][hypothesis] for e in es if h in e.fwd]
        if not gross:
            continue
        result[f"gross_mean_{h}h"] = safe_mean(gross)
        result[f"gross_median_{h}h"] = safe_median(gross)
        result[f"worst5_{h}h"] = percentile(gross, 5)
        result[f"best5_{h}h"] = percentile(gross, 95)

        for c in COST_LEVELS_BPS:
            net = [e.fwd_net[(h, c)][hypothesis] for e in es if (h, c) in e.fwd_net]
            if not net:
                continue
            result[f"net_mean_{h}h_{c}bps"] = safe_mean(net)
            wins = [r for r in net if r > 0]
            result[f"winrate_{h}h_{c}bps"] = len(wins) / len(net) if net else 0
            result[f"pf_{h}h_{c}bps"] = profit_factor(net)

    mfes = [e.mfe for e in es if e.mfe > 0]
    maes = [e.mae for e in es if e.mae < 0]
    result["mean_mfe"] = safe_mean(mfes)
    result["mean_mae"] = safe_mean(maes)
    result["mfe_mae_ratio"] = abs(safe_mean(mfes) / safe_mean(maes)) if maes and safe_mean(maes) != 0 else 0

    ttps = [e.ttp for e in es if e.ttp is not None]
    result["median_ttp"] = safe_median(ttps)

    # Funding stats
    rates = [e.funding_rate for e in es]
    result["mean_funding_rate"] = safe_mean(rates)
    result["mean_z_score"] = safe_mean([e.z_score for e in es])

    # Outlier dependence
    for h in [4, 24]:
        gross = [e.fwd[h][hypothesis] for e in es if h in e.fwd]
        if len(gross) < 10:
            continue
        total_pnl = sum(gross)
        if total_pnl == 0:
            continue
        top5 = sorted(gross, reverse=True)[:max(1, len(gross) // 20)]
        result[f"outlier_dep_{h}h"] = sum(top5) / total_pnl if total_pnl > 0 else 0

    # Stability: halves
    es_sorted = sorted(es, key=lambda e: e.timestamp)
    mid = len(es_sorted) // 2
    for label, chunk in [("first_half", es_sorted[:mid]), ("second_half", es_sorted[mid:])]:
        for h in [4, 24]:
            gross = [e.fwd[h][hypothesis] for e in chunk if h in e.fwd]
            if gross:
                result[f"{label}_mean_{h}h"] = safe_mean(gross)

    # Quarterly stability
    if count >= 20:
        chunk_size = max(1, count // 4)
        for qi in range(4):
            chunk = es_sorted[qi*chunk_size:(qi+1)*chunk_size]
            for h in [24]:
                gross = [e.fwd[h][hypothesis] for e in chunk if h in e.fwd]
                if gross:
                    result[f"q{qi+1}_mean_{h}h"] = safe_mean(gross)
                    result[f"q{qi+1}_count"] = len(chunk)

    return result


def classify_failure(events, fam_reversion, fam_continuation):
    modes = []

    if not events:
        return ["No funding extreme events detected"]

    if fam_reversion is None and fam_continuation is None:
        return ["Insufficient events for analysis"]

    # Check which hypothesis (if any) has signal
    rev_24 = fam_reversion.get("gross_mean_24h", 0) if fam_reversion else 0
    con_24 = fam_continuation.get("gross_mean_24h", 0) if fam_continuation else 0

    if abs(rev_24) < 2 and abs(con_24) < 2:
        modes.append("Funding extremes not predictive — no directional signal")

    if fam_reversion and fam_reversion.get("pf_24h_4bps", 0) < 1:
        modes.append("Mean reversion exists but costs dominate")

    if fam_continuation and fam_continuation.get("pf_24h_4bps", 0) < 1:
        modes.append("Continuation exists but costs dominate")

    if fam_reversion and fam_continuation:
        if rev_24 > 0 and con_24 > 0:
            modes.append("Both hypotheses positive — likely noise, not real signal")
        elif rev_24 < 0 and con_24 < 0:
            modes.append("Both hypotheses negative — funding is not predictive")

    # Check long vs short asymmetry
    fam_rev_long = analyze_family(events, "reversion", "long_crowded")
    fam_rev_short = analyze_family(events, "reversion", "short_crowded")
    if fam_rev_long and fam_rev_short:
        rl = fam_rev_long.get("gross_mean_24h", 0)
        rs = fam_rev_short.get("gross_mean_24h", 0)
        if rl > 0 and rs <= 0:
            modes.append("Reversion only works for long-crowded (shorts have edge)")
        elif rl <= 0 and rs > 0:
            modes.append("Reversion only works for short-crowded (longs have edge)")

    if not modes:
        modes.append("Edge may exist — basic checks passed")

    return modes


def generate_report(events, baselines, bars, fam_rev, fam_con, fam_rev_long, fam_rev_short, fam_con_long, fam_con_short, failure_modes):
    lines = []
    lines.append("# FUNDING / POSITIONING PRESSURE REPORT")
    lines.append("")
    lines.append(f"**Date:** {time.strftime('%Y-%m-%d')}")
    lines.append(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # 1. Data Summary
    lines.append("## 1. Data Summary")
    lines.append("")
    duration_days = (bars[-1].timestamp - bars[0].timestamp) / 86400
    lines.append(f"- **Price data:** {len(bars):,} 1m bars ({duration_days:.0f} days)")
    lines.append(f"- **Period:** {time.strftime('%Y-%m-%d', time.gmtime(bars[0].timestamp))} to {time.strftime('%Y-%m-%d', time.gmtime(bars[-1].timestamp))} UTC")
    lines.append(f"- **Funding events:** {len(events)}")
    long_events = [e for e in events if e.event_type == "long_crowded"]
    short_events = [e for e in events if e.event_type == "short_crowded"]
    lines.append(f"  - Long crowded: {len(long_events)}")
    lines.append(f"  - Short crowded: {len(short_events)}")
    lines.append("")

    # 2. Event Definitions
    lines.append("## 2. Event Definitions")
    lines.append("")
    lines.append(f"- **Funding lookback:** {FUNDING_LOOKBACK_HOURS}h rolling window")
    lines.append(f"- **Extreme threshold:** ±{FUNDING_EXTREME_STD}σ from rolling mean")
    lines.append(f"- **Persistence thresholds:** {PERSISTENCE_INTERVALS} consecutive intervals")
    lines.append("- **Long crowded:** funding > mean + 2σ (longs pay shorts)")
    lines.append("- **Short crowded:** funding < mean - 2σ (shorts pay longs)")
    lines.append("")
    lines.append("**Hypothesis H1 — Mean Reversion:**")
    lines.append("- Long crowded → price falls (overleveraged longs unwind)")
    lines.append("- Short crowded → price rises (overleveraged shorts cover)")
    lines.append("")
    lines.append("**Hypothesis H2 — Continuation:**")
    lines.append("- Long crowded → price continues up (strong demand)")
    lines.append("- Short crowded → price continues down (strong selling)")
    lines.append("")

    # 3. Results
    lines.append("## 3. Results by Horizon")
    lines.append("")

    if not events:
        lines.append("⚠️ No funding extreme events detected.")
    else:
        for hyp_name, fam in [("Mean Reversion (H1)", fam_rev), ("Continuation (H2)", fam_con)]:
            if fam is None:
                continue
            lines.append(f"### {hyp_name} — All Events (N={fam['count']})")
            lines.append("")
            lines.append("| Horizon | Gross Mean(bps) | Gross Median(bps) | Net@4bps | Winrate@4bps | PF@4bps |")
            lines.append("|---------|-----------------|-------------------|----------|--------------|---------|")
            for h in OUTCOME_HORIZONS_HOURS:
                gm = fam.get(f"gross_mean_{h}h", 0)
                gmed = fam.get(f"gross_median_{h}h", 0)
                nm = fam.get(f"net_mean_{h}h_{PRIMARY_COST_BPS}bps", 0)
                wr = fam.get(f"winrate_{h}h_{PRIMARY_COST_BPS}bps", 0)
                pf = fam.get(f"pf_{h}h_{PRIMARY_COST_BPS}bps", 0)
                lines.append(f"| {h}h | {gm:.2f} | {gmed:.2f} | {nm:.2f} | {wr:.1%} | {pf:.2f} |")
            lines.append("")
            lines.append(f"- Mean MFE: {fam.get('mean_mfe', 0):.2f} bps")
            lines.append(f"- Mean MAE: {fam.get('mean_mae', 0):.2f} bps")
            lines.append(f"- MFE/MAE: {fam.get('mfe_mae_ratio', 0):.2f}")
            lines.append(f"- Mean funding rate: {fam.get('mean_funding_rate', 0)*100:.4f}%")
            lines.append(f"- Mean z-score: {fam.get('mean_z_score', 0):.2f}")
            lines.append("")

            # Quarterly
            q_keys = [k for k in fam.keys() if k.startswith("q") and "_mean_" in k]
            if q_keys:
                lines.append("**Quarterly stability (24h horizon):**")
                lines.append("")
                for qi in range(1, 5):
                    qm = fam.get(f"q{qi}_mean_24h")
                    qc = fam.get(f"q{qi}_count")
                    if qm is not None:
                        lines.append(f"- Q{qi}: {qm:.2f} bps (N={qc})")
                lines.append("")

        # By event type
        for etype, fam_r, fam_c in [("Long Crowded", fam_rev_long, fam_con_long), ("Short Crowded", fam_rev_short, fam_con_short)]:
            lines.append(f"### {etype}")
            lines.append("")
            for hyp_name, fam in [("Reversion", fam_r), ("Continuation", fam_c)]:
                if fam is None:
                    continue
                lines.append(f"**{hyp_name}** (N={fam['count']}):")
                lines.append(f"- Gross 24h: {fam.get('gross_mean_24h', 0):.2f} bps")
                lines.append(f"- Net 24h @4bps: {fam.get('net_mean_24h_4bps', 0):.2f} bps")
                lines.append(f"- PF 24h @4bps: {fam.get('pf_24h_4bps', 0):.2f}")
                lines.append("")

        # 4. Baselines
        lines.append("## 4. Baseline Comparison")
        lines.append("")
        if baselines:
            lines.append("| Baseline | 4h mean(bps) | 24h mean(bps) | 48h mean(bps) | Count |")
            lines.append("|----------|-------------|---------------|---------------|-------|")
            for name in ["random", "same_vol", "opposite"]:
                b = baselines.get(name, {})
                m4 = b.get(4, {}).get("mean", 0)
                m24 = b.get(24, {}).get("mean", 0)
                m48 = b.get(48, {}).get("mean", 0)
                cnt = b.get(4, {}).get("count", 0)
                lines.append(f"| {name} | {m4:.2f} | {m24:.2f} | {m48:.2f} | {cnt} |")
            lines.append("")

    # 5. Cost Analysis
    lines.append("## 5. Cost Analysis")
    lines.append("")
    if fam_rev:
        lines.append("**Mean Reversion:**")
        lines.append("")
        lines.append("| Horizon | Gross | Net@2bps | Net@4bps | Net@6bps |")
        lines.append("|---------|-------|----------|----------|----------|")
        for h in OUTCOME_HORIZONS_HOURS:
            g = fam_rev.get(f"gross_mean_{h}h", 0)
            n2 = fam_rev.get(f"net_mean_{h}h_2bps", 0)
            n4 = fam_rev.get(f"net_mean_{h}h_{PRIMARY_COST_BPS}bps", 0)
            n6 = fam_rev.get(f"net_mean_{h}h_6bps", 0)
            lines.append(f"| {h}h | {g:.2f} | {n2:.2f} | {n4:.2f} | {n6:.2f} |")
        lines.append("")

    # 6. Stability
    lines.append("## 6. Stability")
    lines.append("")
    if fam_rev:
        for h in [4, 24, 48]:
            fh = fam_rev.get(f"first_half_mean_{h}h", None)
            sh = fam_rev.get(f"second_half_mean_{h}h", None)
            if fh is not None and sh is not None:
                sign_match = "✅" if (fh > 0 and sh > 0) or (fh < 0 and sh < 0) else "❌"
                lines.append(f"- **{h}h (reversion):** 1st half={fh:.2f} bps, 2nd half={sh:.2f} bps {sign_match}")
        lines.append("")

    # 7. Failure Classification
    lines.append("## 7. Failure Classification")
    lines.append("")
    for mode in failure_modes:
        lines.append(f"- {mode}")
    lines.append("")

    # 8. Final Verdict
    lines.append("## 8. Final Verdict")
    lines.append("")

    # Determine best hypothesis
    best_hyp = None
    best_pf = 0
    best_fam = None
    for hyp, fam in [("reversion", fam_rev), ("continuation", fam_con)]:
        if fam:
            pf = fam.get(f"pf_24h_{PRIMARY_COST_BPS}bps", 0)
            if pf > best_pf:
                best_pf = pf
                best_hyp = hyp
                best_fam = fam

    criteria = []
    if best_fam:
        c1 = best_fam["count"] >= MIN_OCCURRENCES
        criteria.append(("Occurrences ≥ 100", c1, best_fam["count"]))

        primary_net = best_fam.get(f"net_mean_24h_{PRIMARY_COST_BPS}bps", 0)
        c2 = primary_net >= 0
        criteria.append(("Mean net @4bps ≥ 0", c2, f"{primary_net:.2f} bps"))

        c3 = best_pf >= MIN_PROFIT_FACTOR
        criteria.append(("PF > 1.1", c3, f"{best_pf:.2f}"))

        mfe_mae = best_fam.get("mfe_mae_ratio", 0)
        c4 = mfe_mae > 1
        criteria.append(("MFE >> MAE", c4, f"{mfe_mae:.2f}"))

        od = best_fam.get("outlier_dep_24h", 0)
        c5 = od < MAX_OUTLIER_DEPENDENCE
        criteria.append(("Outlier dep < 30%", c5, f"{od:.1%}"))

        fh = best_fam.get("first_half_mean_24h", 0)
        sh = best_fam.get("second_half_mean_24h", 0)
        c6 = (fh > 0 and sh > 0) or (fh < 0 and sh < 0)
        criteria.append(("Same sign halves", c6, f"1st={fh:.2f}, 2nd={sh:.2f}"))

        if baselines:
            setup_24 = best_fam.get(f"gross_mean_24h", 0)
            rand_24 = baselines.get("random", {}).get(24, {}).get("mean", 0)
            c7 = setup_24 > rand_24
            criteria.append(("Beats random baseline", c7, f"setup={setup_24:.2f}, rand={rand_24:.2f}"))

        lines.append(f"**Best hypothesis: {best_hyp}** (PF={best_pf:.2f})")
        lines.append("")
        lines.append("| Criterion | Status | Value |")
        lines.append("|-----------|--------|-------|")
        for name, passed, val in criteria:
            lines.append(f"| {name} | {'✅' if passed else '❌'} | {val} |")
        lines.append("")

        all_pass = all(p for _, p, _ in criteria)
        if all_pass:
            lines.append("### ✅ POSITIONING PRESSURE CREATES EXPLOITABLE BEHAVIOR")
        else:
            failed = [name for name, p, _ in criteria if not p]
            lines.append("### ❌ EDGE NOT VALIDATED")
            lines.append(f"Failed: {', '.join(failed)}")
    else:
        lines.append("### ❌ NO FUNDING EXTREME EVENTS DETECTED")
        lines.append("")
        lines.append("Insufficient data to evaluate.")
    lines.append("")

    # 9. Next Action
    lines.append("## 9. Next Action")
    lines.append("")
    if best_fam and best_fam.get(f"net_mean_24h_{PRIMARY_COST_BPS}bps", 0) >= 0 and best_pf >= MIN_PROFIT_FACTOR:
        lines.append("**ONE:** Validate with additional data sources (Bybit, Hyperliquid) and test cross-asset (ETH).")
    else:
        lines.append("**ONE:** This path is closed. Funding/positioning pressure does not create exploitable price behavior at these definitions.")
    lines.append("")
    lines.append("---")
    lines.append("*No parameters were tuned after seeing results.*")
    lines.append(f"*Analysis completed {time.strftime('%Y-%m-%d %H:%M:%S')}.*")

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--funding", default="data/historical/btcusdt_funding.csv")
    parser.add_argument("--prices", default="data/historical/btcusdt_1m.csv")
    parser.add_argument("--output", default="FUNDING_POSITIONING_REPORT.md")
    args = parser.parse_args()

    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    funding_path = os.path.join(base, args.funding)
    prices_path = os.path.join(base, args.prices)
    output_path = os.path.join(base, args.output)

    # Load data
    print(f"Loading funding data from {funding_path}...")
    funding = load_funding(funding_path)
    print(f"  {len(funding)} funding records")

    print(f"Loading price data from {prices_path}...")
    bars = load_bars(prices_path)
    print(f"  {len(bars):,} bars")

    # Step 1: Detect extremes
    print("Step 1: Detecting funding extremes...")
    events = detect_funding_extremes(funding)
    print(f"  {len(events)} events detected")

    # Step 2: Measure outcomes
    print("Step 2: Measuring outcomes...")
    measure_outcomes(events, bars)

    # Step 3: Compute baselines
    print("Step 3: Computing baselines...")
    baselines = compute_baselines(bars, events)

    # Step 4: Analyze both hypotheses
    print("Step 4: Analyzing...")
    fam_rev = analyze_family(events, "reversion", "all")
    fam_con = analyze_family(events, "continuation", "all")
    fam_rev_long = analyze_family(events, "reversion", "long_crowded")
    fam_rev_short = analyze_family(events, "reversion", "short_crowded")
    fam_con_long = analyze_family(events, "continuation", "long_crowded")
    fam_con_short = analyze_family(events, "continuation", "short_crowded")

    # Step 5: Failure classification
    print("Step 5: Classifying failure modes...")
    failure_modes = classify_failure(events, fam_rev, fam_con)

    # Step 6: Generate report
    print("Step 6: Generating report...")
    report = generate_report(events, baselines, bars, fam_rev, fam_con,
                            fam_rev_long, fam_rev_short, fam_con_long, fam_con_short,
                            failure_modes)

    with open(output_path, "w") as f:
        f.write(report)
    print(f"\nReport written to: {output_path}")

    # Summary
    print("\n" + "=" * 60)
    print(f"Total events: {len(events)}")
    if fam_rev:
        print(f"[REVERSION] Gross 24h: {fam_rev.get('gross_mean_24h', 0):.2f} bps, Net @4bps: {fam_rev.get('net_mean_24h_4bps', 0):.2f} bps, PF: {fam_rev.get('pf_24h_4bps', 0):.2f}")
    if fam_con:
        print(f"[CONTINUATION] Gross 24h: {fam_con.get('gross_mean_24h', 0):.2f} bps, Net @4bps: {fam_con.get('net_mean_24h_4bps', 0):.2f} bps, PF: {fam_con.get('pf_24h_4bps', 0):.2f}")
    print("=" * 60)
    print("\nFailure modes:")
    for m in failure_modes:
        print(f"  - {m}")


if __name__ == "__main__":
    main()
