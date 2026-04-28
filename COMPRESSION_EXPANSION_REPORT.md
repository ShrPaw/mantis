# COMPRESSION → EXPANSION REPORT

**Date:** 2026-04-28
**Generated:** 2026-04-28 10:19:45

## 1. Data Summary

- **Source:** Binance BTC/USDT 1-minute bars (historical)
- **Bars:** 482,400
- **Duration:** 335 days (11.2 months)
- **Period:** 2025-05-01 to 2026-03-31 UTC

## 2. Compression Definition

**Compression = market storing energy**

A 1-minute bar is in COMPRESSION state if:
- Realized volatility (over [10, 30, 60] min windows) is in bottom 20% of last 24h
  AND
- High-low range (over [10, 30, 60] min windows) is in bottom 20% of last 24h

Consecutive compressed bars form a **compression box** (high/low of the compressed period).

- **Compression bars:** 28,232 (5.9% of data)
- **Compression boxes:** 3374

## 3. Breakout Logic

**LONG:** Price closes above compression box high
**SHORT:** Price closes below compression box low
**Confirmation:** Price stays outside box for [1, 3, 5] min
**Entry:** Close price AFTER confirmation window

## 4. Results vs Baselines

**Total breakouts:** 3374
- Long: 1691
- Short: 1683

### All (N=3374)

| Horizon | Gross Mean(bps) | Gross Median(bps) | Net@4bps Mean | Winrate@4bps | PF@4bps |
|---------|-----------------|-------------------|---------------|--------------|---------|
| 5m | 0.17 | -0.00 | -3.83 | 24.9% | 0.32 |
| 15m | -0.24 | -0.22 | -4.24 | 32.8% | 0.46 |
| 30m | -0.63 | -0.96 | -4.63 | 36.6% | 0.55 |
| 60m | -0.65 | -0.79 | -4.65 | 40.1% | 0.65 |
| 120m | -0.54 | -1.68 | -4.54 | 42.3% | 0.76 |

- **Mean MFE:** 35.18 bps
- **Mean MAE:** -34.80 bps
- **MFE/MAE ratio:** 1.01
- **Median time-to-positive:** 2.0 min
- **Mean box duration:** 8.4 min
- **Mean box range:** 6.9 bps

**Quarterly stability (60m horizon):**

- Q1: -1.18 bps (N=843)
- Q2: 0.00 bps (N=843)
- Q3: -2.75 bps (N=843)
- Q4: 1.30 bps (N=843)

### Long (N=1691)

| Horizon | Gross Mean(bps) | Gross Median(bps) | Net@4bps Mean | Winrate@4bps | PF@4bps |
|---------|-----------------|-------------------|---------------|--------------|---------|
| 5m | -0.16 | -0.08 | -4.16 | 23.8% | 0.28 |
| 15m | -0.53 | -0.69 | -4.53 | 32.5% | 0.43 |
| 30m | -1.57 | -1.75 | -5.57 | 35.0% | 0.48 |
| 60m | -2.89 | -1.12 | -6.89 | 38.4% | 0.52 |
| 120m | -4.36 | -3.35 | -8.36 | 40.6% | 0.58 |

- **Mean MFE:** 31.29 bps
- **Mean MAE:** -36.14 bps
- **MFE/MAE ratio:** 0.87
- **Median time-to-positive:** 2.0 min
- **Mean box duration:** 8.4 min
- **Mean box range:** 6.8 bps

**Quarterly stability (60m horizon):**

- Q1: -1.51 bps (N=422)
- Q2: -0.48 bps (N=422)
- Q3: -6.84 bps (N=422)
- Q4: -2.80 bps (N=422)

### Short (N=1683)

| Horizon | Gross Mean(bps) | Gross Median(bps) | Net@4bps Mean | Winrate@4bps | PF@4bps |
|---------|-----------------|-------------------|---------------|--------------|---------|
| 5m | 0.50 | 0.00 | -3.50 | 26.0% | 0.35 |
| 15m | 0.06 | 0.16 | -3.94 | 33.1% | 0.50 |
| 30m | 0.33 | -0.11 | -3.67 | 38.2% | 0.63 |
| 60m | 1.59 | -0.44 | -2.41 | 41.7% | 0.81 |
| 120m | 3.31 | -0.42 | -0.69 | 44.0% | 0.96 |

- **Mean MFE:** 39.07 bps
- **Mean MAE:** -33.46 bps
- **MFE/MAE ratio:** 1.17
- **Median time-to-positive:** 1.0 min
- **Mean box duration:** 8.4 min
- **Mean box range:** 7.1 bps

**Quarterly stability (60m horizon):**

- Q1: -1.33 bps (N=420)
- Q2: 0.88 bps (N=420)
- Q3: 1.15 bps (N=420)
- Q4: 5.69 bps (N=420)

### Baseline Comparison

| Baseline | 30m mean(bps) | 60m mean(bps) | 120m mean(bps) | Count |
|----------|---------------|---------------|----------------|-------|
| random | -1.07 | -1.11 | -0.18 | 5000 |
| same_vol | 0.59 | 0.62 | 0.27 | 4468 |
| drift | -0.01 | 0.03 | 0.54 | 5000 |
| opposite | 0.63 | 0.66 | 0.54 | 3374 |

**Edge vs baselines (60m horizon):**

- ✅ vs random: +0.45 bps (setup=-0.65, baseline=-1.11)
- ❌ vs same_vol: -1.28 bps (setup=-0.65, baseline=0.62)
- ❌ vs drift: -0.69 bps (setup=-0.65, baseline=0.03)
- ❌ vs opposite: -1.31 bps (setup=-0.65, baseline=0.66)

## 5. Cost Analysis

| Horizon | Gross | Net@2bps | Net@4bps | Net@6bps |
|---------|-------|----------|----------|----------|
| 5m | 0.17 | -1.83 | -3.83 | -5.83 |
| 15m | -0.24 | -2.24 | -4.24 | -6.24 |
| 30m | -0.63 | -2.63 | -4.63 | -6.63 |
| 60m | -0.65 | -2.65 | -4.65 | -6.65 |
| 120m | -0.54 | -2.54 | -4.54 | -6.54 |

## 6. Stability

- **30m:** First half=-0.76 bps, Second half=-0.49 bps ✅
- **60m:** First half=-0.59 bps, Second half=-0.72 bps ✅
- **120m:** First half=-0.56 bps, Second half=-0.51 bps ✅

## 7. Failure Classification

- No meaningful expansion after compression (|mean 30m| < 1 bps)

## 8. Final Verdict

| Criterion | Status | Value |
|-----------|--------|-------|
| Occurrences ≥ 100 | ✅ | 3374 |
| Mean net @4bps ≥ 0 | ❌ | -4.63 bps |
| PF > 1.1 | ❌ | 0.55 |
| MFE >> MAE | ✅ | 1.01 |
| Outlier dep < 30% | ✅ | 0.0% |
| Same sign across halves | ✅ | 1st=-0.59, 2nd=-0.72 |
| Beats random baseline | ✅ | setup=-0.65, rand=-1.11 |

### ❌ EDGE NOT VALIDATED

Failed criteria: Mean net @4bps ≥ 0, PF > 1.1
## 9. Next Action

**ONE:** This path is closed. Compression → expansion does not produce edge at these definitions.

---
*No parameters were tuned after seeing results. All thresholds are structural assumptions.*
*Analysis completed 2026-04-28 10:19:45.*