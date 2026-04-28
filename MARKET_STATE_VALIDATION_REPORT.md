# MARKET STATE VALIDATION REPORT

**Date:** 2026-04-28
**Dataset:** BTCUSDT 1-minute bars
**Period:** 2025-06-01 to 2026-04-12
**Total bars:** 454,879
**Columns:** timestamp, price, volume, delta, trade_count
**Delta available:** YES
**Volume available:** YES
**Trade count available:** YES

## 1. Executive Verdict

### **No useful market-state edge detected**

**Level:** 0/4

- Total bars: 454,879
- DEAD bars: 76,228
- CHOP bars: 2,958
- EXPANSION bars: 78,070
- NEUTRAL bars: 297,623
- Expansion setups (confirmed): 78066
- Long setups: 37474
- Short setups: 40592

## 2. Data Used

- File: btcusdt_1m.csv (from btc-intraday-system)
- Rows: 454,879
- Date range: 2025-06-01 to 2026-04-12
- Granularity: 1-minute bars
- Columns: timestamp, price, volume, delta, trade_count
- Delta: YES (signed volume)
- Volume: YES
- Trade count: YES

## 3. State Definitions (Fixed Before Data Inspection)

### EXPANSION
- Price move thresholds: [10, 15, 20, 30] bps
- Reference windows: [1, 3, 5] bars (1m, 3m, 5m)
- Confirmation windows: [1, 2, 3] bars (1m, 2m, 3m)
- Confirmation: price holds above/below expansion midpoint
- Flow confirmation: delta not strongly against direction during confirmation

### CHOP
- 3m range ≥ 10 bps
- |3m net return| ≤ 5 bps
- Directional efficiency (5m) < 0.25

### DEAD
- 5m range < 5 bps
- Volume below 30th percentile

## 4. State Counts

| State | Count | % of total |
|-------|-------|------------|
| DEAD | 76,228 | 16.8% |
| CHOP | 2,958 | 0.7% |
| EXPANSION | 78,070 | 17.2% |
| NEUTRAL | 297,623 | 65.4% |

**Expansion setups (after confirmation, deduplicated):** 78066
- Long: 37474
- Short: 40592

## 5. Expansion vs Random Baseline

| Horizon | Expansion Gross | Expansion Net@4bps | Random Gross | Diff |
|---------|----------------|-------------------|--------------|------|
| 1m | -0.02 | -4.02 | 0.03 | -0.05 |
| 2m | -0.10 | -4.10 | 0.01 | -0.11 |
| 3m | -0.15 | -4.15 | -0.05 | -0.10 |
| 5m | -0.19 | -4.19 | 0.40 | -0.58 |
| 10m | -0.23 | -4.23 | 0.40 | -0.62 |

## 6. Expansion vs Same-Volatility Random

| Horizon | Expansion Gross | Same-Vol Gross | Diff |
|---------|----------------|----------------|------|
| 1m | -0.02 | 0.01 | -0.03 |
| 2m | -0.10 | 0.01 | -0.10 |
| 3m | -0.15 | 0.03 | -0.18 |
| 5m | -0.19 | 0.02 | -0.21 |
| 10m | -0.23 | 0.05 | -0.27 |

## 7. Expansion vs Opposite Direction

| Horizon | Expansion Gross | Opposite Gross | Diff |
|---------|----------------|----------------|------|
| 1m | -0.02 | 0.02 | -0.05 |
| 2m | -0.10 | 0.10 | -0.19 |
| 3m | -0.15 | 0.15 | -0.30 |
| 5m | -0.19 | 0.19 | -0.38 |
| 10m | -0.23 | 0.23 | -0.45 |

## 8. Chop vs Expansion

CHOP forward absolute movement (opportunity cost of being in chop):

| Horizon | CHOP mean |abs| | EXPANSION mean | EXP > CHOP? |
|---------|------------------|----------------|-------------|
| 1m | 6.27 | -0.02 | ❌ |
| 2m | 8.87 | -0.10 | ❌ |
| 3m | 10.78 | -0.15 | ❌ |
| 5m | 13.97 | -0.19 | ❌ |
| 10m | 19.11 | -0.23 | ❌ |

## 9. Long vs Short Asymmetry

| Metric | Long | Short |
|--------|------|-------|
| Gross mean 2m | -0.14 | -0.06 |
| Gross mean 5m | -0.28 | -0.11 |
| Gross mean 10m | -0.23 | -0.23 |
| Net mean 5m @4bps | -4.28 | -4.11 |
| PF 5m @4bps | 0.51 | 0.54 |

## 10. Cost Stress Test

| Horizon | Gross | Net@2bps | Net@4bps | Net@6bps | Winrate@4bps | PF@4bps |
|---------|-------|----------|----------|----------|--------------|---------|
| 1m | -0.02 | -2.02 | -4.02 | -6.02 | 23.5% | 0.27 |
| 2m | -0.10 | -2.10 | -4.10 | -6.10 | 29.3% | 0.38 |
| 3m | -0.15 | -2.15 | -4.15 | -6.15 | 32.0% | 0.45 |
| 5m | -0.19 | -2.19 | -4.19 | -6.19 | 35.2% | 0.53 |
| 10m | -0.23 | -2.23 | -4.23 | -6.23 | 39.0% | 0.63 |

## 11. Stability Analysis

- 2m: First half=-0.11 bps, Second half=-0.08 bps ✅
- 5m: First half=-0.26 bps, Second half=-0.12 bps ✅
- 10m: First half=-0.30 bps, Second half=-0.16 bps ✅

- 5m thirds: -0.06 / -0.35 / -0.16

## 12. Outlier Dependence

- 2m: Top 5% drive 0.0% of total P&L ✅ OK
- 5m: Top 5% drive 0.0% of total P&L ✅ OK
- 10m: Top 5% drive 0.0% of total P&L ✅ OK

## 13. Practical Interpretation

MANTIS market-state classification does not provide useful distinction between EXPANSION and other states.
No practical value as a decision filter.

## 14. Final Verdict

**No useful market-state edge detected.**

## 15. Next Action

Stop. Market-state classification does not provide actionable edge.

---
*No parameters were tuned after seeing results. All definitions were fixed before data inspection.*
*Analysis completed 2026-04-28 09:37:49.*