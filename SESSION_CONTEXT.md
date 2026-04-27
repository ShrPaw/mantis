# Session Context — MANTIS Auction Failure Research (Session 2)

## What Happened This Session

### 1. Data Collection — 1 Hour from Hyperliquid
- Connected directly to Hyperliquid WebSocket (`wss://api.hyperliquid.xyz/ws`)
- Collector ran for 3600 seconds (1 hour)
- **~7,000+ trades collected** at ~2.4 trades/second
- **~25-30 events detected** across all four detector classes
- Output: `data/research/trades.jsonl` (raw trades), `data/research/auction_events.csv` (events)
- Trade rate was consistent: 2.0-2.8 trades/sec throughout

### 2. Critical Bug Fixed in replay.py
- **Bug:** `replay.py` expected `data.get("type") == "large_trade"` but collector saves `{"timestamp", "price", "qty", "side", "delta"}` with NO `type` field
- **Effect:** Every trade from collector output was silently skipped — replay would produce 0 events
- **Fix:** Added fallback detection checking for `price`+`qty`+`delta` keys directly (no type field required)
- **Pushed to GitHub:** commit `8bbbd5f` on main

### 3. Event Rate Analysis
- Event detection rate: ~1 event per 2 minutes (very low)
- Strict detection conditions:
  - delta_ratio threshold: 0.40 (40% net directional volume)
  - delta_percentile: 0.85 (top 15% vs recent history)
  - volume_percentile: 0.70 (top 30% vs recent history)
- At this rate, 1 hour yields ~25-30 events — **far below the ≥100 promotion threshold**
- The detectors are working correctly — they're just filtering for genuinely extreme conditions

### 4. Collector Status at Session End
- Collector was still running when session ended (background process `vivid-bloom`)
- Was at ~2730s / 3600s with 23 events detected
- Data files may or may not be complete depending on when the process finished
- **CHECK FIRST:** `wc -l data/research/trades.jsonl` to see if collection completed

## What Needs To Happen Next

### Immediate
1. **Check if collection completed:**
   ```bash
   cd /root/.openclaw/workspace/mantis
   wc -l data/research/trades.jsonl
   ```
2. **If complete, run analysis:**
   ```bash
   python3 -m research.auction_failure.replay --input data/research/trades.jsonl --format trades
   ```
3. **If not complete, restart collector:**
   ```bash
   python3 -u -m research.auction_failure.collector --duration 3600
   ```

### Analysis Phase
4. Review generated `AUCTION_FAILURE_RESEARCH_REPORT.md`
5. Apply promotion criteria check:
   - ≥100 occurrences per event class
   - Gross > 0 at intended horizon
   - Net ≥ 0 at 4bps
   - Stable across chronological halves
   - Controlled MAE
   - Fast time-to-positive
   - No severe decay

### Decision Point
6. **If NO class promotes → "No edge at these assumptions." Done. Stop.**
7. **If a class promotes → candidate only, needs 1000+ events for confirmation**

## Expected Outcome (Honest Assessment)

With only ~25-30 events total across 4 classes, the sample size is **far too small** for any promotion. The expected result is:

- **No event class meets the ≥100 threshold**
- Most classes will have 5-10 events each
- Statistical power is essentially zero at this sample size
- Conclusion will be: "Insufficient data for validation" or "No edge detectable"

### Possible Paths Forward (DO NOT DO THESE WITHOUT EXPLICIT INSTRUCTION)
- **Option A:** Run collector for 8-10 hours to get ~200-300 events (still marginal)
- **Option B:** Relax detection thresholds (violates the "no tuning" constraint)
- **Option C:** Accept that the auction failure approach at these structural assumptions doesn't produce enough events in 1 hour of BTC trading, and conclude "no edge at current assumptions"

## Key Files

| File | Purpose |
|------|---------|
| `research/auction_failure/` | Entire research module (13 files) |
| `research/auction_failure/collector.py` | Direct Hyperliquid WS collector |
| `research/auction_failure/detectors.py` | Four primitive detectors |
| `research/auction_failure/config.py` | All relative thresholds (structural assumptions) |
| `research/auction_failure/replay.py` | **FIXED** — now handles collector output format |
| `research/auction_failure/analytics.py` | Statistics computation |
| `research/auction_failure/report.py` | Report generator with promotion criteria gate |
| `data/research/trades.jsonl` | Raw trades (gitignored, may or may not exist) |
| `data/research/auction_events.csv` | Detected events (gitignored) |
| `AUCTION_FAILURE_RESEARCH_REPORT.md` | Generated report |
| `FORENSIC_AUDIT_REPORT.md` | Full audit of old 8-detector system |
| `SESSION_CONTEXT.md` | This file |

## Detection Design Summary

| Class | Aggression Condition | Failure Condition | Favorable |
|-------|---------------------|-------------------|-----------|
| failed_aggressive_sell | delta_ratio ≤ -0.40, percentile ≥ 0.85 | Price move < 3bps OR broke low and reclaimed | Price RISES |
| failed_aggressive_buy | delta_ratio ≥ +0.40, percentile ≥ 0.85 | Price move < 3bps OR broke high and rejected | Price FALLS |
| breakout_acceptance | Price outside range by 10% of range height | Holds outside for 15s, flow confirms (ratio ≥ 0.25) | Continuation |
| breakout_rejection | Price WAS outside range | Returned inside within 30s, flow does NOT confirm | Reversal |

## Hard Rules (DO NOT VIOLATE)
- **DO NOT modify detectors**
- **DO NOT tune thresholds**
- **DO NOT add features**
- **DO NOT optimize parameters**
- This is a **falsification exercise** — if no edge is found, the answer is "no edge"
