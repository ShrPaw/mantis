# SPE_SHORT_STRESS — Unseen-Data / Walk-Forward Validation Plan

**Date:** 2026-05-01  
**Scope:** SPE_SHORT_STRESS only  
**Constraints:** No code modifications. No threshold tuning. No feature additions.  
**Mode:** Observation-only. Maker execution assumptions.  

---

## 1. What Is SPE_SHORT_STRESS

SPE_SHORT_STRESS is a specific activation path through the 8-layer SPE pipeline that fires when:

| Layer | Condition for SHORT_STRESS |
|-------|---------------------------|
| **L1** | Market state = CASCADE or UNWIND (or composite gate: imbalance ≥70, exec quality ≥70, risk ≤60) |
| **L2** | crowd_direction = **LONG_CROWD** (funding z ≥ +1.5, OI proxy rising) — the crowd is net long and building |
| **L3** | displacement_direction = **UP** — a forced up-move is in progress (body ≥ p85, ≥15 bps, continuation) |
| **L4** | sweep_detected = true — a structural sweep / CRT event occurred |
| **L5** | trap_detected = true — the crowd got trapped (liquidity taken, direction failure, or rapid reversal) |
| **L6** | execution_quality ≥ 70 — spread < 3 bps, depth ≥ 2 BTC, no book thinning, no vol spike |
| **L7** | Entry = passive limit at 30–50% retrace of the UP displacement (maker-only) |
| **L8** | TP below entry (nearest liquidity/swing), SL above displacement origin, R:R ≥ 1.5 |

**Direction derivation:** `LONG_CROWD + UP displacement + trap → SHORT` (fade the trapped crowd).

This is the highest-conviction short setup in SPE: the crowd is long, price moved up (displacement), liquidity was swept, the crowd is now trapped, and execution conditions are clean. The model fades the crowd.

---

## 2. Current State

| Metric | Value (as of 2026-05-01) |
|--------|--------------------------|
| Accounting invariant | ✅ VALID |
| L1_context_gate | 100% fail (market has been IDLE — no CASCADE/UNWIND) |
| L2–L8 | 100% not_evaluated (blocked by L1) |
| Full 8-layer passes | **0** |
| Emitted SPE events | **0** |
| Data collected | ~5 minutes of live observation (smoke test) |

**The pipeline has never produced a SHORT_STRESS event.** This is expected — the conditions require extreme market states (CASCADE/UNWIND) that haven't occurred during observation.

---

## 3. Unseen Data Requirements

### 3.1 Time Period

| Requirement | Minimum | Target | Rationale |
|-------------|---------|--------|-----------|
| **Total observation time** | 72 hours | 168 hours (7 days) | SHORT_STRESS requires CASCADE/UNWIND states. These are rare (~0.3% of observed time per RUN_STATUS_SNAPSHOT). Need enough wall-clock time to capture ≥5 state transitions. |
| **Market regime coverage** | 2 regimes | 3+ regimes | Must cover: (1) trending/volatile, (2) ranging/calm, (3) event-driven (CPI, FOMC, NFP). Each regime produces different SHORT_STRESS dynamics. |
| **Session coverage** | All 3 sessions | All 3 × 3 days | Asia (00:00–08:00 UTC), London (08:00–16:00 UTC), NY (13:00–21:00 UTC). SHORT_STRESS may cluster around session transitions. |
| **Calendar events** | 1 HIGH event | 2+ HIGH events | FOMC, CPI, NFP — these are when CASCADE/UNWIND states are most likely. Macro events within 1 hour should trigger HIGH_VOL warnings. |

### 3.2 Data Volume

| Data Type | Minimum | Target | Storage |
|-----------|---------|--------|---------|
| **Trade ticks** | 500,000 | 2,000,000+ | `data/events/spe_events.jsonl` + `spe_events.csv` |
| **Candle history** | 3 days (4,320 × 1m) | 7 days (10,080 × 1m) | `data/candles.jsonl` |
| **Order book snapshots** | Not required (uses ctx.book) | — | Live from Hyperliquid WS |
| **SPE evaluations** | 500,000 | 2,000,000+ | `data/metrics/spe_metrics.json` (periodic flush) |

### 3.3 Specific Unseen Windows

The validation data must be **temporally separated** from any development/tuning data:

