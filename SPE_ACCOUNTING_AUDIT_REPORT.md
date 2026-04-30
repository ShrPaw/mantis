# MANTIS SPE — Accounting Consistency Audit Report

**Date:** 2026-05-01  
**Scope:** SPE layer accounting/reporting only  
**Constraints enforced:** No threshold changes, no detector logic changes, no execution

---

## 1. Root Cause Analysis

### Was L6-L8 = 26 real or a reporting typo?

**It was a reporting typo.** The previous smoke test output showed ALL layers at 266 consistently:

```
L1_context_gate: fail=266, not_evaluated=0
L2_pressure through confidence_gate: fail=0, not_evaluated=266
```

The "26" figure for L6-L8 in the task description does not appear in any recorded API output, `/spe/metrics` response, or `spe_metrics.json` snapshot. The code path (`_mark_not_evaluated(from_index)`) iterates from `from_index` through the end of `_layer_order`, which includes L6, L7, L8, and confidence_gate. There was never a code-level bug that excluded L6-L8 from the `not_evaluated` marking.

### Additional real bug found and fixed

While the "26" was a typo, a **real single-source-of-truth bug** existed:

- `flush_spe_metrics()` used `self._spe_evaluations` (manager counter) for `raw_evaluations`
- `get_layer_metrics()` used `self._signals_evaluated` (orchestrator counter) for layer counts
- These are separate counters that increment once per `on_trade` call, but using two different sources of truth for the same metric is fragile and could drift under edge conditions (e.g., exception paths)

**Fix:** `flush_spe_metrics()` and `get_spe_layer_stats()` now both use `orchestrator.get_layer_metrics()["raw_evaluations"]` as the single source of truth.

---

## 2. Code Paths Inspected

| File | What was inspected | Finding |
|---|---|---|
| `backend/event_engine/spe/orchestrator.py` | `_mark_not_evaluated()`, all gate calls, `get_layer_metrics()`, `get_stats()` | Correct cascading. All 9 layers in `_layer_order`. `_mark_not_evaluated(from_index)` iterates `from_index:` through end. |
| `backend/event_engine/manager.py` | `_spe_evaluations` vs orchestrator `_signals_evaluated`, `flush_spe_metrics()`, `get_spe_layer_stats()` | Fixed: now uses orchestrator as single source of truth for `raw_evaluations`. |
| `backend/main.py` | `/spe/metrics`, `/spe/layers`, `/spe/events`, broadcast | All endpoints consistent. `/spe/metrics` now includes `accounting_valid` and `accounting_errors`. |
| `frontend/src/types.ts` | `SPELayerStat`, `SPELayerStats`, `SPEStats` | Updated: three-state `pass/fail/not_evaluated`. |
| `frontend/src/components/SPEPanel.tsx` | Layer stats rendering | Updated: shows ✓/✗/⊘ per layer. |
| `frontend/src/store.ts` | Default SPE stats | Updated: matches new types. |

---

## 3. The Invariant

```
For each layer in [L1_context_gate, L2_pressure, L3_displacement, L4_sweep,
                    L5_trap, L6_execution_filter, L7_entry_zone, L8_exit_model,
                    confidence_gate]:

    pass + fail + not_evaluated == raw_evaluations
```

This invariant is now enforced by `SPEOrchestrator.validate_layer_accounting()` and checked on every `/spe/metrics` response and every periodic flush.

---

## 4. Fresh Smoke Test Output (5-minute run)

### /health
```json
{
  "status": "ok",
  "source": "hyperliquid",
  "clients": 0,
  "trade_count": 796,
  "candles_loaded": 101,
  "uptime": 311.69,
  "event_engine": "active",
  "events_total": 36,
  "events_fired": 36,
  "events_deduped": 997,
  "pending_outcomes": 36,
  "spe": "active",
  "spe_observation_only": true,
  "spe_evaluations": 796,
  "spe_events": 0
}
```

### /spe/metrics
```json
{
  "timestamp": 1777583989.0486379,
  "spe_enabled": true,
  "observation_only": true,
  "current_state": "IDLE",
  "raw_evaluations": 796,
  "layer_counts": {
    "L1_context_gate":     { "pass": 0, "fail": 796, "not_evaluated": 0 },
    "L2_pressure":         { "pass": 0, "fail": 0,   "not_evaluated": 796 },
    "L3_displacement":     { "pass": 0, "fail": 0,   "not_evaluated": 796 },
    "L4_sweep":            { "pass": 0, "fail": 0,   "not_evaluated": 796 },
    "L5_trap":             { "pass": 0, "fail": 0,   "not_evaluated": 796 },
    "L6_execution_filter": { "pass": 0, "fail": 0,   "not_evaluated": 796 },
    "L7_entry_zone":       { "pass": 0, "fail": 0,   "not_evaluated": 796 },
    "L8_exit_model":       { "pass": 0, "fail": 0,   "not_evaluated": 796 },
    "confidence_gate":     { "pass": 0, "fail": 0,   "not_evaluated": 796 }
  },
  "full_8_layer_passes": 0,
  "emitted_events": 0,
  "suppressed_duplicates": 0,
  "cooldown_hits": 0,
  "accounting_valid": true,
  "accounting_errors": []
}
```

### /spe/layers
```json
{
  "layer_stats": {
    "layer_pass_fail": { /* same as layer_counts above */ },
    "raw_evaluations": 796,
    "full_8_layer_passes": 0,
    "emitted_events": 0,
    "suppressed_duplicates": 0,
    "cooldown_hits": 0,
    "current_state": "IDLE",
    "observation_only": true,
    "accounting_valid": true,
    "accounting_errors": []
  }
}
```

### /spe/events?limit=5
```json
{
  "spe_events": [],
  "spe_stats": { /* consistent with above */ }
}
```

### Disk verification
- `data/metrics/spe_metrics.json` — EXISTS (1131 bytes)
- `data/events/spe_events.jsonl` — ABSENT (acceptable: zero SPE events fired)

---

## 5. Final Accounting Status

| Check | Result |
|---|---|
| `accounting_valid` | **true** |
| `accounting_errors` | **[]** (empty) |
| Invariant per layer | **ALL PASS** — every layer sums to 796 |
| Cascading correctness | **PASS** — L1 fail=796, all downstream fail=0 |
| Cross-endpoint consistency | **PASS** — `/health`, `/spe/metrics`, `/spe/layers`, `/spe/events` all agree |
| Disk persistence | **PASS** — `spe_metrics.json` updated during idle runtime |

---

## 6. Safety Status

| Check | Status |
|---|---|
| `observation_only` | **true** |
| Execution attempted | **No** — zero trading endpoint calls |
| Thresholds changed | **No** |
| Detector logic changed | **No** |
| SPE events emitted | **0** (correct for observation-only with L1 blocking) |

---

## 7. Final Verdict

### **A — Accounting correct, ready for 30-min SPE smoke test**

All layers obey the invariant `pass + fail + not_evaluated == raw_evaluations`.  
Cascading semantics are correct: when layer N fails, layers N+1..end are `not_evaluated`.  
The invariant check is now built into the runtime and will ERROR-log any future drift.  
No thresholds, detector logic, or execution behavior was changed.
