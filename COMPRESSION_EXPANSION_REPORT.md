# COMPRESSION → EXPANSION REPORT

**Date:** 2026-04-28
**Generated:** 2026-04-28 10:11:20

## 1. Data Summary

- **Source:** Binance BTC/USDT 1-minute bars
- **Bars:** 10081
- **Duration:** 168.0 hours
- **Period:** 2026-04-21 02:10 to 2026-04-28 02:10 UTC

## 2. Compression Definition

**Compression = market storing energy**

A 1-minute bar is in COMPRESSION state if:

- Realized volatility (over [10, 30, 60] min windows) is in bottom 20% of last 24h
  AND
- High-low range (over [10, 30, 60] min windows) is in bottom 20% of last 24h

Consecutive compressed bars form a **compression box** (defined by the high/low of the compressed period).

- **Total compression bars detected:** 515 (5.1% of data)
- **Compression boxes:** 64

## 3. Breakout Logic

**LONG breakout:** Price closes above compression box high

**SHORT breakout:** Price closes below compression box low

**Confirmation:** Price must remain outside the box for [1, 3, 5] minutes

**Entry:** Close price after confirmation window (NOT at breakout)

## 4. Results vs Baselines

**Total breakouts:** 64
- Long: 34
- Short: 30

### All (N=64)

| Horizon | Gross Mean(bps) | Gross Median(bps) | Net@4bps Mean | Winrate@4bps | PF@4bps |
|---------|-----------------|-------------------|---------------|--------------|---------|
| 5m | 0.21 | -0.45 | -3.79 | 21.9% | 0.20 |
| 15m | -0.96 | -1.17 | -4.96 | 28.1% | 0.34 |
| 30m | -3.28 | -2.51 | -7.28 | 31.2% | 0.25 |
| 60m | -3.00 | -1.24 | -7.00 | 39.1% | 0.35 |
| 120m | -1.52 | -2.94 | -5.52 | 43.8% | 0.58 |

- **Mean MFE:** 22.69 bps
- **Mean MAE:** -26.78 bps
- **MFE/MAE ratio:** 0.85
- **Median time-to-positive:** 2.0 min
- **Mean box duration:** 8.0 min
- **Mean box range:** 5.6 bps

### Long (N=34)

| Horizon | Gross Mean(bps) | Gross Median(bps) | Net@4bps Mean | Winrate@4bps | PF@4bps |
|---------|-----------------|-------------------|---------------|--------------|---------|
| 5m | -0.51 | -0.71 | -4.51 | 20.6% | 0.11 |
| 15m | -1.92 | -2.05 | -5.92 | 20.6% | 0.22 |
| 30m | -1.89 | 1.01 | -5.89 | 35.3% | 0.29 |
| 60m | 1.35 | 4.66 | -2.65 | 52.9% | 0.60 |
| 120m | 3.00 | 4.38 | -1.00 | 52.9% | 0.89 |

- **Mean MFE:** 25.78 bps
- **Mean MAE:** -23.20 bps
- **MFE/MAE ratio:** 1.11
- **Median time-to-positive:** 2.0 min
- **Mean box duration:** 7.3 min
- **Mean box range:** 6.0 bps

### Short (N=30)

| Horizon | Gross Mean(bps) | Gross Median(bps) | Net@4bps Mean | Winrate@4bps | PF@4bps |
|---------|-----------------|-------------------|---------------|--------------|---------|
| 5m | 1.02 | -0.31 | -2.98 | 23.3% | 0.32 |
| 15m | 0.14 | 0.82 | -3.86 | 36.7% | 0.48 |
| 30m | -4.86 | -5.65 | -8.86 | 26.7% | 0.22 |
| 60m | -7.93 | -12.95 | -11.93 | 23.3% | 0.23 |
| 120m | -6.65 | -8.23 | -10.65 | 33.3% | 0.40 |

- **Mean MFE:** 19.18 bps
- **Mean MAE:** -30.83 bps
- **MFE/MAE ratio:** 0.62
- **Median time-to-positive:** 1.5 min
- **Mean box duration:** 8.9 min
- **Mean box range:** 5.1 bps

### Baseline Comparison

| Baseline | 30m mean(bps) | 60m mean(bps) | 120m mean(bps) | Count |
|----------|---------------|---------------|----------------|-------|
| random | 0.38 | 0.98 | 1.68 | 640 |
| same_vol | 0.63 | 1.13 | 0.52 | 640 |
| drift | 0.25 | 0.05 | -1.00 | 640 |
| opposite | 3.28 | 3.00 | 1.52 | 64 |

**Edge vs baselines (60m horizon):**

- ❌ vs random: -3.98 bps (setup=-3.00, baseline=0.98)
- ❌ vs same_vol: -4.13 bps (setup=-3.00, baseline=1.13)
- ❌ vs drift: -3.06 bps (setup=-3.00, baseline=0.05)
- ❌ vs opposite: -6.00 bps (setup=-3.00, baseline=3.00)

## 5. Cost Analysis

| Horizon | Gross | Net@2bps | Net@4bps | Net@6bps |
|---------|-------|----------|----------|----------|
| 5m | 0.21 | -1.79 | -3.79 | -5.79 |
| 15m | -0.96 | -2.96 | -4.96 | -6.96 |
| 30m | -3.28 | -5.28 | -7.28 | -9.28 |
| 60m | -3.00 | -5.00 | -7.00 | -9.00 |
| 120m | -1.52 | -3.52 | -5.52 | -7.52 |

## 6. Stability

- **30m:** First half=-3.01 bps, Second half=-3.55 bps ✅
- **60m:** First half=-2.70 bps, Second half=-3.31 bps ✅

## 7. Failure Classification

- Direction is random — both sides move same way
- MFE < MAE — adverse excursion exceeds favorable

## 8. Final Verdict

| Criterion | Status | Value |
|-----------|--------|-------|
| Occurrences ≥ 100 | ❌ | 64 |
| Mean net @4bps ≥ 0 | ❌ | -7.28 bps |
| PF > 1.1 | ❌ | 0.25 |
| MFE >> MAE | ❌ | 0.85 |
| Outlier dep < 30% | ✅ | 0.0% |
| Same sign across halves | ✅ | 1st=-2.70, 2nd=-3.31 |
| Beats random baseline | ❌ | setup=-3.00, rand=0.98 |

### ❌ EDGE NOT VALIDATED

Failed criteria: Occurrences ≥ 100, Mean net @4bps ≥ 0, PF > 1.1, MFE >> MAE, Beats random baseline
## 9. Next Action

**ONE:** Collect significantly more data (3-7 days of 1m bars) to reach minimum sample size, then re-run.

---
*No parameters were tuned after seeing results. All thresholds are structural assumptions.*
*Analysis completed 2026-04-28 10:11:20.*