# FAILED_AGGRESSION_SELL_V0_REPORT

**Generated:** 2026-04-27 10:15 CST
**Source events:** 0 (no events_with_outcomes.jsonl found)
**Shadow detections:** 0
**Mode:** Shadow only (no production impact)

---

## 1. Detector Definition

Three conditions, no more:

```
AGGRESSION:
  delta_ratio <= -0.40
  abs_delta_percentile >= 0.85

NO PRICE RESPONSE:
  downside_move_bps <= 2.0
  OR (failed_to_break_prior_low
      AND distance_to_prior_low <= 5.0 bps)

DETECTION WINDOW: 15 seconds
MIN SAMPLES: 8 events in window
MIN VOLUME: 0.5 BTC in window
```

**Corrections applied:**
- Proximity condition: distance_to_prior_low ≤ 5 bps (prevents mid-range noise)
- Promotion criteria: minimum ≥100, preferred ≥300
- Chronological enforcement: strict timestamp ordering, past-only buffer
- time_to_positive metric: reported in validation

Forward return is measured AFTER detection by OutcomeTracker.
It is never used to trigger detection.

---

## 2. Why This Is Different from sell_exhaustion

| Aspect | sell_exhaustion (rejected) | failed_aggression_sell_v0 |
|--------|---------------------------|--------------------------|
| Observes | Impact decline over time | Aggression vs price response NOW |
| Fires when | Selling happened and slowed | Selling IS happening but price won't follow |
| Confirmation | None | Price not moving lower (present observation) |
| Proximity | Any price near low | Within 5 bps of prior low (actual support test) |
| Causal link | Indirect (decline → maybe exhaustion) | Direct (aggression high + price flat = absorption) |

---

## 3. Shadow Detection Results

**No events detected.** Source data file `backend/data/events/events_with_outcomes.jsonl` does not exist.

---

## 4–7. Validation Sections

Cannot validate — no source data.

---

## 8. Promotion Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1a | Sample ≥100 (minimum) | ❌ (0 events) |
| 1b | Sample ≥300 (preferred) | ❌ (0 events) |
| 2 | Gross positive at 10s | ❌ (no data) |
| 3 | Net ≥0 at 4bps | ❌ (no data) |
| 4 | Time-stable | ❌ (no data) |
| 5 | Controlled adverse | ❌ (no data) |

### VERDICT: **Insufficient data** — Cannot evaluate.

---

## Corrections Log

| # | Correction | File | Status |
|---|-----------|------|--------|
| 1 | Promotion criteria: min ≥100, pref ≥300 | validate script | ✅ Applied |
| 2 | Chronological enforcement: sort + past-only buffer | validate script | ✅ Applied |
| 3 | Proximity condition: distance ≤ 5bps | detector + validate | ✅ Applied |
| 4 | time_to_positive metric | validate script + CSV | ✅ Applied |
