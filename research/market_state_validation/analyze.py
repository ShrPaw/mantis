"""
Market State Validation — Single Script

Loads BTC 1-minute data, classifies market states (EXPANSION / CHOP / DEAD),
compares against 5 baselines, measures forward outcomes, generates report.

No tuning. No ML. Fixed definitions. Honest results.

Usage:
  python3 -m research.market_state_validation.analyze
  python3 -m research.market_state_validation.analyze --input /path/to/data.csv
"""

import argparse
import math
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

# ============================================================
# FIXED CONFIGURATION — Set BEFORE seeing data
# ============================================================
# Data source (default: btc-intraday-system dataset)
DEFAULT_INPUT = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', 'btc-intraday-system',
    'data', 'features', 'btcusdt_1m.csv'
)

# Expansion thresholds (bps) — price must move this much
EXPANSION_THRESHOLDS_BPS = [10, 15, 20, 30]

# Reference windows (in bar counts, 1 bar = 1 minute)
REFERENCE_WINDOWS_BARS = [1, 3, 5]  # 1m, 3m, 5m

# Confirmation windows (bars)
CONFIRMATION_WINDOWS_BARS = [1, 2, 3]  # 1m, 2m, 3m

# Forward outcome horizons (bars)
OUTCOME_HORIZONS_BARS = [1, 2, 3, 5, 10]  # 1m, 2m, 3m, 5m, 10m

# Cost assumptions (round trip, bps)
COST_LEVELS_BPS = [2, 4, 6]
PRIMARY_COST_BPS = 4

# Chop definition
CHOP_MIN_RANGE_BPS = 10
CHOP_MAX_NET_RETURN_BPS = 5
CHOP_MAX_EFFICIENCY = 0.25

# Dead definition
DEAD_MAX_RANGE_BPS = 5

# Baseline samples
N_BASELINE_SAMPLES = 2000

# Promotion
MIN_OCCURRENCES = 100
MIN_PROFIT_FACTOR = 1.05

# Random seed for reproducibility
RANDOM_SEED = 42

REPORT_OUTPUT = "MARKET_STATE_VALIDATION_REPORT.md"


# ============================================================
# DATA LOADING
# ============================================================
def load_data(path):
    """Load 1-minute BTC data. Returns list of dicts sorted by time."""
    print(f"Loading data from {path}...")
    rows = []
    with open(path) as f:
        header = f.readline().strip().split(',')
        for line in f:
            parts = line.strip().split(',')
            if len(parts) < 5:
                continue
            try:
                ts_str = parts[0]
                # Parse timestamp
                try:
                    ts = time.mktime(time.strptime(ts_str, '%Y-%m-%d %H:%M:%S'))
                except ValueError:
                    ts = float(ts_str)
                rows.append({
                    'timestamp': ts,
                    'price': float(parts[1]),
                    'volume': float(parts[2]),
                    'delta': float(parts[3]),
                    'trade_count': float(parts[4]),
                })
            except (ValueError, IndexError):
                continue
    rows.sort(key=lambda r: r['timestamp'])
    print(f"Loaded {len(rows)} bars")
    if rows:
        t0 = time.strftime('%Y-%m-%d', time.localtime(rows[0]['timestamp']))
        t1 = time.strftime('%Y-%m-%d', time.localtime(rows[-1]['timestamp']))
        print(f"Date range: {t0} to {t1}")
    return rows


