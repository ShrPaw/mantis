# SHADOW VALIDATION REPORT

**Generated:** 2026-04-27 09:03:27 CST
**Data source:** Hyperliquid BTC live event engine
**Validation type:** Shadow scoring (original vs new modules)

---

## 1. Executive Summary

- **Events analyzed:** 277
- **Completed outcomes:** 237
- **Time range:** 08:19:57 – 08:55:33 (36 min)
- **Sample sufficiency:** WEAK PRELIMINARY — treat with caution
  - 100–300 events. Directional evidence only. Need 1000+ for stronger claims.
- **Live engine modified:** NO (shadow mode only)

## 2. Baseline Problems Identified

### 2.1 Dead Regime Detection

Original regime distribution: {'low_volatility': 277}

All events classified as `low_volatility`. The original `classify_regime()` uses
a 60-tick absolute price range with a 0.3% threshold ($235 at BTC $78,500).
The entire 36-minute price span is ~$232. Threshold never reached.
Result: `regime_score=0.4` and `confidence_regime=0.4` for every event.

### 2.2 Score Compression

Original composite score distribution:
- min=0.0910  p25=0.1701  median=0.2495  p75=0.4440  max=0.7227

Multiplicative formula `strength × confidence × (1 - noise × 0.5)` compresses
most scores into 0.09–0.42 range. Score separation is weak.

### 2.3 Short-Side Noise Hypothesis

Sell-side event type distribution: {'imbalance': 34, 'exhaustion': 24, 'large_trade_cluster': 16, 'delta_divergence': 9, 'vwap_reaction': 4, 'range_break': 4, 'absorption': 3, 'liquidity_sweep': 1}

`sell_imbalance`, `sell_cluster`, and `down_break` may represent
absorption noise, not valid short setups. Structural short candidates:
`sell_exhaustion`, `bearish_divergence`, `sell_absorption`.

## 3. Shadow Scoring Method

Three new modules computed in shadow mode (not integrated into live engine):

1. **RegimeClassifier** (`regime.py`): Multi-signal regime detection
   - Volatility ratio (30s/300s rv, percentile-ranked)
   - CVD slope + price slope at two timeframes
   - Range position within session

2. **ConfidenceEngine** (`confidence.py`): Regime-aware confidence
   - Regime-event alignment (does regime support this direction?)
   - Structural proximity (distance to VWAP/session H-L)
   - Flow consistency (CVD vs event direction)
   - Event type reliability (structural base rate)

3. **DirectionalBias** (`directional_bias.py`): Short filter + score modifier
   - Shorts allowed only in: bearish regime, structural events, or extended above VWAP
   - Score multiplier: 0.5x–1.5x based on regime-direction alignment

Shadow composite formula (additive, replaces multiplicative):
`quality = strength×0.40 + confidence×0.40 + (1-noise)×0.20`
`shadow_score = quality × directional_multiplier`

### 3.1 Shadow Regime Distribution

- `mild_up`: 182 (66%)
- `mild_down`: 77 (28%)
- `compression`: 14 (5%)
- `unknown`: 4 (1%)

### 3.2 Score Distribution Comparison

| Metric | Original | Shadow |
|--------|----------|--------|
| min | 0.0910 | 0.5000 |
| p25 | 0.1701 | 0.5080 |
| median | 0.2495 | 0.5779 |
| p75 | 0.4440 | 0.7190 |
| max | 0.7227 | 1.0000 |

## 4. Score Ranking Validation

Question: Do higher scores predict better directional outcomes?

### 4.1 Original Score Buckets (60s, net @ 4bps)

| Bucket | N | Mean Gross | Mean Net | Winrate | PF |
|--------|---|-----------|---------|---------|-----|
| Q1 | 59 | -0.03 | -4.03 | 17.0% | 0.18 |
| Q2 | 59 | +0.60 | -3.40 | 20.3% | 0.19 |
| Q3 | 59 | +0.39 | -3.61 | 25.4% | 0.25 |
| Q4 | 60 | -0.30 | -4.30 | 16.7% | 0.14 |

### 4.2 Shadow Score Buckets (60s, net @ 4bps)

| Bucket | N | Mean Gross | Mean Net | Winrate | PF |
|--------|---|-----------|---------|---------|-----|
| Q1 | 59 | -0.25 | -4.25 | 17.0% | 0.17 |
| Q2 | 59 | +1.64 | -2.36 | 27.1% | 0.33 |
| Q3 | 59 | -0.91 | -4.91 | 13.6% | 0.10 |
| Q4 | 60 | +0.18 | -3.82 | 21.7% | 0.21 |

### 4.3 Monotonicity Check

Does score increase → outcome improve monotonically?

