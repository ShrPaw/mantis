# FUNDING / POSITIONING PRESSURE REPORT

**Date:** 2026-04-28
**Generated:** 2026-04-28 10:47:32

## 1. Data Summary

- **Price data:** 482,400 1m bars (335 days)
- **Period:** 2025-05-01 to 2026-03-31 UTC
- **Funding events:** 319
  - Long crowded: 151
  - Short crowded: 168

## 2. Event Definitions

- **Funding lookback:** 24h rolling window
- **Extreme threshold:** ±2.0σ from rolling mean
- **Persistence thresholds:** [1, 2, 3] consecutive intervals
- **Long crowded:** funding > mean + 2σ (longs pay shorts)
- **Short crowded:** funding < mean - 2σ (shorts pay longs)

**Hypothesis H1 — Mean Reversion:**
- Long crowded → price falls (overleveraged longs unwind)
- Short crowded → price rises (overleveraged shorts cover)

**Hypothesis H2 — Continuation:**
- Long crowded → price continues up (strong demand)
- Short crowded → price continues down (strong selling)

## 3. Results by Horizon

### Mean Reversion (H1) — All Events (N=319)

| Horizon | Gross Mean(bps) | Gross Median(bps) | Net@4bps | Winrate@4bps | PF@4bps |
|---------|-----------------|-------------------|----------|--------------|---------|
| 1h | 2.51 | 4.11 | -1.49 | 50.0% | 0.91 |
| 4h | 2.71 | 5.52 | -1.29 | 50.7% | 0.96 |
| 8h | 4.25 | -0.07 | 0.25 | 46.0% | 1.01 |
| 24h | 13.14 | 11.54 | 9.14 | 51.6% | 1.11 |
| 48h | 7.53 | 7.29 | 3.53 | 50.2% | 1.03 |

- Mean MFE: 234.88 bps
- Mean MAE: -223.09 bps
- MFE/MAE: 1.05
- Mean funding rate: 0.0023%
- Mean z-score: -1.25

**Quarterly stability (24h horizon):**

- Q1: -1.29 bps (N=79)
- Q2: 8.23 bps (N=79)
- Q3: 50.92 bps (N=79)
- Q4: -15.99 bps (N=79)

### Continuation (H2) — All Events (N=319)

| Horizon | Gross Mean(bps) | Gross Median(bps) | Net@4bps | Winrate@4bps | PF@4bps |
|---------|-----------------|-------------------|----------|--------------|---------|
| 1h | -2.51 | -4.11 | -6.51 | 41.4% | 0.67 |
| 4h | -2.71 | -5.52 | -6.71 | 45.2% | 0.80 |
| 8h | -4.25 | 0.07 | -8.25 | 46.7% | 0.84 |
| 24h | -13.14 | -11.54 | -17.14 | 47.0% | 0.82 |
| 48h | -7.53 | -7.29 | -11.53 | 48.8% | 0.91 |

- Mean MFE: 234.88 bps
- Mean MAE: -223.09 bps
- MFE/MAE: 1.05
- Mean funding rate: 0.0023%
- Mean z-score: -1.25

**Quarterly stability (24h horizon):**

- Q1: 1.29 bps (N=79)
- Q2: -8.23 bps (N=79)
- Q3: -50.92 bps (N=79)
- Q4: 15.99 bps (N=79)

### Long Crowded

**Reversion** (N=151):
- Gross 24h: 35.38 bps
- Net 24h @4bps: 31.38 bps
- PF 24h @4bps: 1.41

**Continuation** (N=151):
- Gross 24h: -35.38 bps
- Net 24h @4bps: -39.38 bps
- PF 24h @4bps: 0.65

### Short Crowded

**Reversion** (N=168):
- Gross 24h: -6.89 bps
- Net 24h @4bps: -10.89 bps
- PF 24h @4bps: 0.88

**Continuation** (N=168):
- Gross 24h: 6.89 bps
- Net 24h @4bps: 2.89 bps
- PF 24h @4bps: 1.04

## 4. Baseline Comparison

| Baseline | 4h mean(bps) | 24h mean(bps) | 48h mean(bps) | Count |
|----------|-------------|---------------|---------------|-------|
| random | 0.36 | -1.22 | -1.16 | 3190 |
| same_vol | 0.22 | -0.10 | -0.47 | 3190 |
| opposite | -2.73 | -13.53 | -8.52 | 319 |

## 5. Cost Analysis

**Mean Reversion:**

| Horizon | Gross | Net@2bps | Net@4bps | Net@6bps |
|---------|-------|----------|----------|----------|
| 1h | 2.51 | 0.51 | -1.49 | -3.49 |
| 4h | 2.71 | 0.71 | -1.29 | -3.29 |
| 8h | 4.25 | 2.25 | 0.25 | -1.75 |
| 24h | 13.14 | 11.14 | 9.14 | 7.14 |
| 48h | 7.53 | 5.53 | 3.53 | 1.53 |

## 6. Stability

- **4h (reversion):** 1st half=1.28 bps, 2nd half=4.45 bps ✅
- **24h (reversion):** 1st half=2.51 bps, 2nd half=26.34 bps ✅

## 7. Failure Classification

- Continuation exists but costs dominate
- Reversion only works for long-crowded (shorts have edge)

## 8. Final Verdict

**Best hypothesis: reversion** (PF=1.11)

| Criterion | Status | Value |
|-----------|--------|-------|
| Occurrences ≥ 100 | ✅ | 319 |
| Mean net @4bps ≥ 0 | ✅ | 9.14 bps |
| PF > 1.1 | ✅ | 1.11 |
| MFE >> MAE | ✅ | 1.05 |
| Outlier dep < 30% | ❌ | 253.3% |
| Same sign halves | ✅ | 1st=2.51, 2nd=26.34 |
| Beats random baseline | ✅ | setup=13.14, rand=-1.22 |

### ❌ EDGE NOT VALIDATED
Failed: Outlier dep < 30%

### Outlier Deep-Dive

The 24h reversion "edge" is **entirely driven by outliers**:

- **Top 5% (15 events) contribute +9,948 bps** while total PnL is only +4,315 bps
- **Without top 5%: mean = -18.53 bps per event** (deeply negative)
- **Median return = 0.00 bps** — coin flip at median
- **Top event:** 2026-02-05 long_crowded → +1,383 bps (single outlier)
- **Top 10 events cluster** in Nov 2025 – Mar 2026 (specific market regime)

The "edge" is a few extreme market events (likely liquidation cascades), not a systematic signal.

**Long crowded (N=151):** Mean=+31.51 bps, Median=0.00 bps, 119% outlier dependent
**Short crowded (N=168):** Mean=-2.64 bps, Median=0.00 bps, no signal at all

## 9. Next Action

**ONE:** This path is closed. The funding reversion "edge" is entirely outlier-dependent. Without the top 5% of events (15 trades), mean return is -18.53 bps. Median return is 0.00 bps. The signal comes from a handful of extreme market events (likely liquidation cascades in Nov 2025 – Mar 2026), not from a systematic funding pressure mechanism. Funding rate extremes do not create exploitable price behavior.

---
*No parameters were tuned after seeing results.*
*Analysis completed 2026-04-28 10:47:32.*