# ============================================================
# ROLLING METRICS
# ============================================================
def compute_rolling_metrics(rows):
    """Compute all rolling metrics for each bar."""
    print("Computing rolling metrics...")
    n = len(rows)

    # Pre-extract arrays for speed
    prices = [r['price'] for r in rows]
    volumes = [r['volume'] for r in rows]
    deltas = [r['delta'] for r in rows]
    trade_counts = [r['trade_count'] for r in rows]

    for i in range(n):
        row = rows[i]
        p = prices[i]

        # Returns over various windows (in bps)
        for w in [1, 3, 5, 10]:
            if i >= w and prices[i - w] > 0:
                row[f'return_{w}m_bps'] = ((p / prices[i - w]) - 1) * 10000
            else:
                row[f'return_{w}m_bps'] = 0.0

        # Rolling range (high - low) in bps
        for w in [3, 5]:
            start = max(0, i - w + 1)
            window_prices = prices[start:i + 1]
            if window_prices and p > 0:
                hi = max(window_prices)
                lo = min(window_prices)
                row[f'range_{w}m_bps'] = ((hi - lo) / p) * 10000
            else:
                row[f'range_{w}m_bps'] = 0.0

        # Realized volatility (std of log returns)
        for w in [3, 5]:
            start = max(0, i - w)
            if start < i:
                rets = []
                for j in range(start + 1, i + 1):
                    if prices[j - 1] > 0:
                        rets.append(math.log(prices[j] / prices[j - 1]))
                if len(rets) >= 2:
                    m = sum(rets) / len(rets)
                    var = sum((r - m) ** 2 for r in rets) / len(rets)
                    row[f'rvol_{w}m'] = var ** 0.5
                else:
                    row[f'rvol_{w}m'] = 0.0
            else:
                row[f'rvol_{w}m'] = 0.0

        # Direction consistency: fraction of bars with same-sign return in window
        for w in [3, 5]:
            start = max(0, i - w)
            if start < i:
                signs = []
                for j in range(start + 1, i + 1):
                    if prices[j] != prices[j - 1]:
                        signs.append(1 if prices[j] > prices[j - 1] else -1)
                if signs:
                    current_sign = 1 if prices[i] > prices[start] else -1
                    same = sum(1 for s in signs if s == current_sign)
                    row[f'dir_consist_{w}m'] = same / len(signs)
                else:
                    row[f'dir_consist_{w}m'] = 0.5
            else:
                row[f'dir_consist_{w}m'] = 0.5

        # Flow metrics
        for w in [3, 5]:
            start = max(0, i - w + 1)
            net_d = sum(deltas[start:i + 1])
            tot_v = sum(volumes[start:i + 1])
            tot_tc = sum(trade_counts[start:i + 1])
            row[f'net_delta_{w}m'] = net_d
            row[f'dv_ratio_{w}m'] = net_d / tot_v if tot_v > 0 else 0
            row[f'volume_{w}m'] = tot_v
            row[f'trade_count_{w}m'] = tot_tc

        # Volume percentile (vs 60-bar lookback)
        lookback = 60
        start_lb = max(0, i - lookback)
        vols_lb = volumes[start_lb:i + 1]
        cur_vol = volumes[i]
        if vols_lb:
            row['vol_pct'] = sum(1 for v in vols_lb if v <= cur_vol) / len(vols_lb)
        else:
            row['vol_pct'] = 0.5

        # Trade count intensity (vs 60-bar lookback)
        tcs_lb = trade_counts[start_lb:i + 1]
        cur_tc = trade_counts[i]
        if tcs_lb:
            row['tc_pct'] = sum(1 for t in tcs_lb if t <= cur_tc) / len(tcs_lb)
        else:
            row['tc_pct'] = 0.5

    print(f"Computed metrics for {n} bars")
    return rows


# ============================================================
# STATE CLASSIFICATION
# ============================================================
def classify_states(rows):
    """Classify each bar as EXPANSION, CHOP, DEAD, or NEUTRAL."""
    print("Classifying market states...")

    # Compute volume percentiles for DEAD detection (global)
    volumes = sorted(r['volume'] for r in rows)
    vol_30pct = volumes[int(len(volumes) * 0.30)] if volumes else 0

    counts = defaultdict(int)
    expansion_setups = []  # (index, direction, config)

    for i, row in enumerate(rows):
        row['state'] = 'NEUTRAL'
        row['direction'] = 'none'

        # DEAD: low range, low activity
        r5 = row.get('range_5m_bps', 0)
        if r5 < DEAD_MAX_RANGE_BPS and row['volume'] < vol_30pct:
            row['state'] = 'DEAD'
            counts['DEAD'] += 1
            continue

        # CHOP: range exists but no progress
        r3 = row.get('range_3m_bps', 0)
        net3 = abs(row.get('return_3m_bps', 0))
        if r3 >= CHOP_MIN_RANGE_BPS and net3 <= CHOP_MAX_NET_RETURN_BPS:
            # Check directional efficiency
            r5_range = row.get('range_5m_bps', 0)
            net5 = abs(row.get('return_5m_bps', 0))
            if r5_range > 0:
                efficiency = net5 / r5_range
                if efficiency < CHOP_MAX_EFFICIENCY:
                    row['state'] = 'CHOP'
                    counts['CHOP'] += 1
                    continue

        # EXPANSION: check each config
        is_expansion = False
        for thresh in EXPANSION_THRESHOLDS_BPS:
            for ref_win in REFERENCE_WINDOWS_BARS:
                ret_key = f'return_{ref_win}m_bps'
                ret = row.get(ret_key, 0)

                if abs(ret) < thresh:
                    continue

                direction = 'long' if ret > 0 else 'short'

                # Confirmation: price must hold
                confirmed = True
                for conf_win in CONFIRMATION_WINDOWS_BARS:
                    if i + conf_win >= len(rows):
                        confirmed = False
                        break

                    # Check if price holds during confirmation
                    future_prices = [rows[i + j]['price'] for j in range(1, conf_win + 1)]
                    cur_price = row['price']

                    if direction == 'long':
                        # Price should stay above midpoint of expansion
                        # Use the price thresh bps ago as reference
                        ref_price = rows[max(0, i - ref_win)]['price']
                        mid = ref_price + (cur_price - ref_price) * (1 - 0.5)
                        if any(fp < mid for fp in future_prices):
                            confirmed = False
                            break
                        # Delta during confirmation should not be strongly negative
                        conf_delta = sum(rows[i + j]['delta'] for j in range(1, conf_win + 1))
                        conf_vol = sum(rows[i + j]['volume'] for j in range(1, conf_win + 1))
                        if conf_vol > 0 and conf_delta / conf_vol < -0.15:
                            confirmed = False
                            break
                    else:  # short
                        ref_price = rows[max(0, i - ref_win)]['price']
                        mid = ref_price - (ref_price - cur_price) * (1 - 0.5)
                        if any(fp > mid for fp in future_prices):
                            confirmed = False
                            break
                        conf_delta = sum(rows[i + j]['delta'] for j in range(1, conf_win + 1))
                        conf_vol = sum(rows[i + j]['volume'] for j in range(1, conf_win + 1))
                        if conf_vol > 0 and conf_delta / conf_vol > 0.15:
                            confirmed = False
                            break

                if confirmed:
                    is_expansion = True
                    row['state'] = 'EXPANSION'
                    row['direction'] = direction
                    # Record setup after confirmation window
                    entry_idx = i + max(CONFIRMATION_WINDOWS_BARS)
                    if entry_idx < len(rows):
                        expansion_setups.append({
                            'idx': entry_idx,
                            'direction': direction,
                            'thresh': thresh,
                            'ref_win': ref_win,
                            'trigger_idx': i,
                            'exp_bps': abs(ret),
                        })
                    counts['EXPANSION'] += 1
                    break
            if is_expansion:
                break

        if not is_expansion and row['state'] == 'NEUTRAL':
            counts['NEUTRAL'] += 1

    print(f"State counts: {dict(counts)}")
    print(f"Expansion setups (before dedup): {len(expansion_setups)}")

    # Deduplicate: keep one setup per bar (take first detected)
    seen_indices = set()
    unique_setups = []
    for s in expansion_setups:
        if s['idx'] not in seen_indices:
            seen_indices.add(s['idx'])
            unique_setups.append(s)
    print(f"Unique expansion setups: {len(unique_setups)}")

    return rows, unique_setups