- **Original**: ❌ NOT monotonic (Q1→Q4: -4.0→-3.4→-3.6→-4.3)
- **Shadow**: ❌ NOT monotonic (Q1→Q4: -4.2→-2.4→-4.9→-3.8)

### 4.4 Top Quartile Performance

- **Original** top 25%: n=59, net=-4.29bps, WR=17.0%
- **Shadow** top 25%: n=59, net=-3.79bps, WR=22.0%

## 5. Short Filter Validation

- Suppressed: 34 events
- Preserved: 48 events

Suppressed types: {'imbalance': 22, 'large_trade_cluster': 7, 'range_break': 3, 'vwap_reaction': 2}
Preserved types: {'exhaustion': 21, 'imbalance': 7, 'delta_divergence': 7, 'large_trade_cluster': 6, 'absorption': 3, 'vwap_reaction': 2, 'range_break': 1, 'liquidity_sweep': 1}

**cost_2bps**:
| Metric | Suppressed | Preserved |
|--------|-----------|-----------|
| N | 34 | 48 |
| Mean net bps | -1.79 | -3.58 |
| Winrate | 0.2647 | 0.1458 |
| PF | 0.438 | 0.136 |
| Worst loss | -6.6 | -9.41 |

**cost_4bps**:
| Metric | Suppressed | Preserved |
|--------|-----------|-----------|
| N | 34 | 48 |
| Mean net bps | -3.79 | -5.58 |
| Winrate | 0.1471 | 0.125 |
| PF | 0.211 | 0.051 |
| Worst loss | -6.6 | -9.41 |

**cost_6bps**:
| Metric | Suppressed | Preserved |
|--------|-----------|-----------|
| N | 34 | 48 |
| Mean net bps | -5.79 | -7.58 |
| Winrate | 0.1471 | 0.0625 |
| PF | 0.11 | 0.009 |
| Worst loss | -6.6 | -9.41 |

**Filter verdict:** ❌ Suppressed events perform BETTER. Filter is harmful.

## 6. Regime Validation

### compression
- Events: 13 (with outcome: 13)
- Types: {'imbalance': 5, 'exhaustion': 4, 'large_trade_cluster': 3, 'delta_divergence': 1}

  - long: n=7, net=-5.42bps, WR=28.6%, PF=0.04
  - short: n=6, net=-5.38bps, WR=0.0%, PF=0.00
  - all: n=13, net=-5.40bps, WR=15.4%, PF=0.02

### unknown
- Events: 4 (with outcome: 4)
- Types: {'vwap_reaction': 2, 'imbalance': 1, 'exhaustion': 1}

  - long: n=2, net=-0.05bps, WR=50.0%, PF=0.95
  - short: n=2, net=-8.20bps, WR=0.0%, PF=0.00
  - all: n=4, net=-4.13bps, WR=25.0%, PF=0.10

### unknown_all
- Events: 4 (with outcome: 0)
- Types: {}


### unknown_long
- Events: 2 (with outcome: 0)
- Types: {}


### unknown_short
- Events: 2 (with outcome: 0)
- Types: {}


## 7. Time Split Validation

| Metric | First Half | Second Half |
|--------|-----------|-------------|
| Events | 118 | 119 |
| With outcome | 118 | 119 |
| Score median | 0.584 | 0.5677 |
| All mean net | -5.11 bps | -2.57 bps |
| All winrate | 0.1525 | 0.2437 |
| All PF | 0.089 | 0.332 |
| Top Q mean net | -6.39 bps | -1.49 bps |
| Top Q winrate | 0.1379 | 0.3103 |

**Stability:** ✅ Directionally consistent across halves.

## 8. Cost Stress Test

| Cost | All N | All Net | All WR | All PF | Top Q Net | Top Q WR | Top Q PF |
|------|-------|---------|--------|--------|-----------|----------|----------|
| cost_2bps | 237 | -1.84 | 29.1% | 0.43 | -1.79 | 28.8% | 0.46 |
| cost_4bps | 237 | -3.84 | 19.8% | 0.19 | -3.79 | 22.0% | 0.21 |
| cost_6bps | 237 | -5.84 | 14.3% | 0.09 | -5.79 | 15.2% | 0.10 |

## 9. Event Type × Side × Regime × Horizon Performance

### Sell-Side Focus Events