| Window | Purpose | Duration |
|--------|---------|----------|
| **Window A: Calm baseline** | Confirm SPE correctly stays silent in IDLE | 24 hours of low-volatility ranging |
| **Window B: Volatile trend** | Test CASCADE detection for SHORT_STRESS | 24 hours of trending market with ≥15 bps moves |
| **Window C: Event-driven** | Test UNWIND detection around macro events | 1 HIGH-impact calendar event (FOMC/CPI) |
| **Window D: Full week** | Walk-forward completeness test | 168 continuous hours, no interruptions |

---

## 4. How Much Data Is Enough

### 4.1 Statistical Power Calculation

SHORT_STRESS is a **rare-event strategy**. The question is not "how many trades" but "how many SHORT_STRESS events."

From prior observations:
- Event rate (all classes): ~0.55 events/minute (auction failure module)
- CASCADE/UNWIND state: ~0.3% of time (RUN_STATUS_SNAPSHOT: 21 UNWIND in 7,086 events)
- SHORT_STRESS requires CASCADE/UNWIND + LONG_CROWD + UP displacement + sweep + trap + clean execution
- Estimated SHORT_STRESS rate: **≤ 0.05 events/hour** (conservative, based on 8-layer funnel)

| Collection Time | Expected SHORT_STRESS Events | Sufficient? |
|-----------------|------------------------------|-------------|
| 24 hours | ~1 | ❌ No |
| 72 hours | ~3–4 | ❌ No |
| 168 hours (7 days) | ~8–10 | ⚠️ Marginal |
| 336 hours (14 days) | ~16–20 | ✅ Minimum for validation |

### 4.2 Minimum Viable Sample

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| **SHORT_STRESS events** | ≥ 10 | Below this, any metric is noise. Per RESUME.md promotion criteria: ≥100 per class is ideal, but for a filtered sub-path (SHORT only, HIGH_VOLUME only, HIGH_VOLATILITY only), 10 is the absolute floor for directional signal detection. |
| **Distinct market days** | ≥ 5 | Events must span different days to avoid day-of-week clustering bias. |
| **Distinct sessions** | ≥ 2 of 3 | Must see SHORT_STRESS fire in at least Asia, London, or NY — not just one session. |
| **CASCADE events observed** | ≥ 5 | L1 must pass enough times for the downstream layers to be meaningfully tested. |

### 4.3 If Events Are Insufficient

If after 168 hours of continuous observation, SHORT_STRESS events < 10:

- **Do NOT tune thresholds.** Per project constraints.
- **Do NOT relax detection conditions.** The funnel is the funnel.
- **Report honestly:** "Insufficient SHORT_STRESS signal density for statistical validation at current structural assumptions."
- This is a valid conclusion (see ANALYSIS_FINAL.md: "We did NOT prove the detectors have no edge. We proved we can't collect enough data to tell.").

---

## 5. Metrics That Must Pass

All metrics are evaluated on SHORT_STRESS events only (direction=SHORT, filtered for HIGH_VOLUME and HIGH_VOLATILITY context).

### 5.1 Gate Metrics (Must Pass — Binary)

| # | Metric | Threshold | Kill if Fail |
|---|--------|-----------|-------------|
| G1 | **Accounting invariant** | `pass + fail + not_evaluated == raw_evaluations` for all 9 layers | ✅ Yes — structural integrity failure |
| G2 | **Observation-only compliance** | Zero execution attempts. Zero trading endpoint calls. All events have `observation_only=True`. | ✅ Yes — safety violation |
| G3 | **No code changes during observation** | Git commit hash unchanged from baseline | ✅ Yes — invalidates results |
| G4 | **Threshold stability** | All config values in `config.py` match baseline snapshot | ✅ Yes — invalidates results |

### 5.2 Detection Quality Metrics (Must Pass)

| # | Metric | Threshold | Calculation |
|---|--------|-----------|-------------|
| D1 | **L1 pass rate during CASCADE/UNWIND** | ≥ 80% | When market_state is CASCADE or UNWIND, L1_context_gate must pass ≥80% of the time. If L1 blocks during its own qualifying states, the gate is broken. |
| D2 | **L2–L5 funnel is non-trivial** | ≥ 1 event passes L5 | At least one event must reach the trap layer. If zero events pass L5 after L1 passes, the funnel is too restrictive or broken. |
| D3 | **SHORT direction dominance** | ≥ 70% of full passes are SHORT | When LONG_CROWD + UP displacement + trap fires, direction must be SHORT (per `_determine_direction` logic). If direction derivation is random, the logic is broken. |
| D4 | **Layer pass rates are monotonically decreasing** | L1 pass% ≥ L2 pass% ≥ ... ≥ L8 pass% | Each layer should reject more than it passes. If a downstream layer passes more than an upstream layer, accounting is wrong. |
| D5 | **Trap type distribution** | At least 2 of 3 trap types observed | LIQUIDITY_TAKEN, DIRECTION_FAIL, RAPID_REVERSAL — if only one type ever fires, the detector may be one-dimensional. |

