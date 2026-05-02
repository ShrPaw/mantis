# MANTIS L3 1M Displacement Diagnostic Report

## Problem Statement

During live BTC perp trading on Hyperliquid, visually obvious 1m candle displacement moves are **not triggering production L3 Displacement**. The chart shows clear directional movement with momentum, but the SPE pipeline stalls at L3.

## Current L3 Production Logic

**File:** `backend/event_engine/spe/displacement.py`

### How it works:
1. Receives **raw trade ticks** (not candles) via `update(price, qty, delta, timestamp)`
2. Pulls all ticks within a **180-second sliding window** from the RollingBuffer
3. Computes `body_bps = (window_high - window_low) / avg_price * 10000`
4. Stores `body_bps` in a rolling history (deque, maxlen=200)
5. Requires `body_bps >= p85(history) AND body_bps >= 15 bps`
6. Continuation check: divides window into 3 segments, needs ≥1 segment moving ≥5 bps in same direction
7. Continuation is **not gating** — only used in strength score

### Key thresholds:
| Parameter | Value | Nature |
|---|---|---|
| `body_percentile_threshold` | 0.85 (p85) | Rolling percentile |
| `min_move_bps` | 15.0 | **Hard floor** |
| `move_window_seconds` | 180 | Fixed window |
| `continuation_candles` | 3 | Segments in window |
| `continuation_min_bps` | 5.0 | Min segment move |

---

## Root Cause Analysis

### Issue 1: Measurement Mismatch (Primary)

Production L3 measures **tick range over a fixed 180s window**, not candle structure.

A visually obvious 1m displacement candle (e.g., a single 30 bps body candle) may not trigger L3 because:
- The 180s window spans ~3 candles, diluting the single-candle move
- Ticks within the window may be spread unevenly (high-frequency chop within the range)
- The window may capture both the move AND partial reversal, reducing `body_bps`

**Evidence:** The production detector computes `max(ticks) - min(ticks)` over 180s. A single candle that moves 25 bps in 60s, then retraces 10 bps in the next 120s, shows only 25 bps range in the full window — but the 1m candle body is 25 bps.

### Issue 2: Inflating Percentile Baseline

After volatile periods, the p85 threshold becomes very high. Example:
- 200 ticks of 20-30 bps 180s ranges → p85 ≈ 25 bps
- Subsequent 18 bps move (90th percentile of recent action) fails because 18 < 25

The `_body_history` deque (maxlen=200) contains evaluations from every tick, not every candle. High-frequency evaluation during volatile periods fills the history with large values, inflating the baseline.

### Issue 3: Hard 15 bps Floor

The `min_move_bps = 15` is a fixed constant regardless of regime. In low-volatility conditions:
- A 12 bps move might be a 99th-percentile event
- But it fails the 15 bps hard floor
- The percentile gate (p85) might pass, but the floor blocks it

### Issue 4: Continuation Logic Doesn't Match Visual Intuition

Production L3's continuation check divides the 180s tick window into 3 segments and requires **at least 1** segment to move ≥5 bps in the same direction. This is:
- **Too lenient** structurally (1 of 3 is a weak requirement)
- **Misaligned** with what traders see (candle-to-candle continuation, not tick-segment continuation)
- A move can "pass" continuation even if the last segment reverses

### Issue 5: No Candle Structure Awareness

Production L3 has no concept of:
- Individual candle body (open → close)
- Candle range (high → low)
- Close-to-close between adjacent candles
- Multi-candle legs (3c, 5c directional sequences)
- Directional efficiency (net move vs total path)
- Pullback ratios within a leg

These are the metrics traders visually associate with "displacement."

---

## Shadow Diagnostic System

### Design

Independent shadow calibrator (`l3_live_calibrator.py`) that:
1. Aggregates ticks into 1m candles (aligned to clock minutes)
2. Computes single-candle and multi-candle metrics
3. Maintains rolling percentile stats at 60/240/720 candle windows
4. Evaluates 5 shadow variants independently of production L3
5. Persists results to `data/metrics/l3_live_shadow.json` and `data/events/l3_shadow_events.jsonl`

### Shadow Variants