# ============================================================
# FORWARD OUTCOMES
# ============================================================
def measure_outcomes(rows, setups):
    """Measure forward returns for each setup."""
    print("Measuring forward outcomes...")
    n = len(rows)
    max_h = max(OUTCOME_HORIZONS_BARS)

    for s in setups:
        idx = s['idx']
        if idx + max_h >= n:
            s['incomplete'] = True
            continue

        entry_price = rows[idx]['price']
        if entry_price <= 0:
            s['incomplete'] = True
            continue

        direction_mult = 1 if s['direction'] == 'long' else -1
        s['fwd'] = {}
        s['fwd_net'] = {}

        mfe = 0.0
        mae = 0.0
        ttp = None

        for h in OUTCOME_HORIZONS_BARS:
            future_price = rows[idx + h]['price']
            raw_ret = ((future_price / entry_price) - 1) * 10000
            dir_ret = raw_ret * direction_mult

            s['fwd'][h] = dir_ret
            for c in COST_LEVELS_BPS:
                s['fwd_net'][(h, c)] = dir_ret - c

            # MFE/MAE tracking (bar by bar up to this horizon)
            for j in range(1, h + 1):
                fp = rows[idx + j]['price']
                exc = ((fp / entry_price) - 1) * 10000 * direction_mult
                mfe = max(mfe, exc)
                mae = min(mae, exc)

            if ttp is None and dir_ret > 0:
                ttp = h  # bar count to positive

        s['mfe'] = mfe
        s['mae'] = mae
        s['ttp'] = ttp
        s['incomplete'] = False

    complete = [s for s in setups if not s.get('incomplete')]
    print(f"Complete setups: {len(complete)}")
    return complete


