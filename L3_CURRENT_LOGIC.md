# L3 Displacement — Current Production Logic Audit

## File: `backend/event_engine/spe/displacement.py`

### Overview

Production L3 detects "forced move" displacement from **raw tick data** aggregated over a sliding time window. It does NOT use candle OHLCV structure. The detector receives individual trade ticks via `update(price, qty, delta, timestamp)` and computes displacement from the RollingBuffer's time-windowed price data.

---

## Core Computation

### Body Size (bps)
```python
prices, volumes, deltas, timestamps = buffer.get_window(180s, timestamp)
window_high = max(prices)
window_low = min(prices)
avg_price = mean(prices)
body_bps = ((window_high - window_low) / avg_price) * 10000
```
- Uses the **full price range** within the 180s window
- NOT candle body (open-to-close)
- NOT close-to-close between candles
- This is effectively a **high-low range of all ticks in 3 minutes**

### Percentile Threshold
```python
body_percentile_threshold = 0.85  # p85
body_lookback_count = 60          # but uses deque maxlen=200
```
- Stores `body_bps` from each tick evaluation into `_body_history` (deque, maxlen=200)
- Sorts history, takes index `int(len * 0.85)` as the p85 value
- Requires at least 10 samples before evaluating
- **Inflating baseline**: after a volatile period, p85 is high, making it harder to trigger

### Move Magnitude
```python
min_move_bps = 15.0  # hard floor
```
- `body_bps >= 15` is a **hard gate** — regardless of percentile
- If the recent 180s range is < 15 bps, L3 always fails

### Direction
```python
direction = "UP" if prices[-1] > prices[0] else "DOWN"
```
- Simple: last price vs first price in window

### Continuation Check
```python
continuation_candles = 3
continuation_min_bps = 5.0
```
- Divides the price window into N segments (window_size / 3)
- Checks if at least **1 segment** has avg price moving ≥ 5 bps in same direction
- This is very lenient — only needs 1 of 3 segments to continue
- But also fragile: a quick reversal after displacement can still pass if any segment moved

### Volume Spike (optional, not gating)
```python
liquidation_spike_mult = 3.0
volume_spike_percentile = 0.95
```
- Checks if current trade qty > 3x average volume
- Or if last 5 trades avg > 2x overall average
- **Not used as a gate** — only contributes to strength score

### Confirmation Gate
```python
displacement_confirmed = body_ok AND move_bps >= min_move_bps
```
- `body_ok = body_bps >= p85`
- Continuation is NOT required for confirmation — only used in strength scoring
- Volume spike is NOT required — only bonus in strength

### Strength Calculation (0-100)
```
body_score:    min(body_bps / (p85 * 2), 1.0) * 40   # 40%
move_score:    min(move_bps / (15 * 3), 1.0) * 30     # 30%
cont_score:    20 if continuation_ok else 0             # 20%
vol_score:     10 if volume_spike else 0                # 10%
```

---

## Configuration Summary (`config.py` → `DisplacementConfig`)

| Parameter | Value | Type | Notes |
|---|---|---|---|
| `body_percentile_threshold` | 0.85 | Fixed | p85 of rolling body distribution |
| `body_lookback_count` | 60 | Fixed | But deque maxlen=200 |
| `min_move_bps` | 15.0 | Fixed | Hard floor, not percentile-based |
| `move_window_seconds` | 180.0 | Fixed | 3-minute tick window |
| `continuation_candles` | 3 | Fixed | Segments within window |
| `continuation_min_bps` | 5.0 | Fixed | Min continuation per segment |
| `liquidation_spike_mult` | 3.0 | Fixed | Optional volume confirmation |
| `volume_spike_percentile` | 0.95 | Fixed | Optional |

---

## Orchestrator Integration (`orchestrator.py`)

L3 is the **third gate** in the 8-layer pipeline:
1. L1 Context Gate (CASCADE/UNWIND or composite score) → must pass
2. L2 Pressure (crowd_direction != NONE) → must pass
3. **L3 Displacement (displacement_detected == True) → must pass**
4. L4–L8 downstream

If L3 fails, L4–L8 are marked `not_evaluated`.

---

## Key Issues Identified

### 1. Measurement Mismatch
Production L3 uses **raw ticks over 180s window**, not 1m candle structure. A visually obvious 1m displacement (e.g., a single large candle with 30 bps body) may not trigger L3 if:
- The ticks are spread unevenly within the window
- The window straddles two candles, diluting the range
- The 180s window captures both the move AND partial reversal

### 2. Inflating Percentile Baseline
After a volatile period (e.g., 200 ticks of 20+ bps windows), p85 becomes very high. A subsequent 15 bps move that looks significant on the chart won't clear p85.

### 3. Hard 15 bps Floor
The `min_move_bps = 15` is a fixed constant. In low-volatility regimes, a 12 bps move might be a 99th-percentile event but still fail L3.

### 4. Continuation Logic is Weak
- Only needs 1 of 3 segments to continue — too lenient for "forced move" detection
- But also fragile: a quick reversal can still pass if the first segment moved
- Not measuring actual candle-to-candle continuation

### 5. No Candle Structure Awareness
Production L3 has no concept of:
- Candle body (open → close)
- Candle range (high → low)
- Close-to-close between adjacent candles
- Multi-candle legs (3-candle, 5-candle directional moves)
- Pullback ratios within a leg
- Directional efficiency (net move / total path)

---

## Summary

Production L3 is a **tick-range detector over a fixed 180s window** with a **p85 percentile gate** and a **15 bps hard floor**. It does not analyze candle structure, multi-candle legs, or directional efficiency. The continuation check is segment-based and only requires 1 of 3 segments to confirm.

The primary failure mode for live 1m displacement: **the 180s tick window doesn't align with candle boundaries**, and the **percentile baseline inflates after volatile periods**, causing visually clear 1m moves to fail the p85 gate.