| Variant | Threshold | Rationale |
|---|---|---|
| **A. Production L3** | Exact replay of production logic from candles | Baseline comparison |
| **B. 3-Candle Displacement** | 3c_leg ≥ p85, efficiency ≥ 0.55, vol_pct ≥ 60 | Standard 1m displacement |
| **C. Stress Displacement** | 3c_leg ≥ p90, efficiency ≥ 0.65, vol_pct ≥ 75 | High-conviction move |
| **D. Single Candle Impulse** | body ≥ p90, range ≥ p85 | Explosive single candle |
| **E. 5-Candle Leg** | 5c_leg ≥ p85, efficiency ≥ 0.60, pullback ≤ 0.40 | Sustained directional move |

### Metrics Computed

**Single candle:**
- `body_bps`: |close - open| / avg * 10000
- `range_bps`: (high - low) / avg * 10000
- `close_to_close_bps`: |curr_close - prev_close| / avg * 10000

**Multi-candle legs (2c/3c/5c):**
- `leg_bps`: |end_close - start_open| / avg * 10000
- `directional_efficiency`: net_move / total_path (1.0 = straight line)
- `pullback_ratio`: max_retracement / leg_range (0.0 = no pullback)
- `max_extension_bps`: max distance from leg open

**Rolling stats (per metric, at 60/240/720 candle windows):**
- p75, p80, p85, p90, p95, p99

---

## Expected Behavior

### When L3 Should Pass But Doesn't

The shadow system will show:
- Production L3: **FAIL** (with specific block reason)
- One or more shadow variants: **PASS**
- Interpretation: "Visible 1m displacement detected but production L3 failed"

### Common Scenarios

1. **Single large candle, quick reversal**
   - Shadow D (single candle) passes
   - Production L3 fails because 180s window includes reversal
   - Interpretation: "Production L3 requires continuation; move reversed too quickly"

2. **Sustained 3-candle move, below 15 bps floor**
   - Shadow B (3c) passes at percentile
   - Production L3 fails on hard 15 bps floor
   - Interpretation: "Production L3 too strict vs 1m percentile displacement"

3. **Choppy move with high range but poor efficiency**
   - All shadows fail (efficiency too low)
   - Production L3 may or may not pass (tick range can be large even in chop)
   - Interpretation: "Move is choppy; efficiency too low"

4. **Low volatility, small but significant move**
   - Shadow B or E passes at percentile
   - Production L3 fails on both p85 and 15 bps floor
   - Interpretation: "Move below 15 bps hard floor but significant relative to recent history"

---

## Recommendation

**Do NOT replace production L3 yet.**

The shadow system needs 24-48 hours of live data to:
1. Calibrate percentile baselines (need ≥240 candles for stable p85)
2. Measure false positive rate of each shadow variant
3. Compare shadow pass/fail against visual chart assessment
4. Identify which variant(s) best correlate with meaningful displacement

After data collection:
- Review `data/events/l3_shadow_events.jsonl` for pass/fail patterns
- Compare shadow variant timing against chart screenshots
- Evaluate whether any variant should replace or supplement production L3
- Consider hybrid approach: production L3 OR shadow variant pass

---

## Files Created

| File | Purpose |
|---|---|
| `L3_CURRENT_LOGIC.md` | Full audit of production L3 logic |
| `backend/event_engine/spe/l3_live_calibrator.py` | Shadow diagnostic system |
| `frontend/src/components/L3DiagnosticPanel.tsx` | UI panel for shadow diagnostics |
| `MANTIS_L3_1M_DIAGNOSTIC_REPORT.md` | This report |

## Files Modified

| File | Change |
|---|---|
| `backend/event_engine/manager.py` | Added L3LiveCalibrator initialization and on_trade hook |
| `backend/main.py` | Added `GET /l3/calibration` endpoint |
| `frontend/src/components/DecisionSidebar.tsx` | Added L3DiagnosticPanel to sidebar |

## Endpoints

- `GET /l3/calibration` — Returns full diagnostic snapshot with production status, shadow variants, metrics, percentile ranks, and interpretation

## Persistence

- `data/metrics/l3_live_shadow.json` — Latest snapshot (overwritten each evaluation)
- `data/events/l3_shadow_events.jsonl` — Append-only log when any shadow variant passes
