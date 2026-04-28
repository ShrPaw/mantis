"""
Compression → Expansion Research — Optimized for large datasets

Hypothesis: periods of low volatility compression lead to large directional
expansions sufficient to overcome costs.

Reads 1m OHLCV bars (CSV), detects compression, measures breakout outcomes,
computes baselines, generates report.

No tuning. No ML. No optimization. Fixed definitions.

Usage:
  python3 -m research.compression_expansion.analyze --input data/historical/btcusdt_1m.csv
"""

import argparse
import csv
import math
import os
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

# ============================================================
# FIXED CONFIGURATION — Set BEFORE seeing any data
# ============================================================

VOL_WINDOWS_MIN = [10, 30, 60]
RANGE_WINDOWS_MIN = [10, 30, 60]
COMPRESSION_PERCENTILE = 20
LOOKBACK_HOURS = 24
LOOKBACK_BARS = LOOKBACK_HOURS * 60

BREAKOUT_CONFIRM_MIN = [1, 3, 5]
OUTCOME_HORIZONS_MIN = [5, 15, 30, 60, 120]
COST_LEVELS_BPS = [2, 4, 6]
PRIMARY_COST_BPS = 4

MIN_OCCURRENCES = 100
MIN_PROFIT_FACTOR = 1.10
MAX_OUTLIER_DEPENDENCE = 0.30


# ============================================================
# DATA LOADING
# ============================================================
@dataclass
class Bar:
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float


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
# EFFICIENT ROLLING STATISTICS
# ============================================================
def precompute_rolling_stats(bars):
    """
    Precompute realized vol and range for all windows.
    Returns dict: (window_min, bar_index) -> value
    """
    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    n = len(bars)

    stats = {}

    for win in VOL_WINDOWS_MIN:
        # Rolling realized vol using log returns
        log_rets = [0.0] * n
        for i in range(1, n):
            if closes[i-1] > 0:
                log_rets[i] = math.log(closes[i] / closes[i-1])

        # Rolling mean and sum of squares
        ret_sum = 0.0
        ret_sq_sum = 0.0
        q = deque()

        for i in range(n):
            q.append(log_rets[i])
            ret_sum += log_rets[i]
            ret_sq_sum += log_rets[i] ** 2
            if len(q) > win:
                old = q.popleft()
                ret_sum -= old
                ret_sq_sum -= old ** 2
            if len(q) == win:
                mean = ret_sum / win
                var = ret_sq_sum / win - mean ** 2
                stats[("vol", win, i)] = math.sqrt(max(0, var))

    for win in RANGE_WINDOWS_MIN:
        # Rolling high-low range in bps
        high_q = deque()
        low_q = deque()

        for i in range(n):
            high_q.append(highs[i])
            low_q.append(lows[i])
            if len(high_q) > win:
                high_q.popleft()
                low_q.popleft()
            if len(high_q) == win:
                h = max(high_q)
                l = min(low_q)
                mid = (h + l) / 2
                if mid > 0:
                    stats[("range", win, i)] = ((h - l) / mid) * 10000
                else:
                    stats[("range", win, i)] = 0.0

    return stats


def precompute_percentiles(stats, bars, lookback=LOOKBACK_BARS):
    """
    For each bar and each stat key, compute what percentile the current value
    is in the trailing lookback window.

    Returns dict: (key_type, window, bar_index) -> percentile (0-100)
    """
    n = len(bars)
    percentiles = {}

    stat_keys = set()
    for k in stats:
        stat_keys.add((k[0], k[1]))

    for key_type, win in stat_keys:
        # Collect values in order
        values = []
        for i in range(n):
            v = stats.get((key_type, win, i))
            if v is not None:
                values.append((i, v))

        # Sliding window percentile
        q = deque()
        for idx, val in values:
            q.append((idx, val))
            # Remove old entries
            while q and q[0][0] < idx - lookback:
                q.popleft()

            if len(q) >= 5:  # need minimum samples
                count_below = sum(1 for _, v in q if v <= val)
                percentiles[(key_type, win, idx)] = (count_below / len(q)) * 100

    return percentiles


