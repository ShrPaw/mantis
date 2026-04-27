# AUCTION FAILURE RESEARCH REPORT

**Generated:** 2026-04-28 05:30:08 CST
**Module:** `research/auction_failure/`
**Mode:** Shadow only — no production integration
**Objective:** Do failed auctions or accepted breakouts produce repeatable net-positive behavior after costs?

---

## 1. Data Integrity

| Metric | Value |
|--------|-------|
| Total events | 0 |
| Complete outcomes | 0 |
| Time span | 0.0 minutes |
| Time range | 05:30:08 – 05:30:08 |

### Event Class Distribution

| Event Class | Count | % |
|-------------|-------|---|

**⚠️ NO EVENTS DETECTED.** Awaiting data collection.

### Next Steps

1. **Start MANTIS backend:** `cd backend && python3 main.py`
2. **Run the collector:** `python3 research/auction_failure/collector.py --duration 3600`
3. **Or replay existing data:** `python3 research/auction_failure/replay.py --input <path> --format trades`

### Module Status

- ✅ Module architecture: complete
- ✅ Four detectors: implemented
- ✅ Outcome tracker: implemented (no lookahead bias)
- ✅ Analytics engine: implemented
- ✅ Report generator: implemented
- ✅ CSV export: implemented
- ✅ Collector (WebSocket): implemented
- ✅ Offline replay: implemented
- ⏳ Data collection: awaiting MANTIS backend connection
- ⏳ Analysis: awaiting collected data

### Detection Design Summary

| Class | Aggression Condition | Failure Condition | Favorable |
|-------|---------------------|-------------------|-----------|
| failed_aggressive_sell | delta_ratio ≤ -0.40, percentile ≥ 0.85 | Price move < 3bps OR broke low and reclaimed | Price RISES |
| failed_aggressive_buy | delta_ratio ≥ +0.40, percentile ≥ 0.85 | Price move < 3bps OR broke high and rejected | Price FALLS |
| breakout_acceptance | Price outside range by 10% of range height | Holds outside for 15s, flow confirms (ratio ≥ 0.25) | Continuation |
| breakout_rejection | Price WAS outside range | Returned inside within 30s, flow does NOT confirm | Reversal |

All thresholds are **structural starting assumptions** (bps, percentile, ratio, fraction of range).
They are NOT proven constants. They will NOT be tuned after results are observed.
If no edge is found at these thresholds, the conclusion is "no edge" — not "try different thresholds."