### 5.3 Execution Quality Metrics (Must Pass)

| # | Metric | Threshold | Calculation |
|---|--------|-----------|-------------|
| E1 | **Entry zone validity** | 100% of entries within 30–50% retrace of displacement | Verify `entry_price` falls within the displacement retrace zone. |
| E2 | **R:R ratio** | ≥ 1.5 for all events | Per ExitConfig.min_rr_ratio. Every emitted event must have valid R:R. |
| E3 | **Spread at entry** | ≤ 3 bps average | Per ExecutionFilterConfig.max_spread_bps. Maker execution requires tight spread. |
| E4 | **Depth at entry** | ≥ 2 BTC in top 5 levels | Per ExecutionFilterConfig.min_depth_btc. |
| E5 | **SL distance** | ≥ 5 bps from entry | Per ExitConfig.sl_buffer_bps. SL must be beyond displacement origin + buffer. |
| E6 | **TP distance** | ≥ 10 bps from entry | Per ExitConfig.tp_min_distance_bps. |

### 5.4 Behavioral Separation Metrics (Must Pass)

| # | Metric | Threshold | Calculation |
|---|--------|-----------|-------------|
| B1 | **Forward return (gross) at 5m** | > 0 bps mean | Mean forward return of SHORT_STRESS events at 5-minute horizon must be positive (price drops after entry). |
| B2 | **Forward return (gross) at 15m** | > 0 bps mean | Same at 15-minute horizon. |
| B3 | **Forward return (gross) at 30m** | > 0 bps mean | Same at 30-minute horizon. |
| B4 | **MFE/MAE ratio** | > 1.0 | Max favorable excursion must exceed max adverse excursion on average. If MFE/MAE ≤ 1.0, the setup has no directional edge. |
| B5 | **Beats random baseline** | SPE net maker > random net maker | SPE SHORT_STRESS forward returns must exceed random-direction entries at the same timestamps. |
| B6 | **Beats opposite baseline** | SPE net maker > opposite net maker | SPE SHORT returns must exceed LONG entries at the same timestamps. If opposite direction performs better, the directional assumption is wrong. |

### 5.5 Robustness Metrics (Should Pass)

| # | Metric | Threshold | Calculation |
|---|--------|-----------|-------------|
| R1 | **Profit factor (maker)** | ≥ 1.1 | Gross wins / gross losses with 0.5 bps maker cost. |
| R2 | **Win rate (maker)** | ≥ 50% | Percentage of events with positive net maker return. |
| R3 | **Outlier dependence** | Top 5% PnL share < 80% | If the top 5% of events contribute >80% of total PnL, the edge is outlier-driven (cf. FUNDING_POSITIONING_REPORT.md failure mode). |
| R4 | **Stability across splits** | All 5 chronological splits have same sign | Divide events into 5 chronological chunks. All must have the same sign of net return. |
| R5 | **Median PnL** | > 0 bps | Median must be positive. If mean > 0 but median ≤ 0, the edge is outlier-driven. |
| R6 | **Adverse selection rate** | < 30% | Percentage of events where MAE > 2 bps (adverse selection cost threshold). |
| R7 | **Missed-fill adjusted return** | > 0 bps | Net maker return × (1 − 15% missed fill probability). Must still be positive. |
| R8 | **Time to TP** | < 300 seconds average | Average time from entry to target hit. If too long, the setup may be too slow for maker fills. |

---

## 6. What Would Kill the Candidate

Any single kill condition terminates the validation and closes the SHORT_STRESS path. **No exceptions. No tuning. No second chances.**

### 6.1 Hard Kills (Immediate Termination)