# ============================================================
# COMPRESSION DETECTION (OPTIMIZED)
# ============================================================
def detect_compression(bars, stats, percentiles):
    """
    A bar is COMPRESSION if ALL vol windows are in bottom 20%
    AND ALL range windows are in bottom 20% of last 24h.
    """
    n = len(bars)
    compressed = []

    for i in range(LOOKBACK_BARS, n):
        is_compression = True

        # Check all vol windows
        for win in VOL_WINDOWS_MIN:
            pct = percentiles.get(("vol", win, i))
            if pct is None or pct > COMPRESSION_PERCENTILE:
                is_compression = False
                break

        if not is_compression:
            continue

        # Check all range windows
        for win in RANGE_WINDOWS_MIN:
            pct = percentiles.get(("range", win, i))
            if pct is None or pct > COMPRESSION_PERCENTILE:
                is_compression = False
                break

        if is_compression:
            # Score = average percentile across all metrics
            pcts = []
            for win in VOL_WINDOWS_MIN:
                p = percentiles.get(("vol", win, i))
                if p is not None:
                    pcts.append(p)
            for win in RANGE_WINDOWS_MIN:
                p = percentiles.get(("range", win, i))
                if p is not None:
                    pcts.append(p)
            score = sum(pcts) / len(pcts) if pcts else 0
            compressed.append((i, score))

    return compressed


# ============================================================
# COMPRESSION BOX + BREAKOUT
# ============================================================
@dataclass
class CompressionBox:
    start_idx: int
    end_idx: int
    high: float
    low: float
    mid: float
    range_bps: float
    duration_min: int
    score: float


@dataclass
class Breakout:
    box: CompressionBox
    direction: str
    breakout_idx: int
    breakout_price: float
    confirm_idx: int
    confirm_price: float
    entry_price: float
    fwd: dict = field(default_factory=dict)
    fwd_net: dict = field(default_factory=dict)
    mfe: float = 0.0
    mae: float = 0.0
    ttp: Optional[float] = None


def build_compression_boxes(bars, compressed_indices):
    if not compressed_indices:
        return []

    idx_set = set(i for i, _ in compressed_indices)
    score_map = {i: s for i, s in compressed_indices}
    boxes = []
    start = None
    box_high = 0
    box_low = float("inf")
    scores = []

    for i in sorted(idx_set):
        if start is None:
            start = i
            box_high = bars[i].high
            box_low = bars[i].low
            scores = [score_map[i]]
        elif i == start + len(scores):
            box_high = max(box_high, bars[i].high)
            box_low = min(box_low, bars[i].low)
            scores.append(score_map[i])
        else:
            if box_high > box_low:
                mid = (box_high + box_low) / 2
                rng = ((box_high - box_low) / mid) * 10000 if mid > 0 else 0
                boxes.append(CompressionBox(
                    start_idx=start, end_idx=start + len(scores) - 1,
                    high=box_high, low=box_low, mid=mid,
                    range_bps=rng, duration_min=len(scores),
                    score=sum(scores)/len(scores),
                ))
            start = i
            box_high = bars[i].high
            box_low = bars[i].low
            scores = [score_map[i]]

    if start is not None and box_high > box_low:
        mid = (box_high + box_low) / 2
        rng = ((box_high - box_low) / mid) * 10000 if mid > 0 else 0
        boxes.append(CompressionBox(
            start_idx=start, end_idx=start + len(scores) - 1,
            high=box_high, low=box_low, mid=mid,
            range_bps=rng, duration_min=len(scores),
            score=sum(scores)/len(scores),
        ))

    return boxes


