# MANTIS Event Engine — Diagnostic & Improvement Report

**Date:** 2026-04-27
**Data:** 169 live events from Hyperliquid BTC (~2 hours collection)
**Status:** Collection ongoing, validation pending 1000+ events

---

## 1. CRITICAL BUG: Regime Detection is Dead

### Finding
**100% of events classified as `low_volatility`.** Regime_score is a constant `0.4` for every single event.

### Root Cause
`EngineContext.classify_regime()` in `context.py` uses:
```python
prices = list(self.buffer._prices)[-60:]  # 60 ticks
price_range = max(prices) - min(prices)
volatility_pct = (price_range / avg_price) * 100
# Thresholds: >1.0% = high, >0.3% = normal, else low
```

With BTC at $78,500:
- 0.3% threshold = $235.5
- The entire price span over 2 hours of collection is $232
- So the 60-tick window NEVER exceeds 0.3%

### Impact
The `confidence_components.regime` contributes 30% of the confidence score but is always `0.4`:
- All noise penalties for `low_volatility` are active (0.2-0.5 penalty)
- No regime differentiation between events
- The entire regime-dependent scoring pathway is non-functional

### Fix
Replaced with multi-signal `RegimeClassifier` (`regime.py`):
- **Volatility signal**: rv ratio between 30s and 300s windows (percentile-ranked)
- **Directional signal**: CVD slope + price slope at two timeframes
- **Range signal**: position within session range

Result: 62% mild_up, 28% mild_down, 7% compression, 2% unknown (vs 100% low_volatility before)

---

## 2. SHORT SELECTION: 42% of Sell-Side Events Are Noise

### Finding
Directional filter suppressed **23 out of 55 sell-side events (42%)**:
- `sell_imbalance`: 12/16 suppressed (75%) — noise-prone, no structural justification
- `sell_cluster`: 6/10 suppressed (60%) — large sells in uptrend = absorption, not signal
- `down_break`: 3/4 suppressed (75%) — breakout against trend = likely failed break
- `above_vwap` (sell-side): 2/2 suppressed — selling above VWAP in uptrend

### Preserved (structural) sell-side events:
- `sell_exhaustion`: 0/14 suppressed — structural, works in any regime
- `bearish_divergence`: 0/4 suppressed — price vs CVD disagreement is structural
- `sell_absorption`: 0/3 suppressed — aggressive buying absorbed = structural

### Logic
Shorts are allowed if ANY of:
1. Regime is bearish (downtrend or mild_down)
2. Event is structural (exhaustion, absorption, sweep, divergence)
3. Price is extended >15 bps above VWAP AND near session high

Shorts are suppressed when:
- Regime is bullish + event is noise-prone (imbalance, cluster, range_break)

---

## 3. SCORING: Multiplicative Formula Compresses to Noise Floor

### Finding
Original formula: `strength × confidence × (1 - noise × 0.5)`

Typical values: `0.55 × 0.51 × 0.92 = 0.258`

This multiplicative compression means:
- Median composite score = 0.25
- 75th percentile = 0.42
- Score differences are tiny and hard to act on

### Fix
New additive formula: `strength × 0.40 + confidence × 0.40 + (1-noise) × 0.20`

Result:
- Median = 0.60, p25 = 0.54, p75 = 0.76
- Clear separation between high and low quality events
- Directional multiplier applied on top (0.5x to 1.5x)

---

## 4. CONFIDENCE ENGINE: Replaced Dead Components

### Original
- `regime`: always 0.4 (dead)
- `liquidity`: book depth based, reasonable
- `spread`: always 0.7 or 1.0 (nearly constant)
- `sample_size`: volume-based proxy, reasonable

### New Components
- `regime_alignment`: does regime support this direction? (0.30-0.80)
- `structural_proximity`: distance to VWAP/session H/L (0.97-1.00)
- `flow_consistency`: CVD slope vs event direction (0.50 constant — need raw CVD data)
- `event_reliability`: base rate by event type (0.45-0.75)

### Issue
`flow_consistency` is stuck at 0.50 because the re-scoring script doesn't have access to raw CVD time series. In live integration, this will use `buffer.get_cvd_window()`.

---

## 5. EVENT TYPE RELIABILITY RANKING

Based on structural analysis (not performance — we don't have outcomes yet):

| Event Type | Structural Basis | Reliability |
|---|---|---|
| absorption | Direct observation: aggression absorbed | High |
| exhaustion | Direct observation: impact declining | High |
| liquidity_sweep | Observable: liquidity grab + reclaim | High |
| range_break | Observable: price breaks range | Medium |
| vwap_reaction | Observable: behavior at VWAP | Medium |
| delta_divergence | Observable: price vs CVD disagreement | Medium |
| large_trade_cluster | Observable: large trades cluster | Low-Medium |
| imbalance | Volume ratio only, no structural check | Low |

---

## 6. IMPLEMENTATION FILES

Created in `backend/event_engine/`:
- `regime.py` — Multi-signal RegimeClassifier
- `confidence.py` — Regime-aware ConfidenceEngine
- `directional_bias.py` — Post-detection filter + score modifier

Created in `scripts/`:
- `rescore_events.py` — Re-scores existing events with new engines

### Integration Path (when ready)
To integrate into live `EventManager`, modify `manager.py`:

```python
# In EventManager.__init__:
from .regime import RegimeClassifier
from .confidence import ConfidenceEngine
from .directional_bias import DirectionalBias

self.regime_clf = RegimeClassifier()
self.conf_eng = ConfidenceEngine()
self.bias = DirectionalBias(self.config)

# In EventManager.on_trade, after detection:
regime, regime_details = self.regime_clf.classify(
    self.ctx.buffer, self.ctx.session, timestamp
)

# Before scoring: apply directional filter
allowed, reason = self.bias.should_allow_event(
    event.event_type, event.side, regime, regime_details, self.ctx
)
if not allowed:
    continue  # suppress event

# Replace scoring:
conf_result = self.conf_eng.score(
    event.event_type, event.side, regime,
    event.price, self.ctx.buffer, self.ctx.session
)
# Use conf_result["confidence_score"] instead of original confidence
```

---

## 7. NEXT STEPS

1. **Continue collecting to 1000+ events** (current: 169, rate ~80/hour)
2. **Run validation** with original scores to establish baseline
3. **Integrate new modules** into live EventManager
4. **Collect second batch** with improved scoring
5. **Compare**: original vs improved — which events have edge?

**DO NOT integrate until we have baseline validation results.**
We need to measure the original system first, then measure the improvement.