| # | Condition | Rationale |
|---|-----------|-----------|
| K1 | **G1 fails** — accounting invariant violated | Structural integrity failure. All downstream metrics are unreliable. |
| K2 | **G2 fails** — execution attempt detected | Safety violation. Observation-only was breached. |
| K3 | **B6 fails** — opposite direction beats SPE | If going LONG at the same timestamps produces better returns than going SHORT, the directional assumption is **wrong**. The SHORT signal is anti-predictive. |
| K4 | **MFE/MAE ≤ 0.8** | The setup moves against itself more than it moves in its favor. Net negative expectation even before costs. |
| K5 | **Net maker return < −5 bps mean** | After 0.5 bps maker cost, the average SHORT_STRESS trade loses ≥5 bps. Unrecoverable. |
| K6 | **Zero SHORT_STRESS events after 168 hours** | No signal density = no validation possible. The approach doesn't produce enough qualifying conditions. |
| K7 | **All 5 chronological splits are negative** | The setup consistently loses across time. No regime produces positive returns. |

### 6.2 Soft Kills (Close Path with Report)

| # | Condition | Rationale |
|---|-----------|-----------|
| K8 | **3 of 5 splits negative** | Majority of time periods are negative. Edge is regime-dependent at best. |
| K9 | **Top 5% PnL share > 90%** | Entire edge depends on 1–2 outlier events. Not systematic. |
| K10 | **Median PnL ≤ 0** | The "average" SHORT_STRESS trade loses money. Mean is misleading. |
| K11 | **PF < 1.0** | Gross losses exceed gross wins. Negative expectancy. |
| K12 | **Win rate < 40%** | Less than coin-flip accuracy with no compensation in magnitude. |
| K13 | **Beats random but loses to opposite** | The setup has behavioral separation from random, but the direction is wrong. The structural detection works, but the SHORT assumption is inverted. |

---

## 7. What Would Allow Continued Observation

If none of the kill conditions fire, the following outcomes allow the path to remain open for deeper validation.

### 7.1 Continue Conditions

| # | Condition | Action |
|---|-----------|--------|
| C1 | **10 ≤ SHORT_STRESS events < 30** | Continue observation for another 168 hours. Target: ≥30 events for split stability. |
| C2 | **All gate metrics pass, behavioral metrics marginal** | Continue observation. The setup may need more events to reach statistical significance. |
| C3 | **Gross positive but net marginal (0 to +3 bps)** | Continue observation. The edge exists but is thin. Need more data to confirm it survives costs. |
| C4 | **PF 1.0–1.1** | Continue observation. Barely positive. Need ≥30 events to confirm it's not noise. |
| C5 | **2 of 5 splits positive** | Continue but flag as regime-dependent. Need to identify which regimes produce positive results. |
| C6 | **Beats random AND beats opposite, but low N** | Most promising signal. Continue observation to accumulate ≥30 events for promotion criteria. |

### 7.2 Promotion Criteria (All Must Pass for Upgrade)

If after sufficient data (≥30 SHORT_STRESS events), ALL of the following hold, the candidate may be considered for promotion from observation-only to limited paper trading:

| # | Criterion | Threshold |
|---|-----------|-----------|
| P1 | Event count | ≥ 30 SHORT_STRESS events |
| P2 | Gross return (mean, 30m) | > 0 bps |
| P3 | Net return (maker, mean, 30m) | ≥ 0 bps |
| P4 | Profit factor (maker) | ≥ 1.1 |
| P5 | MFE/MAE ratio | > 1.2 |
| P6 | Beats random | Yes |
| P7 | Beats opposite | Yes |
| P8 | Stability (5 splits) | ≥ 4 of 5 positive |
| P9 | Outlier dependence | Top 5% share < 70% |
| P10 | Median PnL | > 0 bps |

**If ANY promotion criterion fails, the candidate remains in observation-only. No exceptions.**

---

## 8. Validation Procedure

### 8.0 Observation Logger (Primary Data Collection Tool)

The long-run observation logger is the primary tool for data collection:

**Script:** `scripts/run_short_stress_observation.py`

**What it does:**
- Connects to local MANTIS backend at `http://localhost:8000`
- Polls `/health`, `/spe/metrics`, `/spe/events?limit=20` every N seconds
- Saves all snapshots to `data/observation/` as JSONL
- Deduplicates SPE events by timestamp/event_type/direction/confidence
- Generates a session summary on exit (Ctrl+C)
- Windows-safe: UTF-8 encoding, never crashes on error, creates dirs automatically