def detect_breakouts(bars, boxes):
    breakouts = []
    used_boxes = set()

    for box in boxes:
        search_start = box.end_idx + 1
        search_end = min(search_start + 120, len(bars))

        for i in range(search_start, search_end):
            bar = bars[i]

            # Long breakout
            if bar.close > box.high and box.start_idx not in used_boxes:
                for conf_min in BREAKOUT_CONFIRM_MIN:
                    if i + conf_min >= len(bars):
                        continue
                    confirmed = True
                    for j in range(i + 1, i + conf_min + 1):
                        if bars[j].close <= box.high:
                            confirmed = False
                            break
                    if confirmed:
                        entry_idx = i + conf_min
                        entry_price = bars[entry_idx].close
                        breakouts.append(Breakout(
                            box=box, direction="long",
                            breakout_idx=i, breakout_price=bar.close,
                            confirm_idx=entry_idx, confirm_price=bars[entry_idx].close,
                            entry_price=entry_price,
                        ))
                        used_boxes.add(box.start_idx)
                    break

            # Short breakout
            elif bar.close < box.low and box.start_idx not in used_boxes:
                for conf_min in BREAKOUT_CONFIRM_MIN:
                    if i + conf_min >= len(bars):
                        continue
                    confirmed = True
                    for j in range(i + 1, i + conf_min + 1):
                        if bars[j].close >= box.low:
                            confirmed = False
                            break
                    if confirmed:
                        entry_idx = i + conf_min
                        entry_price = bars[entry_idx].close
                        breakouts.append(Breakout(
                            box=box, direction="short",
                            breakout_idx=i, breakout_price=bar.close,
                            confirm_idx=entry_idx, confirm_price=bars[entry_idx].close,
                            entry_price=entry_price,
                        ))
                        used_boxes.add(box.start_idx)
                    break

    return breakouts


# ============================================================
# OUTCOME MEASUREMENT
# ============================================================
def measure_outcomes(breakouts, bars):
    max_h = max(OUTCOME_HORIZONS_MIN)

    for bo in breakouts:
        entry = bo.entry_price
        if entry <= 0:
            continue

        start_idx = bo.confirm_idx
        end_idx = min(start_idx + max_h + 10, len(bars))

        for i in range(start_idx, end_idx):
            bar = bars[i]
            elapsed = i - start_idx

            if bo.direction == "long":
                ret_bps = ((bar.close - entry) / entry) * 10000
                high_ret = ((bar.high - entry) / entry) * 10000
                low_ret = ((bar.low - entry) / entry) * 10000
            else:
                ret_bps = ((entry - bar.close) / entry) * 10000
                high_ret = ((entry - bar.low) / entry) * 10000
                low_ret = ((entry - bar.high) / entry) * 10000

            bo.mfe = max(bo.mfe, high_ret)
            bo.mae = min(bo.mae, low_ret)

            for h in OUTCOME_HORIZONS_MIN:
                if elapsed >= h and h not in bo.fwd:
                    bo.fwd[h] = ret_bps
                    for c in COST_LEVELS_BPS:
                        bo.fwd_net[(h, c)] = ret_bps - c

            if bo.ttp is None and ret_bps > 0:
                bo.ttp = elapsed


# ============================================================
# BASELINES
# ============================================================
def compute_baselines(bars, breakouts):
    import random
    random.seed(42)

    if len(bars) < 100 or not breakouts:
        return {}

    n_samples = min(5000, len(breakouts) * 10)
    horizons = OUTCOME_HORIZONS_MIN
    min_idx = LOOKBACK_BARS + max(horizons)
    max_idx = len(bars) - max(horizons) - 1

    if max_idx <= min_idx:
        return {}

    def forward_return(entry_idx, direction, horizon):
        target_idx = min(entry_idx + horizon, len(bars) - 1)
        entry_px = bars[entry_idx].close
        exit_px = bars[target_idx].close
        if entry_px <= 0:
            return 0.0
        if direction == "long":
            return ((exit_px - entry_px) / entry_px) * 10000
        else:
            return ((entry_px - exit_px) / entry_px) * 10000

    baselines = {"random": {h: [] for h in horizons}}
    for _ in range(n_samples):
        idx = random.randint(min_idx, max_idx)
        d = random.choice(["long", "short"])
        for h in horizons:
            baselines["random"][h].append(forward_return(idx, d, h))

    # Same-vol baseline
    baselines["same_vol"] = {h: [] for h in horizons}
    # Sample some compression-period vol values
    comp_indices = [bo.box.end_idx for bo in breakouts]
    if comp_indices:
        for _ in range(n_samples):
            ci = random.choice(comp_indices)
            # Find a bar with similar vol (±50%)
            for attempt in range(20):
                idx = random.randint(min_idx, max_idx)
                # Simple proxy: use close-to-close absolute return
                if idx >= 30 and ci >= 30:
                    ci_ret = abs(bars[ci].close - bars[ci-30].close) / bars[ci-30].close if bars[ci-30].close > 0 else 0
                    idx_ret = abs(bars[idx].close - bars[idx-30].close) / bars[idx-30].close if bars[idx-30].close > 0 else 0
                    if ci_ret > 0 and abs(idx_ret - ci_ret) < ci_ret * 0.5:
                        d = random.choice(["long", "short"])
                        for h in horizons:
                            baselines["same_vol"][h].append(forward_return(idx, d, h))
                        break

    # Opposite direction
    baselines["opposite"] = {h: [] for h in horizons}
    for bo in breakouts:
        opp = "short" if bo.direction == "long" else "long"
        for h in horizons:
            baselines["opposite"][h].append(forward_return(bo.confirm_idx, opp, h))

    # Drift
    baselines["drift"] = {h: [] for h in horizons}
    for _ in range(n_samples):
        idx = random.randint(min_idx, max_idx)
        for h in horizons:
            baselines["drift"][h].append(forward_return(idx, "long", h))

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