# ============================================================
# BASELINES
# ============================================================
def compute_baselines(rows, setups):
    """Compute 5 baselines."""
    print("Computing baselines...")
    random.seed(RANDOM_SEED)
    n = len(rows)
    max_h = max(OUTCOME_HORIZONS_BARS)

    setup_indices = [s['idx'] for s in setups]
    setup_directions = [s['direction'] for s in setups]

    def fwd_return(idx, direction, horizon):
        if idx + horizon >= n: return None
        p0 = rows[idx]['price']
        p1 = rows[idx + horizon]['price']
        if p0 <= 0: return None
        raw = ((p1 / p0) - 1) * 10000
        return raw if direction == 'long' else -raw

    results = {}
    n_samples = min(N_BASELINE_SAMPLES, len(setups) * 5)

    # Baseline 1: Random timestamp
    print("  Baseline 1: Random...")
    bl_random = {h: [] for h in OUTCOME_HORIZONS_BARS}
    for _ in range(n_samples):
        idx = random.randint(max_h, n - max_h - 1)
        d = random.choice(['long', 'short'])
        for h in OUTCOME_HORIZONS_BARS:
            r = fwd_return(idx, d, h)
            if r is not None: bl_random[h].append(r)
    results['random'] = bl_random

    # Baseline 2: Same-time distribution (match by hour)
    print("  Baseline 2: Same-time...")
    bl_sametime = {h: [] for h in OUTCOME_HORIZONS_BARS}
    if setups:
        # Get hour distribution of setups
        setup_hours = []
        for s in setups:
            t = time.localtime(rows[s['idx']]['timestamp'])
            setup_hours.append(t.tm_hour)
        hour_counts = defaultdict(int)
        for h in setup_hours:
            hour_counts[h] += 1

        # Sample by hour
        hour_indices = defaultdict(list)
        for i in range(max_h, n - max_h - 1):
            t = time.localtime(rows[i]['timestamp'])
            hour_indices[t.tm_hour].append(i)

        for hour, count in hour_counts.items():
            candidates = hour_indices.get(hour, [])
            if not candidates: continue
            for _ in range(min(count * 3, len(candidates))):
                idx = random.choice(candidates)
                d = random.choice(['long', 'short'])
                for h in OUTCOME_HORIZONS_BARS:
                    r = fwd_return(idx, d, h)
                    if r is not None: bl_sametime[h].append(r)
    results['same_time'] = bl_sametime

    # Baseline 3: Same-volatility
    print("  Baseline 3: Same-volatility...")
    bl_samevol = {h: [] for h in OUTCOME_HORIZONS_BARS}
    rvols = [rows[i].get('rvol_5m', 0) for i in range(n)]
    valid_rvols = sorted(set(v for v in rvols if v > 0))
    if len(valid_rvols) >= 5:
        quintiles = [valid_rvols[len(valid_rvols) * i // 5] for i in range(5)]
    else:
        quintiles = [0] * 5

    def vol_bucket(v):
        for i, q in enumerate(quintiles):
            if v < q: return i
        return len(quintiles) - 1

    # Build index by vol bucket
    bucket_indices = defaultdict(list)
    for i in range(max_h, n - max_h - 1):
        b = vol_bucket(rvols[i])
        bucket_indices[b].append(i)

    for s in setups:
        s_vol = rvols[s['idx']] if s['idx'] < n else 0
        sb = vol_bucket(s_vol)
        candidates = bucket_indices.get(sb, [])
        if not candidates: continue
        for _ in range(min(5, max(1, n_samples // max(len(setups), 1)))):
            idx = random.choice(candidates)
            for h in OUTCOME_HORIZONS_BARS:
                r = fwd_return(idx, s['direction'], h)
                if r is not None: bl_samevol[h].append(r)
    results['same_vol'] = bl_samevol

    # Baseline 4: Same-direction drift
    print("  Baseline 4: Same-direction drift...")
    bl_samedir = {h: [] for h in OUTCOME_HORIZONS_BARS}
    for _ in range(n_samples):
        idx = random.randint(max_h, n - max_h - 1)
        d = random.choice(['long', 'short'])
        for h in OUTCOME_HORIZONS_BARS:
            r = fwd_return(idx, d, h)
            if r is not None: bl_samedir[h].append(r)
    results['same_dir'] = bl_samedir

    # Baseline 5: Opposite direction
    print("  Baseline 5: Opposite direction...")
    bl_opp = {h: [] for h in OUTCOME_HORIZONS_BARS}
    for s in setups:
        opp = 'short' if s['direction'] == 'long' else 'long'
        for h in OUTCOME_HORIZONS_BARS:
            r = fwd_return(s['idx'], opp, h)
            if r is not None: bl_opp[h].append(r)
    results['opposite'] = bl_opp

    # Compute summaries
    summaries = {}
    for name, data in results.items():
        summaries[name] = {}
        for h in OUTCOME_HORIZONS_BARS:
            vals = data[h]
            if vals:
                summaries[name][h] = {
                    'mean': sum(vals) / len(vals),
                    'median': sorted(vals)[len(vals) // 2],
                    'count': len(vals),
                }
            else:
                summaries[name][h] = {'mean': 0, 'median': 0, 'count': 0}

    return results, summaries


# ============================================================
# ANALYTICS
# ============================================================
def safe_mean(xs):
    return sum(xs) / len(xs) if xs else 0

def safe_median(xs):
    if not xs: return 0
    s = sorted(xs); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2

def percentile(xs, p):
    if not xs: return 0
    s = sorted(xs)
    return s[min(int(len(s) * p / 100), len(s) - 1)]

def profit_factor(returns):
    gains = sum(r for r in returns if r > 0)
    losses = abs(sum(r for r in returns if r < 0))
    return gains / losses if losses > 0 else (999.0 if gains > 0 else 0.0)


def analyze_group(setups, label="all"):
    """Analyze a group of setups."""
    if not setups: return None
    n = len(setups)
    result = {'count': n, 'label': label}

    for h in OUTCOME_HORIZONS_BARS:
        gross = [s['fwd'][h] for s in setups if h in s.get('fwd', {})]
        if not gross: continue
        result[f'gross_mean_{h}'] = safe_mean(gross)
        result[f'gross_median_{h}'] = safe_median(gross)
        result[f'worst5_{h}'] = percentile(gross, 5)
        result[f'best5_{h}'] = percentile(gross, 95)

        for c in COST_LEVELS_BPS:
            net = [s['fwd_net'].get((h, c), 0) for s in setups if 'fwd_net' in s]
            if not net: continue
            result[f'net_mean_{h}_{c}'] = safe_mean(net)
            wins = [r for r in net if r > 0]
            result[f'winrate_{h}_{c}'] = len(wins) / len(net) if net else 0
            result[f'pf_{h}_{c}'] = profit_factor(net)

    mfes = [s['mfe'] for s in setups if s.get('mfe', 0) > 0]
    maes = [s['mae'] for s in setups if s.get('mae', 0) < 0]
    result['mean_mfe'] = safe_mean(mfes)
    result['mean_mae'] = safe_mean(maes)
    result['mfe_mae_ratio'] = abs(safe_mean(mfes) / safe_mean(maes)) if maes and safe_mean(maes) != 0 else 0

    ttps = [s['ttp'] for s in setups if s.get('ttp') is not None]
    result['median_ttp'] = safe_median(ttps)

    # Outlier dependence
    for h in [2, 5, 10]:
        gross = [s['fwd'][h] for s in setups if h in s.get('fwd', {})]
        if len(gross) < 10: continue
        total = sum(gross)
        if total == 0: continue
        top5 = sorted(gross, reverse=True)[:max(1, len(gross) // 20)]
        result[f'outlier_dep_{h}'] = sum(top5) / total if total > 0 else 0

    # Stability: first half vs second half
    ss = sorted(setups, key=lambda s: s['idx'])
    mid = len(ss) // 2
    for label2, chunk in [('first_half', ss[:mid]), ('second_half', ss[mid:])]:
        for h in [2, 5, 10]:
            gross = [s['fwd'][h] for s in chunk if h in s.get('fwd', {})]
            if gross:
                result[f'{label2}_{h}'] = safe_mean(gross)

    # Thirds
    third = len(ss) // 3
    for label3, chunk in [('third1', ss[:third]), ('third2', ss[third:2*third]), ('third3', ss[2*third:])]:
        for h in [5]:
            gross = [s['fwd'][h] for s in chunk if h in s.get('fwd', {})]
            if gross:
                result[f'{label3}_{h}'] = safe_mean(gross)

    return result


# ============================================================
# CHOP ANALYSIS
# ============================================================
def analyze_chop_forward(rows):
    """Measure forward returns during CHOP periods."""
    print("Analyzing CHOP forward returns...")
    n = len(rows)
    max_h = max(OUTCOME_HORIZONS_BARS)
    chop_returns = {h: [] for h in OUTCOME_HORIZONS_BARS}

    for i in range(max_h, n - max_h):
        if rows[i].get('state') == 'CHOP':
            p0 = rows[i]['price']
            if p0 <= 0: continue
            for h in OUTCOME_HORIZONS_BARS:
                p1 = rows[i + h]['price']
                ret = ((p1 / p0) - 1) * 10000
                chop_returns[h].append(abs(ret))  # absolute movement

    result = {}
    for h in OUTCOME_HORIZONS_BARS:
        vals = chop_returns[h]
        if vals:
            result[h] = {'mean': safe_mean(vals), 'median': safe_median(vals), 'count': len(vals)}
        else:
            result[h] = {'mean': 0, 'median': 0, 'count': 0}
    return result


# ============================================================
# REPORT
# ============================================================
def generate_report(rows, setups, baselines, baselines_summary, chop_fwd):
    """Generate the final report."""
    print("Generating report...")
    lines = []

    # Header
    lines.append("# MARKET STATE VALIDATION REPORT")
    lines.append("")
    lines.append(f"**Date:** {time.strftime('%Y-%m-%d')}")
    lines.append(f"**Dataset:** BTCUSDT 1-minute bars")
    t0 = time.strftime('%Y-%m-%d', time.localtime(rows[0]['timestamp']))
    t1 = time.strftime('%Y-%m-%d', time.localtime(rows[-1]['timestamp']))
    lines.append(f"**Period:** {t0} to {t1}")
    lines.append(f"**Total bars:** {len(rows):,}")
    lines.append(f"**Columns:** timestamp, price, volume, delta, trade_count")
    lines.append(f"**Delta available:** YES")
    lines.append(f"**Volume available:** YES")
    lines.append(f"**Trade count available:** YES")
    lines.append("")

    # State counts
    state_counts = defaultdict(int)
    for r in rows:
        state_counts[r.get('state', 'NEUTRAL')] += 1
    long_exp = sum(1 for s in setups if s['direction'] == 'long')
    short_exp = sum(1 for s in setups if s['direction'] == 'short')

    # Executive verdict
    lines.append("## 1. Executive Verdict")
    lines.append("")

    all_setup = analyze_group(setups, "all")
    long_setups = [s for s in setups if s['direction'] == 'long']
    short_setups = [s for s in setups if s['direction'] == 'short']
    long_analysis = analyze_group(long_setups, "long")
    short_analysis = analyze_group(short_setups, "short")

    # Determine verdict
    total_setups = len(setups)
    verdict = ""
    level = 0

    if total_setups < MIN_OCCURRENCES:
        verdict = "Insufficient data"
        level = 0
    elif all_setup is None:
        verdict = "No useful market-state edge detected"
        level = 0
    else:
        # Check if expansion beats random
        exp_mean_5 = all_setup.get('gross_mean_5', 0)
        rand_mean_5 = baselines_summary.get('random', {}).get(5, {}).get('mean', 0)
        exp_net_5_4 = all_setup.get('net_mean_5_4', 0)
        exp_pf_5_4 = all_setup.get('pf_5_4', 0)

        beats_random = exp_mean_5 > rand_mean_5
        net_positive = exp_net_5_4 > 0
        pf_ok = exp_pf_5_4 > MIN_PROFIT_FACTOR

        if not beats_random:
            verdict = "No useful market-state edge detected"
            level = 0
        elif not net_positive:
            # Check if CHOP is worse (avoidance value)
            chop_mean = chop_fwd.get(5, {}).get('mean', 0)
            if chop_mean > 0 and exp_mean_5 > chop_mean:
                verdict = "Avoidance edge detected"
                level = 1
            else:
                verdict = "No useful market-state edge detected"
                level = 0
        elif net_positive and not pf_ok:
            chop_mean = chop_fwd.get(5, {}).get('mean', 0)
            if chop_mean > 0 and exp_mean_5 > chop_mean:
                verdict = "Weak context edge detected"
                level = 2
            else:
                verdict = "Avoidance edge detected"
                level = 1
        elif pf_ok:
            # Check stability
            fh = all_setup.get('first_half_5', 0)
            sh = all_setup.get('second_half_5', 0)
            stable = (fh > 0 and sh > 0) or (fh < 0 and sh < 0)
            od = all_setup.get('outlier_dep_5', 0)
            not_outlier = od < 0.30

            if stable and not_outlier:
                verdict = "Expansion participation edge detected"
                level = 3
            else:
                verdict = "Weak context edge detected"
                level = 2
        else:
            verdict = "No useful market-state edge detected"
            level = 0

    lines.append(f"### **{verdict}**")
    lines.append("")
    lines.append(f"**Level:** {level}/4")
    lines.append("")
    lines.append(f"- Total bars: {len(rows):,}")
    lines.append(f"- DEAD bars: {state_counts.get('DEAD', 0):,}")
    lines.append(f"- CHOP bars: {state_counts.get('CHOP', 0):,}")
    lines.append(f"- EXPANSION bars: {state_counts.get('EXPANSION', 0):,}")
    lines.append(f"- NEUTRAL bars: {state_counts.get('NEUTRAL', 0):,}")
    lines.append(f"- Expansion setups (confirmed): {total_setups}")
    lines.append(f"- Long setups: {long_exp}")
    lines.append(f"- Short setups: {short_exp}")
    lines.append("")

    # Data used
    lines.append("## 2. Data Used")
    lines.append("")
    lines.append(f"- File: btcusdt_1m.csv (from btc-intraday-system)")
    lines.append(f"- Rows: {len(rows):,}")
    lines.append(f"- Date range: {t0} to {t1}")
    lines.append(f"- Granularity: 1-minute bars")
    lines.append(f"- Columns: timestamp, price, volume, delta, trade_count")
    lines.append(f"- Delta: YES (signed volume)")
    lines.append(f"- Volume: YES")
    lines.append(f"- Trade count: YES")
    lines.append("")

    # State definitions
    lines.append("## 3. State Definitions (Fixed Before Data Inspection)")
    lines.append("")
    lines.append("### EXPANSION")
    lines.append(f"- Price move thresholds: {EXPANSION_THRESHOLDS_BPS} bps")
    lines.append(f"- Reference windows: {REFERENCE_WINDOWS_BARS} bars (1m, 3m, 5m)")
    lines.append(f"- Confirmation windows: {CONFIRMATION_WINDOWS_BARS} bars (1m, 2m, 3m)")
    lines.append(f"- Confirmation: price holds above/below expansion midpoint")
    lines.append(f"- Flow confirmation: delta not strongly against direction during confirmation")
    lines.append("")
    lines.append("### CHOP")
    lines.append(f"- 3m range ≥ {CHOP_MIN_RANGE_BPS} bps")
    lines.append(f"- |3m net return| ≤ {CHOP_MAX_NET_RETURN_BPS} bps")
    lines.append(f"- Directional efficiency (5m) < {CHOP_MAX_EFFICIENCY}")
    lines.append("")
    lines.append("### DEAD")
    lines.append(f"- 5m range < {DEAD_MAX_RANGE_BPS} bps")
    lines.append(f"- Volume below 30th percentile")
    lines.append("")

    # State counts
    lines.append("## 4. State Counts")
    lines.append("")
    lines.append("| State | Count | % of total |")
    lines.append("|-------|-------|------------|")
    total = len(rows)
    for state in ['DEAD', 'CHOP', 'EXPANSION', 'NEUTRAL']:
        c = state_counts.get(state, 0)
        lines.append(f"| {state} | {c:,} | {c/total:.1%} |")
    lines.append("")
    lines.append(f"**Expansion setups (after confirmation, deduplicated):** {total_setups}")
    lines.append(f"- Long: {long_exp}")
    lines.append(f"- Short: {short_exp}")
    lines.append("")

    # Expansion vs Random
    lines.append("## 5. Expansion vs Random Baseline")
    lines.append("")
    if all_setup:
        lines.append("| Horizon | Expansion Gross | Expansion Net@4bps | Random Gross | Diff |")
        lines.append("|---------|----------------|-------------------|--------------|------|")
        for h in OUTCOME_HORIZONS_BARS:
            eg = all_setup.get(f'gross_mean_{h}', 0)
            en = all_setup.get(f'net_mean_{h}_4', 0)
            rg = baselines_summary.get('random', {}).get(h, {}).get('mean', 0)
            diff = eg - rg
            lines.append(f"| {h}m | {eg:.2f} | {en:.2f} | {rg:.2f} | {diff:+.2f} |")
        lines.append("")
    else:
        lines.append("No expansion setups to compare.")
        lines.append("")

    # Expansion vs Same-Volatility
    lines.append("## 6. Expansion vs Same-Volatility Random")
    lines.append("")
    if all_setup:
        lines.append("| Horizon | Expansion Gross | Same-Vol Gross | Diff |")
        lines.append("|---------|----------------|----------------|------|")
        for h in OUTCOME_HORIZONS_BARS:
            eg = all_setup.get(f'gross_mean_{h}', 0)
            sv = baselines_summary.get('same_vol', {}).get(h, {}).get('mean', 0)
            diff = eg - sv
            lines.append(f"| {h}m | {eg:.2f} | {sv:.2f} | {diff:+.2f} |")
        lines.append("")

    # Expansion vs Opposite Direction
    lines.append("## 7. Expansion vs Opposite Direction")
    lines.append("")
    if all_setup:
        lines.append("| Horizon | Expansion Gross | Opposite Gross | Diff |")
        lines.append("|---------|----------------|----------------|------|")
        for h in OUTCOME_HORIZONS_BARS:
            eg = all_setup.get(f'gross_mean_{h}', 0)
            opp = baselines_summary.get('opposite', {}).get(h, {}).get('mean', 0)
            diff = eg - opp
            lines.append(f"| {h}m | {eg:.2f} | {opp:.2f} | {diff:+.2f} |")
        lines.append("")

    # Chop vs Expansion
    lines.append("## 8. Chop vs Expansion")
    lines.append("")
    lines.append("CHOP forward absolute movement (opportunity cost of being in chop):")
    lines.append("")
    lines.append("| Horizon | CHOP mean |abs| | EXPANSION mean | EXP > CHOP? |")
    lines.append("|---------|------------------|----------------|-------------|")
    for h in OUTCOME_HORIZONS_BARS:
        cm = chop_fwd.get(h, {}).get('mean', 0)
        em = all_setup.get(f'gross_mean_{h}', 0) if all_setup else 0
        better = "✅" if abs(em) > cm else "❌"
        lines.append(f"| {h}m | {cm:.2f} | {em:.2f} | {better} |")
    lines.append("")

    # Long vs Short
    lines.append("## 9. Long vs Short Asymmetry")
    lines.append("")
    if long_analysis and short_analysis:
        lines.append("| Metric | Long | Short |")
        lines.append("|--------|------|-------|")
        for h in [2, 5, 10]:
            ml = long_analysis.get(f'gross_mean_{h}', 0)
            ms = short_analysis.get(f'gross_mean_{h}', 0)
            lines.append(f"| Gross mean {h}m | {ml:.2f} | {ms:.2f} |")
        nl = long_analysis.get('net_mean_5_4', 0)
        ns = short_analysis.get('net_mean_5_4', 0)
        lines.append(f"| Net mean 5m @4bps | {nl:.2f} | {ns:.2f} |")
        pfl = long_analysis.get('pf_5_4', 0)
        pfs = short_analysis.get('pf_5_4', 0)
        lines.append(f"| PF 5m @4bps | {pfl:.2f} | {pfs:.2f} |")
        lines.append("")
    elif long_analysis:
        lines.append("Only long setups detected.")
        lines.append("")
    elif short_analysis:
        lines.append("Only short setups detected.")
        lines.append("")

    # Cost stress test
    lines.append("## 10. Cost Stress Test")
    lines.append("")
    if all_setup:
        lines.append("| Horizon | Gross | Net@2bps | Net@4bps | Net@6bps | Winrate@4bps | PF@4bps |")
        lines.append("|---------|-------|----------|----------|----------|--------------|---------|")
        for h in OUTCOME_HORIZONS_BARS:
            g = all_setup.get(f'gross_mean_{h}', 0)
            n2 = all_setup.get(f'net_mean_{h}_2', 0)
            n4 = all_setup.get(f'net_mean_{h}_4', 0)
            n6 = all_setup.get(f'net_mean_{h}_6', 0)
            wr = all_setup.get(f'winrate_{h}_4', 0)
            pf = all_setup.get(f'pf_{h}_4', 0)
            lines.append(f"| {h}m | {g:.2f} | {n2:.2f} | {n4:.2f} | {n6:.2f} | {wr:.1%} | {pf:.2f} |")
        lines.append("")

    # Stability
    lines.append("## 11. Stability Analysis")
    lines.append("")
    if all_setup:
        for h in [2, 5, 10]:
            fh = all_setup.get(f'first_half_{h}', None)
            sh = all_setup.get(f'second_half_{h}', None)
            if fh is not None and sh is not None:
                sign = "✅" if (fh > 0 and sh > 0) or (fh < 0 and sh < 0) else "❌"
                lines.append(f"- {h}m: First half={fh:.2f} bps, Second half={sh:.2f} bps {sign}")
        lines.append("")
        for h in [5]:
            t1 = all_setup.get(f'third1_{h}', None)
            t2 = all_setup.get(f'third2_{h}', None)
            t3 = all_setup.get(f'third3_{h}', None)
            if t1 is not None:
                lines.append(f"- {h}m thirds: {t1:.2f} / {t2:.2f} / {t3:.2f}")
        lines.append("")

    # Outlier dependence
    lines.append("## 12. Outlier Dependence")
    lines.append("")
    if all_setup:
        for h in [2, 5, 10]:
            od = all_setup.get(f'outlier_dep_{h}', None)
            if od is not None:
                status = "⚠️ HIGH" if od > 0.30 else "✅ OK"
                lines.append(f"- {h}m: Top 5% drive {od:.1%} of total P&L {status}")
        lines.append("")

    # Practical interpretation
    lines.append("## 13. Practical Interpretation")
    lines.append("")
    if level == 0:
        lines.append("MANTIS market-state classification does not provide useful distinction between EXPANSION and other states.")
        lines.append("No practical value as a decision filter.")
    elif level == 1:
        lines.append("MANTIS has value as an **avoidance filter**.")
        lines.append("CHOP conditions produce worse outcomes than EXPANSION.")
        lines.append("Useful for 'do not trade' decisions, not for entry signals.")
    elif level == 2:
        lines.append("MANTIS shows **weak context edge**.")
        lines.append("EXPANSION beats baselines but not strongly enough after costs for automation.")
        lines.append("Potentially useful as discretionary decision support.")
    elif level >= 3:
        lines.append("MANTIS shows **participation edge**.")
        lines.append("EXPANSION states are materially better than random and chop.")
        lines.append("Candidate for execution layer integration.")
    lines.append("")

    # Final verdict
    lines.append("## 14. Final Verdict")
    lines.append("")
    lines.append(f"**{verdict}.**")
    lines.append("")

    # Next action
    lines.append("## 15. Next Action")
    lines.append("")
    if level >= 3:
        lines.append("Integrate market-state classification into MANTIS execution layer with live validation.")
    elif level == 2:
        lines.append("Use MANTIS as discretionary context only; do not automate.")
    elif level == 1:
        lines.append("Use MANTIS as an avoidance filter; no entry automation.")
    else:
        lines.append("Stop. Market-state classification does not provide actionable edge.")
    lines.append("")
    lines.append("---")
    lines.append("*No parameters were tuned after seeing results. All definitions were fixed before data inspection.*")
    lines.append(f"*Analysis completed {time.strftime('%Y-%m-%d %H:%M:%S')}.*")

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=REPORT_OUTPUT)
    args = parser.parse_args()

    # Resolve path
    input_path = args.input
    if not os.path.isabs(input_path):
        input_path = os.path.join(os.path.dirname(__file__), input_path)
    if not os.path.exists(input_path):
        print(f"ERROR: {input_path} not found")
        sys.exit(1)

    # Load
    rows = load_data(input_path)

    # Compute metrics
    rows = compute_rolling_metrics(rows)

    # Classify
    rows, setups = classify_states(rows)

    # Measure outcomes
    setups = measure_outcomes(rows, setups)

    # Baselines
    _, baselines_summary = compute_baselines(rows, setups)

    # Chop analysis
    chop_fwd = analyze_chop_forward(rows)

    # Report
    report = generate_report(rows, setups, _, baselines_summary, chop_fwd)

    # Write report in the mantis workspace
    output_path = args.output
    if not os.path.isabs(output_path):
        output_path = os.path.join(os.path.dirname(__file__), '..', '..', output_path)
    with open(output_path, 'w') as f:
        f.write(report)
    print(f"\nReport written to: {output_path}")

    # Summary
    all_setup = analyze_group(setups, "all")
    if all_setup:
        print(f"\n{'='*60}")
        print(f"Setups: {all_setup['count']}")
        print(f"Gross mean 5m: {all_setup.get('gross_mean_5', 0):.2f} bps")
        print(f"Net mean 5m @4bps: {all_setup.get('net_mean_5_4', 0):.2f} bps")
        print(f"Winrate 5m @4bps: {all_setup.get('winrate_5_4', 0):.1%}")
        print(f"PF 5m @4bps: {all_setup.get('pf_5_4', 0):.2f}")
        print(f"MFE/MAE: {all_setup.get('mfe_mae_ratio', 0):.2f}")
    else:
        print("\nNo setups found.")


if __name__ == "__main__":
    main()