**What it does NOT do:**
- Does NOT change thresholds
- Does NOT modify SPE logic
- Does NOT enable execution
- Does NOT call trading endpoints
- Does NOT claim edge
- Does NOT produce alerts
- Does NOT require user interaction

#### Run Instructions

```bash
# ── Windows / cross-platform ──

# Terminal 1: Start MANTIS backend
cd backend
python main.py

# Terminal 2: Start observation logger (30s interval)
python scripts/run_short_stress_observation.py --interval 30

# Or with custom API URL:
python scripts/run_short_stress_observation.py --interval 30 --api http://localhost:8000

# Stop cleanly with Ctrl+C — generates session summary automatically
```

#### Output Files

| File | Format | Description |
|------|--------|-------------|
| `data/observation/short_stress_health.jsonl` | JSONL | Raw health poll snapshots (one per poll) |
| `data/observation/short_stress_metrics.jsonl` | JSONL | Raw SPE metrics snapshots (one per poll) |
| `data/observation/short_stress_events.jsonl` | JSONL | Deduplicated SPE events (only new events logged) |
| `data/observation/SHORT_STRESS_OBSERVATION_SESSION_SUMMARY.md` | Markdown | Session summary with all required metrics |

#### Session Summary Contents

The auto-generated summary includes:
- Start time, end time, runtime duration
- Total health samples, metric samples, unique SPE events
- current_state distribution (IDLE/CASCADE/UNWIND percentages)
- Max emitted_events observed
- Accounting valid failures (if any)
- observation_only violations (if any)
- Layer pass/fail/not_evaluated counts (last snapshot)
- All SHORT_STRESS candidates (direction=SHORT, crowd=LONG_CROWD, state=CASCADE/UNWIND)

#### Multi-Day Runs