| Type | Side | Regime | N | Gross10s | Gross30s | Gross60s | Gross120s | Gross300s | Net4@60s | WR@60s |
|------|------|--------|---|----------|----------|----------|-----------|-----------|----------|--------|
| absorption | sell_absorption | mild_up | 3 | -0.55 | +1.83 | +4.12 | +3.19 | +2.50 | +0.12 | 66.7% |
| delta_divergence | bearish_divergence | mild_down | 6 | -1.12 | -0.64 | +0.04 | +2.88 | +1.66 | -3.96 | 0.0% |
| delta_divergence | bearish_divergence | mild_up | 1 | -0.76 | +2.16 | +1.78 | +2.03 | -2.16 | -2.22 | 0.0% |
| exhaustion | sell_exhaustion | compression | 1 | -1.78 | -1.91 | -2.68 | +4.84 | +2.55 | -6.68 | 0.0% |
| exhaustion | sell_exhaustion | mild_down | 12 | -1.02 | -3.22 | -2.66 | -1.62 | -4.70 | -6.66 | 16.7% |
| exhaustion | sell_exhaustion | mild_up | 8 | -0.03 | -1.47 | -2.69 | -0.27 | -6.52 | -6.69 | 0.0% |
| imbalance | sell_imbalance | compression | 3 | -1.24 | -0.72 | -0.51 | -3.34 | -11.16 | -4.51 | 0.0% |
| imbalance | sell_imbalance | mild_down | 7 | -1.35 | -2.62 | -2.11 | -3.26 | -9.29 | -6.11 | 14.3% |
| imbalance | sell_imbalance | mild_up | 18 | -0.20 | +0.23 | +0.58 | -1.47 | -5.53 | -3.42 | 16.7% |
| imbalance | sell_imbalance | unknown | 1 | -4.33 | -5.86 | -3.18 | -2.29 | +6.49 | -7.18 | 0.0% |
| large_trade_cluster | sell_cluster | compression | 2 | +0.06 | -1.47 | -2.04 | +3.00 | -0.51 | -6.04 | 0.0% |
| large_trade_cluster | sell_cluster | mild_down | 6 | -1.57 | -5.08 | -2.85 | -3.16 | -16.37 | -6.85 | 0.0% |
| large_trade_cluster | sell_cluster | mild_up | 5 | +1.60 | -0.87 | -2.50 | -0.10 | -3.07 | -6.50 | 0.0% |
| liquidity_sweep | high_sweep | mild_up | 1 | +0.38 | -5.85 | -9.41 | -13.09 | -15.25 | -13.41 | 0.0% |

### Buy-Side Focus Events

| Type | Side | Regime | N | Gross10s | Gross30s | Gross60s | Gross120s | Gross300s | Net4@60s | WR@60s |
|------|------|--------|---|----------|----------|----------|-----------|-----------|----------|--------|
| absorption | buy_absorption | mild_down | 1 | +0.64 | -4.45 | -5.60 | -4.45 | -14.00 | -9.60 | 0.0% |
| absorption | buy_absorption | mild_up | 2 | +0.89 | +1.85 | +1.15 | +2.10 | +3.52 | -2.85 | 50.0% |
| delta_divergence | bullish_divergence | compression | 1 | +2.81 | +2.68 | +4.72 | +4.21 | +1.15 | +0.72 | 100.0% |
| delta_divergence | bullish_divergence | mild_down | 3 | -0.26 | +0.21 | +3.95 | +0.00 | -6.75 | -0.05 | 33.3% |
| delta_divergence | bullish_divergence | mild_up | 9 | -2.02 | -1.32 | -1.31 | -0.89 | +2.45 | -5.31 | 11.1% |
| exhaustion | buy_exhaustion | compression | 3 | -0.13 | -1.91 | -5.30 | -5.43 | -3.06 | -9.30 | 0.0% |
| exhaustion | buy_exhaustion | mild_down | 5 | -0.81 | +0.23 | +0.61 | +0.14 | +5.82 | -3.39 | 0.0% |
| exhaustion | buy_exhaustion | mild_up | 33 | +0.24 | +0.82 | +1.81 | +3.34 | +8.95 | -2.19 | 27.3% |
| exhaustion | buy_exhaustion | unknown | 1 | +3.18 | +4.33 | +2.04 | +1.02 | -7.76 | -1.96 | 0.0% |
| imbalance | buy_imbalance | compression | 2 | +0.77 | +0.57 | +1.47 | +1.66 | +6.57 | -2.53 | 50.0% |
| imbalance | buy_imbalance | mild_down | 16 | +0.37 | +1.67 | -0.27 | -0.65 | +3.68 | -4.27 | 18.8% |
| imbalance | buy_imbalance | mild_up | 41 | -0.49 | -0.31 | -0.19 | -0.12 | +5.71 | -4.19 | 21.9% |
| large_trade_cluster | buy_cluster | compression | 1 | +0.51 | -1.40 | -1.66 | +2.68 | +12.88 | -5.66 | 0.0% |
| large_trade_cluster | buy_cluster | mild_down | 2 | -1.91 | -1.28 | +1.98 | +0.89 | +4.72 | -2.02 | 50.0% |
| large_trade_cluster | buy_cluster | mild_up | 14 | +0.45 | +1.43 | +1.53 | +2.51 | +8.74 | -2.47 | 21.4% |
| range_break | up_break | mild_down | 1 | -0.63 | -0.63 | +0.25 | -6.59 | -1.52 | -3.75 | 0.0% |
| range_break | up_break | mild_up | 14 | +1.66 | +2.58 | +3.36 | +6.27 | +12.30 | -0.64 | 35.7% |
| vwap_reaction | below_vwap | mild_down | 2 | -2.17 | -3.37 | -3.56 | -1.21 | +4.47 | -7.56 | 0.0% |
| vwap_reaction | below_vwap | mild_up | 3 | +0.04 | -1.27 | -1.19 | -2.71 | -3.25 | -5.19 | 0.0% |
| vwap_reaction | below_vwap | unknown | 1 | +6.75 | +8.40 | +5.86 | +3.44 | -3.95 | +1.86 | 100.0% |

