# BLACKLIST VALIDATION REPORT

**Generated:** 2026-04-27 10:45:54 CST
**Total events:** 199
**Blacklisted:** 11
**Non-blacklisted:** 188
**Watchlisted:** 50

## 1. Blacklist Event Breakdown

| Type | Count |
|------|-------|
| sell_exhaustion | 4 |
| sell_imbalance | 7 |
| **TOTAL** | **11** |

## 2. Before vs After Blacklist

| Horizon | Metric | ALL (before) | Non-BL (after) | Delta |
|---------|--------|-------------|----------------|-------|
| 10s | Avg | -0.34bps | -0.20bps | +0.14 |
| 10s | WR | 48.7% | 50.0% | +1.3% |
| 30s | Avg | +0.34bps | +0.59bps | +0.25 |
| 30s | WR | 48.2% | 49.5% | +1.2% |
| 60s | Avg | +1.24bps | +1.07bps | -0.17 |
| 60s | WR | 51.8% | 51.1% | -0.7% |
| 120s | Avg | +2.44bps | +2.51bps | +0.07 |
| 120s | WR | 57.3% | 56.9% | -0.4% |
| 300s | Avg | +3.54bps | +3.47bps | -0.07 |
| 300s | WR | 59.3% | 59.0% | -0.3% |

## 3. Cost Stress: Before vs After

| Cost | Horizon | ALL Net | Non-BL Net | Delta |
|------|---------|---------|------------|-------|
| 2bps | 10s | -2.34 | -2.20 | +0.14 |
| 2bps | 30s | -1.66 | -1.41 | +0.25 |
| 2bps | 60s | -0.76 | -0.93 | -0.17 |
| 4bps | 10s | -4.34 | -4.20 | +0.14 |
| 4bps | 30s | -3.66 | -3.41 | +0.25 |
| 4bps | 60s | -2.76 | -2.93 | -0.17 |
| 6bps | 10s | -6.34 | -6.20 | +0.14 |
| 6bps | 30s | -5.66 | -5.41 | +0.25 |
| 6bps | 60s | -4.76 | -4.93 | -0.17 |

## 4. Blacklisted Events: Individual Performance

These events are excluded from tradeable set.

| Side | N | Gross Avg (60s) | Winrate | PF |
|------|---|-----------------|---------|-----|
| sell_exhaustion | 4 | +3.89 | 50.0% | 1.67 |
| sell_imbalance | 7 | +4.26 | 71.4% | 3.14 |

## 5. Watchlisted Events: Current Performance

These are candidates. NOT tradeable. Diagnostic only.

| Side | N | Gross Avg (60s) | Winrate | PF |
|------|---|-----------------|---------|-----|
| sell_absorption | 10 | -3.16 | 40.0% | 0.41 |
| up_break | 40 | +2.57 | 52.5% | 1.75 |

## 6. Time Stability (Non-Blacklisted Only)

| Metric | First Half | Second Half |
|--------|-----------|-------------|
| N | 94 | 94 |
| Avg (60s) | +0.44bps | +1.69bps |
| Winrate | 47.9% | 54.3% |
| PF | 1.12 | 1.48 |

## 7. Blacklist Impact Summary

- **Events removed:** 11 (5.5%)
- **Gross avg (60s) before:** +1.24bps
- **Gross avg (60s) after:** +1.07bps
- **Gross improvement:** -0.17bps
- **Winrate before:** 51.8%
- **Winrate after:** 51.1%

**Note:** Blacklist is NOT about improving performance.
It is about removing structurally unsound detectors from tradeable logic.
Performance improvement (if any) is a side effect, not the goal.