For extended observation (days/weeks):
- The logger runs indefinitely until Ctrl+C
- All data is append-safe (JSONL — restarts don't corrupt prior data)
- Each run produces its own summary
- Combine multiple runs by concatenating JSONL files for analysis
- The dedup set resets on restart (events may appear in multiple runs — deduplicate in analysis)

### 8.1 Pre-Validation Checklist

- [ ] Baseline config snapshot taken (all thresholds in `config.py` frozen)
- [ ] Git commit hash recorded: `________`
- [ ] `SPE_OBSERVATION_ONLY=true` confirmed in environment
- [ ] `SPE_ENABLED=true` confirmed in environment
- [ ] MANTIS backend healthy: `curl http://localhost:8000/health`
- [ ] SPE active: `curl http://localhost:8000/spe/layers`
- [ ] Accounting invariant: `curl http://localhost:8000/spe/metrics` → `accounting_valid: true`

### 8.2 Data Collection

```bash
# Start MANTIS
cd mantis && bash start.sh

# Verify SPE is running
curl http://localhost:8000/spe/metrics

# Run 7-day continuous observation
python3 scripts/smoke_test_spe.py --duration 604800 --output SPE_SHORT_STRESS_7DAY_OBSERVATION.md

# After observation, collect events
cp backend/data/events/spe_events.jsonl SPE_SHORT_STRESS_EVENTS.jsonl
cp backend/data/metrics/spe_metrics.json SPE_SHORT_STRESS_METRICS.json
```

### 8.3 Validation Analysis

```bash
# Run validation against collected events
python3 scripts/validate_spe.py \
  --events backend/data/events/spe_events.jsonl \
  --candles data/candles.jsonl \
  --output SPE_SHORT_STRESS_VALIDATION_REPORT.md
```

### 8.4 Filtering for SHORT_STRESS

Post-hoc filter on collected events:

```python
# Filter criteria for SHORT_STRESS events:
short_stress_events = [
    e for e in all_spe_events
    if e.get("direction") == "SHORT"
    and e.get("crowd_direction") == "LONG_CROWD"
    and e.get("mantis_state") in ("CASCADE", "UNWIND")
    and e.get("confidence_score", 0) >= 70
]
```

### 8.5 HIGH_VOLUME / HIGH_VOLATILITY Filtering

Since the request specifies HIGH_VOLUME and HIGH_VOLATILITY only:

- **HIGH_VOLUME:** Current volume must exceed 70th percentile of rolling distribution (per `DisplacementConfig.volume_spike_percentile = 0.95`, but displacement itself requires p85 body — volume confirmation is implicit in the cascade detection)
- **HIGH_VOLATILITY:** CASCADE state inherently requires extreme volatility (body ≥ p85, ≥15 bps move). Events in IDLE state are excluded by L1 gate.

Both conditions are structurally embedded in the pipeline — no additional filtering is needed beyond the SHORT + LONG_CROWD + CASCADE/UNWIND filter.

---

## 9. Reporting Requirements

### 9.1 Daily Check (During Observation)

| Check | Source | Frequency |
|-------|--------|-----------|
| Layer accounting | `GET /spe/metrics` | Every 6 hours |
| Event count | `GET /spe/events?limit=10` | Every 6 hours |
| State distribution | `GET /spe/metrics` → `current_state` | Every 6 hours |
| Accounting errors | `GET /spe/metrics` → `accounting_errors` | Every 6 hours |

### 9.2 Final Report Structure

```
SPE_SHORT_STRESS_VALIDATION_REPORT.md
├── 1. Executive Summary (verdict + event count)
├── 2. Gate Metrics (G1–G4 pass/fail)
├── 3. Detection Quality (D1–D5)
├── 4. Execution Quality (E1–E6)
├── 5. Behavioral Separation (B1–B6)
├── 6. Robustness (R1–R8)
├── 7. Baseline Comparison (random, vol-matched, opposite)
├── 8. Outlier Analysis (top 5% share, median vs mean)
├── 9. Chronological Stability (5 splits)
├── 10. Verdict (A/B/C/D + continue/kill recommendation)
└── Appendix: All events with full layer data
```

---

## 10. Absolute Constraints (DO NOT VIOLATE)

- Do NOT enable real trading
- Do NOT change thresholds after seeing results
- Do NOT modify detector logic
- Do NOT add features or layers
- Do NOT remove existing MANTIS functionality
- Do NOT break the dashboard
- Do NOT hide negative findings
- Do NOT claim smart money detection
- Do NOT call SPE a signal before validation
- Do NOT optimize for backtest PnL
- Do NOT use cherry-picked examples
- Do NOT re-run validation on the same data (no p-hacking)
- Do NOT filter out negative events to improve metrics
- Do NOT adjust the 30–50% retrace zone
- Do NOT change the 1.5 R:R minimum
- Do NOT change the 0.5 bps maker cost assumption

---

## 11. Decision Tree

```
START validation
│
├─ G1 (accounting) FAIL? → KILL. Report: "Structural integrity failure."
├─ G2 (observation-only) FAIL? → KILL. Report: "Safety violation."
├─ G3 (no code changes) FAIL? → KILL. Report: "Invalid — code changed during observation."
├─ G4 (threshold stability) FAIL? → KILL. Report: "Invalid — thresholds changed."
│
├─ SHORT_STRESS events < 10 after 168h?
│   └─ YES → KILL. Report: "Insufficient signal density."
│
├─ B6 (beats opposite) FAIL? → KILL. Report: "Direction is anti-predictive."
├─ MFE/MAE ≤ 0.8? → KILL. Report: "Negative directional expectation."
├─ Net maker < -5 bps? → KILL. Report: "Unrecoverable loss after costs."
│
├─ All 5 splits negative? → KILL. Report: "Consistently negative across time."
│
├─ 3+ of 5 splits negative? → SOFT KILL. Report: "Regime-dependent, majority negative."
├─ Top 5% > 90%? → SOFT KILL. Report: "Outlier-dependent."
├─ Median ≤ 0? → SOFT KILL. Report: "Median trade loses."
├─ PF < 1.0? → SOFT KILL. Report: "Negative expectancy."
│
├─ All promotion criteria pass?
│   └─ YES → PROMOTE to limited paper trading
│
└─ OTHERWISE → CONTINUE observation. Report: "Marginal — need more data."
```

---

## 12. Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| **Phase 0: Setup** | Day 0 | Baseline snapshot, config freeze, git hash recorded |
| **Phase 1: Observation** | Days 1–7 | Continuous 168-hour run |
| **Phase 2: Analysis** | Day 8 | Validation report with all metrics |
| **Phase 3: Decision** | Day 8 | Verdict: KILL / CONTINUE / PROMOTE |
| **Phase 4 (if CONTINUE): Extended** | Days 9–21 | Additional 336 hours observation |
| **Phase 5 (if CONTINUE): Final** | Day 22 | Final validation report |

---

*Plan prepared: 2026-05-01*  
*No thresholds modified. No code changed. No features added.*  
*Observation-only. Maker assumptions. Walk-forward validation.*
