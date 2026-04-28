# Audit Methodology — MANTIS 6-Hour Live Run

## Segmentation (in order of evaluation priority)

### Tier 1: Alert-Triggering Events
- Events that actually produced a Tier 1/2/3 alert
- These are the ONLY events the trader would see
- Evaluate: signal quality, noise, actionable value

### Tier 2: High-Severity Events
- imbalance_score >= 75 OR risk_score >= 75
- May or may not have triggered an alert (could be rate-limited)
- Evaluate: did the engine correctly identify these as significant?

### Tier 3: Unique State Transitions
- IDLE → CROWD_BUILDUP, IDLE → CASCADE, etc.
- How often does the engine actually change its mind?
- High transition count = responsive. Too high = jittery.

### Tier 4: Raw Events (INFORMATIONAL ONLY)
- Total event count, IDLE percentage
- NOT a success metric
- Listed only for completeness

## Verdict Criteria

### A — Usable
- Alert-triggering events show meaningful behavioral separation from random
- High-severity events correlate with dangerous/unfavorable execution conditions
- Alert rate is low enough to be useful (not spammy)
- At least 1 example of a genuinely useful alert (caught a dangerous environment)

### B — Too Noisy But Fixable
- Some alerts are useful but too many are noise
- High-severity events are identified but alerts fire too often or at wrong times
- Clear path to improvement (threshold adjustment, better rate limiting)

### C — Not Useful Yet
- Alerts don't correlate with dangerous environments
- High-severity events are random or unhelpful
- No clear value over random sampling