def analyze_family(breakouts, direction="all"):
    if direction != "all":
        bs = [b for b in breakouts if b.direction == direction]
    else:
        bs = breakouts

    count = len(bs)
    if count == 0:
        return None

    result = {"count": count, "direction": direction}

    for h in OUTCOME_HORIZONS_MIN:
        gross = [b.fwd.get(h, 0) for b in bs if h in b.fwd]
        if not gross:
            continue
        result[f"gross_mean_{h}m"] = safe_mean(gross)
        result[f"gross_median_{h}m"] = safe_median(gross)
        result[f"worst5_{h}m"] = percentile(gross, 5)
        result[f"best5_{h}m"] = percentile(gross, 95)

        for c in COST_LEVELS_BPS:
            net = [b.fwd_net.get((h, c), 0) for b in bs if (h, c) in b.fwd_net]
            if not net:
                continue
            result[f"net_mean_{h}m_{c}bps"] = safe_mean(net)
            wins = [r for r in net if r > 0]
            result[f"winrate_{h}m_{c}bps"] = len(wins) / len(net) if net else 0
            result[f"pf_{h}m_{c}bps"] = profit_factor(net)

    mfes = [b.mfe for b in bs if b.mfe > 0]
    maes = [b.mae for b in bs if b.mae < 0]
    result["mean_mfe"] = safe_mean(mfes)
    result["mean_mae"] = safe_mean(maes)
    result["mfe_mae_ratio"] = abs(safe_mean(mfes) / safe_mean(maes)) if maes and safe_mean(maes) != 0 else 0

    ttps = [b.ttp for b in bs if b.ttp is not None]
    result["median_ttp"] = safe_median(ttps)
    result["ttp_count"] = len(ttps)

    for h in [30, 60, 120]:
        gross = [b.fwd.get(h, 0) for b in bs if h in b.fwd]
        if len(gross) < 10:
            continue
        total_pnl = sum(gross)
        if total_pnl == 0:
            continue
        top5 = sorted(gross, reverse=True)[:max(1, len(gross) // 20)]
        result[f"outlier_dep_{h}m"] = sum(top5) / total_pnl if total_pnl > 0 else 0

    bs_sorted = sorted(bs, key=lambda b: b.confirm_idx)
    mid = len(bs_sorted) // 2
    for label, chunk in [("first_half", bs_sorted[:mid]), ("second_half", bs_sorted[mid:])]:
        for h in [30, 60, 120]:
            gross = [b.fwd.get(h, 0) for b in chunk if h in b.fwd]
            if gross:
                result[f"{label}_mean_{h}m"] = safe_mean(gross)

    # Quarterly stability (for 11-month dataset)
    if count >= 20:
        # Split into ~3 month chunks
        chunk_size = max(1, count // 4)
        for qi in range(4):
            chunk = bs_sorted[qi*chunk_size:(qi+1)*chunk_size]
            for h in [60]:
                gross = [b.fwd.get(h, 0) for b in chunk if h in b.fwd]
                if gross:
                    result[f"q{qi+1}_mean_{h}m"] = safe_mean(gross)
                    result[f"q{qi+1}_count"] = len(chunk)

    durations = [b.box.duration_min for b in bs]
    ranges = [b.box.range_bps for b in bs]
    result["mean_box_duration"] = safe_mean(durations)
    result["mean_box_range_bps"] = safe_mean(ranges)

    return result


def classify_failure(breakouts, fam_all, baselines):
    if not breakouts:
        return ["No breakout events detected after compression"]

    fam = fam_all
    if fam is None:
        return ["No analyzable breakout events"]

    modes = []
    total = fam["count"]
    primary_net = fam.get(f"net_mean_30m_{PRIMARY_COST_BPS}bps", 0)
    mfe_mae = fam.get("mfe_mae_ratio", 0)

    gross_30 = fam.get("gross_mean_30m", 0)
    if abs(gross_30) < 1:
        modes.append("No meaningful expansion after compression (|mean 30m| < 1 bps)")

    fam_l = analyze_family(breakouts, "long")
    fam_s = analyze_family(breakouts, "short")
    if fam_l and fam_s:
        gl = fam_l.get("gross_mean_30m", 0)
        gs = fam_s.get("gross_mean_30m", 0)
        if (gl > 0 and gs > 0) or (gl < 0 and gs < 0):
            modes.append("Direction is random — both sides move same way")
        elif gl <= 0 and gs <= 0:
            modes.append("Both directions negative — no directional edge")

    if gross_30 > 0 and primary_net < 0:
        modes.append("Expansion exists but costs kill it")

    if mfe_mae < 1:
        modes.append("MFE < MAE — adverse excursion exceeds favorable")

    if fam_l and not fam_s:
        modes.append("Only long breakouts exist (possible BTC drift)")
    elif fam_s and not fam_l:
        modes.append("Only short breakouts exist")

    if not modes:
        modes.append("Edge may exist — all basic checks passed")

    return modes


def generate_report(breakouts, baselines, bars, fam_all, fam_long, fam_short, failure_modes):
    lines = []
    lines.append("# COMPRESSION → EXPANSION REPORT")
    lines.append("")
    lines.append(f"**Date:** {time.strftime('%Y-%m-%d')}")
    lines.append(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    lines.append("## 1. Data Summary")
    lines.append("")
    duration_days = (bars[-1].timestamp - bars[0].timestamp) / 86400
    lines.append(f"- **Source:** Binance BTC/USDT 1-minute bars (historical)")
    lines.append(f"- **Bars:** {len(bars):,}")
    lines.append(f"- **Duration:** {duration_days:.0f} days ({duration_days/30:.1f} months)")
    lines.append(f"- **Period:** {time.strftime('%Y-%m-%d', time.gmtime(bars[0].timestamp))} to {time.strftime('%Y-%m-%d', time.gmtime(bars[-1].timestamp))} UTC")
    lines.append("")

    lines.append("## 2. Compression Definition")
    lines.append("")
    lines.append("**Compression = market storing energy**")
    lines.append("")
    lines.append("A 1-minute bar is in COMPRESSION state if:")
    lines.append(f"- Realized volatility (over {VOL_WINDOWS_MIN} min windows) is in bottom {COMPRESSION_PERCENTILE}% of last {LOOKBACK_HOURS}h")
    lines.append(f"  AND")
    lines.append(f"- High-low range (over {RANGE_WINDOWS_MIN} min windows) is in bottom {COMPRESSION_PERCENTILE}% of last {LOOKBACK_HOURS}h")
    lines.append("")
    lines.append("Consecutive compressed bars form a **compression box** (high/low of the compressed period).")
    lines.append("")

    comp_bars_count = sum(1 for b in breakouts for _ in range(b.box.duration_min)) if breakouts else 0
    unique_boxes = len(set(id(b.box) for b in breakouts))
    lines.append(f"- **Compression bars:** {comp_bars_count:,} ({comp_bars_count/len(bars)*100:.1f}% of data)")
    lines.append(f"- **Compression boxes:** {unique_boxes}")
    lines.append("")

    lines.append("## 3. Breakout Logic")
    lines.append("")
    lines.append("**LONG:** Price closes above compression box high")
    lines.append("**SHORT:** Price closes below compression box low")
    lines.append(f"**Confirmation:** Price stays outside box for {BREAKOUT_CONFIRM_MIN} min")
    lines.append("**Entry:** Close price AFTER confirmation window")
    lines.append("")

    lines.append("## 4. Results vs Baselines")
    lines.append("")
    total = len(breakouts)
    longs = [b for b in breakouts if b.direction == "long"]
    shorts = [b for b in breakouts if b.direction == "short"]
    lines.append(f"**Total breakouts:** {total}")
    lines.append(f"- Long: {len(longs)}")
    lines.append(f"- Short: {len(shorts)}")
    lines.append("")

    if total < 10:
        lines.append("⚠️ **Insufficient breakouts for meaningful analysis.**")
        lines.append("")
    else:
        for direction, fam in [("All", fam_all), ("Long", fam_long), ("Short", fam_short)]:
            if fam is None:
                continue
            lines.append(f"### {direction} (N={fam['count']})")
            lines.append("")
            lines.append("| Horizon | Gross Mean(bps) | Gross Median(bps) | Net@4bps Mean | Winrate@4bps | PF@4bps |")
            lines.append("|---------|-----------------|-------------------|---------------|--------------|---------|")
            for h in OUTCOME_HORIZONS_MIN:
                gm = fam.get(f"gross_mean_{h}m", 0)
                gmed = fam.get(f"gross_median_{h}m", 0)
                nm = fam.get(f"net_mean_{h}m_{PRIMARY_COST_BPS}bps", 0)
                wr = fam.get(f"winrate_{h}m_{PRIMARY_COST_BPS}bps", 0)
                pf = fam.get(f"pf_{h}m_{PRIMARY_COST_BPS}bps", 0)
                lines.append(f"| {h}m | {gm:.2f} | {gmed:.2f} | {nm:.2f} | {wr:.1%} | {pf:.2f} |")
            lines.append("")
            lines.append(f"- **Mean MFE:** {fam.get('mean_mfe', 0):.2f} bps")
            lines.append(f"- **Mean MAE:** {fam.get('mean_mae', 0):.2f} bps")
            lines.append(f"- **MFE/MAE ratio:** {fam.get('mfe_mae_ratio', 0):.2f}")
            lines.append(f"- **Median time-to-positive:** {fam.get('median_ttp', 0):.1f} min")
            lines.append(f"- **Mean box duration:** {fam.get('mean_box_duration', 0):.1f} min")
            lines.append(f"- **Mean box range:** {fam.get('mean_box_range_bps', 0):.1f} bps")
            lines.append("")

            # Quarterly stability
            q_keys = [k for k in fam.keys() if k.startswith("q") and "_mean_" in k]
            if q_keys:
                lines.append("**Quarterly stability (60m horizon):**")
                lines.append("")
                for qi in range(1, 5):
                    qm = fam.get(f"q{qi}_mean_60m")
                    qc = fam.get(f"q{qi}_count")
                    if qm is not None:
                        lines.append(f"- Q{qi}: {qm:.2f} bps (N={qc})")
                lines.append("")

        # Baselines
        lines.append("### Baseline Comparison")
        lines.append("")
        if baselines:
            lines.append("| Baseline | 30m mean(bps) | 60m mean(bps) | 120m mean(bps) | Count |")
            lines.append("|----------|---------------|---------------|----------------|-------|")
            for name in ["random", "same_vol", "drift", "opposite"]:
                b = baselines.get(name, {})
                m30 = b.get(30, {}).get("mean", 0)
                m60 = b.get(60, {}).get("mean", 0)
                m120 = b.get(120, {}).get("mean", 0)
                cnt = b.get(30, {}).get("count", 0)
                lines.append(f"| {name} | {m30:.2f} | {m60:.2f} | {m120:.2f} | {cnt} |")
            lines.append("")

            if fam_all:
                setup_60 = fam_all.get("gross_mean_60m", 0)
                lines.append("**Edge vs baselines (60m horizon):**")
                lines.append("")
                for name in ["random", "same_vol", "drift", "opposite"]:
                    b_mean = baselines.get(name, {}).get(60, {}).get("mean", 0)
                    diff = setup_60 - b_mean
                    beats = "✅" if diff > 0 else "❌"
                    lines.append(f"- {beats} vs {name}: {diff:+.2f} bps (setup={setup_60:.2f}, baseline={b_mean:.2f})")
                lines.append("")

    lines.append("## 5. Cost Analysis")
    lines.append("")
    if fam_all:
        fam = fam_all
        lines.append("| Horizon | Gross | Net@2bps | Net@4bps | Net@6bps |")
        lines.append("|---------|-------|----------|----------|----------|")
        for h in OUTCOME_HORIZONS_MIN:
            g = fam.get(f"gross_mean_{h}m", 0)
            n2 = fam.get(f"net_mean_{h}m_2bps", 0)
            n4 = fam.get(f"net_mean_{h}m_{PRIMARY_COST_BPS}bps", 0)
            n6 = fam.get(f"net_mean_{h}m_6bps", 0)
            lines.append(f"| {h}m | {g:.2f} | {n2:.2f} | {n4:.2f} | {n6:.2f} |")
        lines.append("")
    else:
        lines.append("No breakouts to analyze.")
        lines.append("")

    lines.append("## 6. Stability")
    lines.append("")
    if fam_all:
        for h in [30, 60, 120]:
            fh = fam_all.get(f"first_half_mean_{h}m", None)
            sh = fam_all.get(f"second_half_mean_{h}m", None)
            if fh is not None and sh is not None:
                sign_match = "✅" if (fh > 0 and sh > 0) or (fh < 0 and sh < 0) else "❌"
                lines.append(f"- **{h}m:** First half={fh:.2f} bps, Second half={sh:.2f} bps {sign_match}")
        lines.append("")
    else:
        lines.append("Insufficient data.")
        lines.append("")

    lines.append("## 7. Failure Classification")
    lines.append("")
    for mode in failure_modes:
        lines.append(f"- {mode}")
    lines.append("")

    lines.append("## 8. Final Verdict")
    lines.append("")

    criteria = []
    if fam_all:
        c1 = fam_all["count"] >= MIN_OCCURRENCES
        criteria.append(("Occurrences ≥ 100", c1, fam_all["count"]))

        primary_net = fam_all.get(f"net_mean_30m_{PRIMARY_COST_BPS}bps", 0)
        c2 = primary_net >= 0
        criteria.append(("Mean net @4bps ≥ 0", c2, f"{primary_net:.2f} bps"))

        primary_pf = fam_all.get(f"pf_30m_{PRIMARY_COST_BPS}bps", 0)
        c3 = primary_pf >= MIN_PROFIT_FACTOR
        criteria.append(("PF > 1.1", c3, f"{primary_pf:.2f}"))

        mfe_mae = fam_all.get("mfe_mae_ratio", 0)
        c4 = mfe_mae > 1
        criteria.append(("MFE >> MAE", c4, f"{mfe_mae:.2f}"))

        od = fam_all.get("outlier_dep_60m", 0)
        c5 = od < MAX_OUTLIER_DEPENDENCE
        criteria.append(("Outlier dep < 30%", c5, f"{od:.1%}"))

        fh = fam_all.get("first_half_mean_60m", 0)
        sh = fam_all.get("second_half_mean_60m", 0)
        c6 = (fh > 0 and sh > 0) or (fh < 0 and sh < 0)
        criteria.append(("Same sign across halves", c6, f"1st={fh:.2f}, 2nd={sh:.2f}"))

        if baselines:
            setup_60 = fam_all.get("gross_mean_60m", 0)
            rand_60 = baselines.get("random", {}).get(60, {}).get("mean", 0)
            c7 = setup_60 > rand_60
            criteria.append(("Beats random baseline", c7, f"setup={setup_60:.2f}, rand={rand_60:.2f}"))

        lines.append("| Criterion | Status | Value |")
        lines.append("|-----------|--------|-------|")
        for name, passed, val in criteria:
            lines.append(f"| {name} | {'✅' if passed else '❌'} | {val} |")
        lines.append("")

        all_pass = all(p for _, p, _ in criteria)
        if all_pass:
            lines.append("### ✅ ALL CRITERIA MET — VALID STRUCTURAL EDGE")
            lines.append("")
            lines.append("Compression → expansion produces exploitable returns that survive costs,")
            lines.append("are stable over time, and beat random baselines.")
        else:
            failed = [name for name, p, _ in criteria if not p]
            lines.append("### ❌ EDGE NOT VALIDATED")
            lines.append("")
            lines.append(f"Failed criteria: {', '.join(failed)}")
    else:
        lines.append("### ❌ INSUFFICIENT DATA")
        lines.append("")
        lines.append(f"Only {total} breakouts detected. Need ≥{MIN_OCCURRENCES} for promotion.")
        lines.append("")

    lines.append("## 9. Next Action")
    lines.append("")
    if fam_all and fam_all["count"] >= MIN_OCCURRENCES:
        primary_net = fam_all.get(f"net_mean_30m_{PRIMARY_COST_BPS}bps", 0)
        if primary_net >= 0:
            lines.append("**ONE:** Validate on out-of-sample data or different asset (ETH, SOL).")
        else:
            lines.append("**ONE:** This path is closed. Compression → expansion does not produce edge at these definitions.")
    else:
        lines.append("**ONE:** This path is closed. Insufficient events after full dataset analysis.")
    lines.append("")
    lines.append("---")
    lines.append("*No parameters were tuned after seeing results. All thresholds are structural assumptions.*")
    lines.append(f"*Analysis completed {time.strftime('%Y-%m-%d %H:%M:%S')}.*")

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to 1m OHLCV CSV")
    parser.add_argument("--output", default="COMPRESSION_EXPANSION_REPORT.md")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: {args.input} not found")
        sys.exit(1)

    print(f"Loading bars from {args.input}...")
    t0 = time.time()
    bars = load_bars(args.input)
    if not bars:
        print("ERROR: No valid bars found")
        sys.exit(1)

    duration = (bars[-1].timestamp - bars[0].timestamp) / 3600
    print(f"Loaded {len(bars):,} bars, {duration/24:.0f} days ({time.time()-t0:.1f}s)")

    # Step 1: Precompute rolling stats
    print("Step 1: Precomputing rolling statistics...")
    t0 = time.time()
    stats = precompute_rolling_stats(bars)
    print(f"  {len(stats):,} stat values computed ({time.time()-t0:.1f}s)")

    # Step 2: Precompute percentiles
    print("Step 2: Computing rolling percentiles...")
    t0 = time.time()
    percentiles = precompute_percentiles(stats, bars)
    print(f"  {len(percentiles):,} percentile values ({time.time()-t0:.1f}s)")

    # Step 3: Detect compression
    print("Step 3: Detecting compression periods...")
    t0 = time.time()
    compressed = detect_compression(bars, stats, percentiles)
    print(f"  {len(compressed):,} compressed bars ({time.time()-t0:.1f}s)")

    # Step 4: Build boxes
    print("Step 4: Building compression boxes...")
    boxes = build_compression_boxes(bars, compressed)
    print(f"  {len(boxes)} compression boxes")

    # Step 5: Detect breakouts
    print("Step 5: Detecting breakouts...")
    breakouts = detect_breakouts(bars, boxes)
    print(f"  {len(breakouts)} breakouts")

    # Step 6: Measure outcomes
    print("Step 6: Measuring outcomes...")
    t0 = time.time()
    measure_outcomes(breakouts, bars)
    print(f"  Done ({time.time()-t0:.1f}s)")

    # Step 7: Baselines
    print("Step 7: Computing baselines...")
    t0 = time.time()
    baselines = compute_baselines(bars, breakouts)
    print(f"  Done ({time.time()-t0:.1f}s)")

    # Step 8: Analyze
    print("Step 8: Analyzing...")
    fam_all = analyze_family(breakouts, "all")
    fam_long = analyze_family(breakouts, "long")
    fam_short = analyze_family(breakouts, "short")

    # Step 9: Failure classification
    failure_modes = classify_failure(breakouts, fam_all, baselines)

    # Step 10: Report
    print("Step 9: Generating report...")
    report = generate_report(breakouts, baselines, bars, fam_all, fam_long, fam_short, failure_modes)

    output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), args.output)
    with open(output_path, "w") as f:
        f.write(report)
    print(f"\nReport written to: {output_path}")

    # Summary
    print("\n" + "=" * 60)
    if fam_all:
        print(f"Total breakouts: {fam_all['count']}")
        print(f"Gross mean 30m: {fam_all.get('gross_mean_30m', 0):.2f} bps")
        print(f"Net mean 30m @4bps: {fam_all.get('net_mean_30m_4bps', 0):.2f} bps")
        print(f"Winrate 30m @4bps: {fam_all.get('winrate_30m_4bps', 0):.1%}")
        print(f"PF 30m @4bps: {fam_all.get('pf_30m_4bps', 0):.2f}")
        print(f"MFE/MAE: {fam_all.get('mfe_mae_ratio', 0):.2f}")
    else:
        print("No breakouts found.")
    print("=" * 60)
    print("\nFailure modes:")
    for m in failure_modes:
        print(f"  - {m}")


if __name__ == "__main__":
    main()