## 10. Gross Edge Before Costs

Question: Is the detector itself wrong (gross negative), or is the issue cost/horizon?

| Type | Side | N | Gross10s | Gross30s | Gross60s | Gross120s | Gross300s | Net4@60s | Verdict |
|------|------|---|----------|----------|----------|-----------|-----------|----------|---------|
| absorption | buy_absorption | 3 | +0.81 | -0.25 | -1.10 | -0.08 | -2.32 | -5.10 | cost_sensitive |
| absorption | sell_absorption | 3 | -0.55 | +1.83 | +4.12 | +3.19 | +2.50 | +0.12 | edge_at_horizon |
| delta_divergence | bearish_divergence | 7 | -1.07 | -0.24 | +0.29 | +2.76 | +1.11 | -3.71 | edge_at_horizon |
| delta_divergence | bullish_divergence | 13 | -1.24 | -0.66 | +0.37 | -0.29 | +0.22 | -3.63 | cost_sensitive |
| exhaustion | buy_exhaustion | 42 | +0.16 | +0.63 | +1.17 | +2.28 | +7.32 | -2.83 | edge_at_horizon |
| exhaustion | sell_exhaustion | 21 | -0.68 | -2.49 | -2.67 | -0.80 | -5.05 | -6.67 | detector_bad |
| imbalance | buy_imbalance | 59 | -0.21 | +0.26 | -0.16 | -0.20 | +5.19 | -4.16 | edge_at_horizon |
| imbalance | sell_imbalance | 29 | -0.73 | -0.76 | -0.31 | -2.12 | -6.61 | -4.31 | detector_bad |
| large_trade_cluster | buy_cluster | 17 | +0.18 | +0.94 | +1.40 | +2.33 | +8.51 | -2.60 | edge_at_horizon |
| large_trade_cluster | sell_cluster | 13 | -0.10 | -2.90 | -2.59 | -1.04 | -8.81 | -6.59 | detector_bad |
| liquidity_sweep | high_sweep | 1 | +0.38 | -5.85 | -9.41 | -13.09 | -15.25 | -13.41 | cost_sensitive |
| range_break | down_break | 4 | +4.68 | +6.37 | +5.48 | +6.69 | +10.35 | +1.48 | edge_at_horizon |
| range_break | up_break | 15 | +1.51 | +2.37 | +3.15 | +5.41 | +11.37 | -0.85 | edge_at_horizon |
| vwap_reaction | above_vwap | 4 | -0.16 | +0.41 | +0.83 | -2.07 | -9.31 | -3.17 | cost_sensitive |
| vwap_reaction | below_vwap | 6 | +0.42 | -0.36 | -0.81 | -1.18 | -0.79 | -4.81 | cost_sensitive |

**Detector bad (gross negative everywhere):** 3 types
  - exhaustion|sell_exhaustion, imbalance|sell_imbalance, large_trade_cluster|sell_cluster
**Cost-sensitive (gross positive, net negative):** 5 types
  - absorption|buy_absorption, delta_divergence|bullish_divergence, liquidity_sweep|high_sweep, vwap_reaction|above_vwap, vwap_reaction|below_vwap
**Edge at some horizon (net positive):** 7 types
  - absorption|sell_absorption, delta_divergence|bearish_divergence, exhaustion|buy_exhaustion, imbalance|buy_imbalance, large_trade_cluster|buy_cluster, range_break|down_break, range_break|up_break

## 11. Final Recommendation

**RECOMMENDATION: KEEP SHADOW MODE** — Evidence insufficient or negative.

## 12. Next Actions

1. Keep collecting events to 1000+
2. Investigate why specific criteria failed
3. Do NOT integrate until criteria pass
4. Consider whether modules need structural changes
