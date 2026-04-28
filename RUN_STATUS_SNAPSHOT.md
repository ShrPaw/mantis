# MANTIS Run — Partial Status Snapshot
# Captured: 2026-04-29 05:57 CST (30 min into 6h run)

## Event Counts

| Category | Count |
|----------|-------|
| Total raw events | 7,086 |
| Alert-triggering events | 20 |
| High-severity (imbalance≥75 OR risk≥75) | 0 |

## State Distribution

| State | Count | % |
|-------|-------|---|
| IDLE | 7,065 | 99.7% |
| UNWIND | 21 | 0.3% |

## Alert Breakdown

| Tier | Count |
|------|-------|
| Tier 1 (Watch) | 20 |
| Tier 2 (Actionable) | 0 |
| Tier 3 (Danger) | 0 |

## Notes

- 30 minutes elapsed of 6-hour run
- Funding/OI z-scores still building rolling history
- 21 UNWIND detections = engine is detecting something
- No high-severity events yet — market is relatively calm
- Alert rate: 20 alerts in 30 min = 40/hr (above the 20/hr cap — need to check rate limiter)
- All 20 alerts are Tier 1 (Watch) — low severity

## Rate Limiter Check

Alert cap is 20/hour. 20 alerts in 30 min suggests the rate limiter may need investigation.
However, if these are 20 unique state transitions (IDLE→UNWIND), each counts as a separate alert type.
