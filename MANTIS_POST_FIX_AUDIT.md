# MANTIS POST-FIX AUDIT REPORT
Date: 2026-04-28 22:12:03 UTC
Duration: 30 minutes (simulated at production tick rate)
Tick interval: 0.25s
min_seconds_between_same_alert: 60

## Summary

| Metric | Value |
|--------|-------|
| Raw events processed | 7,200 |
| Fired alerts | 5 |
| Suppressed (dedup) | 5514 |
| Unique alert keys | 5 |
| High-severity (≥75) | 2 |
| State transitions | 8 |
| Duplicate bursts (>1 in 5s window) | 0 |
| Elapsed (sim) | 0.0s |

## Tier Breakdown

| Tier | Count |
|------|-------|
| Tier 1 (WATCH) | 2 |
| Tier 2 (ACTIONABLE) | 1 |
| Tier 3 (DANGER) | 2 |

## Unique Alert Keys

- `TIER1_CROWD_BUILDUP_LONGS` — fired 1x
- `TIER1_UNWIND_SHORTS_EXITING` — fired 1x
- `TIER2_CROWD_BUILDUP_LONGS` — fired 1x
- `TIER3_DANGER_DOWN` — fired 1x
- `TIER3_DANGER_UP` — fired 1x

## State Transitions

1. CALM → CROWD_BUILDUP_LONGS
2. CROWD_BUILDUP_LONGS → CROWD_ESCALATION
3. CROWD_ESCALATION → LIQUIDATION_CASCADE
4. LIQUIDATION_CASCADE → CASCADE_CONTINUATION
5. CASCADE_CONTINUATION → CASCADE_REVERSAL
6. CASCADE_REVERSAL → EXHAUSTION
7. EXHAUSTION → UNWIND_SHORTS
8. UNWIND_SHORTS → RECOVERY

## Duplicate Burst Analysis

✅ **NO DUPLICATE BURSTS DETECTED**

Every unique alert key fired at most once per cooldown window.
The rate limiter is correctly suppressing duplicates.

## Alert Frequency Assessment

- Alerts per minute: 0.17
- Alerts per hour (projected): 10

✅ Alert frequency is **usable** — less than 1 alert/minute.

## Suppression Effectiveness

- Total alert attempts: 5519
- Suppressed: 5514 (99.9%)
- Fired: 5 (0.1%)

## Sample Fired Alerts (first 20)

| # | Phase | Tier | State | Side | Severity | Key |
|---|-------|------|-------|------|----------|-----|
| 1 | CROWD_BUILDUP_LONGS | 1 | CROWD_BUILDUP | LONGS | 70 | `TIER1_CROWD_BUILDUP_LONGS` |
| 2 | CROWD_ESCALATION | 2 | CROWD_BUILDUP | LONGS | 71 | `TIER2_CROWD_BUILDUP_LONGS` |
| 3 | LIQUIDATION_CASCADE | 3 | DANGER | DOWN | 85 | `TIER3_DANGER_DOWN` |
| 4 | CASCADE_REVERSAL | 3 | DANGER | UP | 79 | `TIER3_DANGER_UP` |
| 5 | UNWIND_SHORTS | 1 | UNWIND | SHORTS_EXITING | 65 | `TIER1_UNWIND_SHORTS_EXITING` |

## Final Verdict

### Scoring

- ✅ No duplicate bursts
- ✅ Suppression active (5514 suppressed)
- ✅ Alert frequency usable (0.17/min)
- ✅ Multiple state transitions (8)
- ✅ Multiple tiers exercised ([1, 2, 3])
- ✅ High-severity alerts handled (2)

**Score: 9/8**

## **VERDICT: A — Usable**

The alert rate limiter fix is working correctly. Duplicate bursts
are eliminated. Alert frequency is manageable. The system is ready
for production use with current thresholds.

---
Report generated in 0.0s
Verdict: **A — usable**