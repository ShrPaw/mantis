# Session Context — MANTIS Auction Failure Research

## What Happened This Session

### 1. Deep Analysis of Existing MANTIS Event Engine
- Performed full forensic audit of the 8-detector system (277 events, 237 with outcomes)
- **Conclusion: No statistically valid edge detected.** System is structurally negative at all cost assumptions.
- 3 of 8 detectors are `detector_bad` (gross negative everywhere): sell_exhaustion, sell_imbalance, sell_cluster
- Scoring system is non-monotonic (neither original nor shadow scores predict outcomes)
- Regime detection was dead (100% low_volatility classification)
- Directional filter was harmful (suppressed events outperformed preserved ones)
- Report: `FORENSIC_AUDIT_REPORT.md` and `SHADOW_VALIDATION_REPORT.md` contain full data

### 2. Built New Research Module: `research/auction_failure/`
- Complete rewrite — NOT an improvement of old detectors, entirely new approach
- Based on **auction failure mechanics**, not pattern matching
- Four primitive event classes:
  - `failed_aggressive_sell`: strong selling fails → expect price UP
  - `failed_aggressive_buy`: strong buying fails → expect price DOWN
  - `breakout_acceptance`: price breaks range, holds, flow confirms → continuation
  - `breakout_rejection`: price breaks range, returns, flow fails → reversal
- **All thresholds are structural starting assumptions** (relative: bps, percentile, ratio)
- No scoring engine, no ML, no tuning — falsification tool only
- Shadow mode only, no production integration

### 3. Critical Corrections Applied
- Fixed directional return logic: failed_aggressive_sell = favorable is UP (not DOWN)
- Fixed directional return logic: failed_aggressive_buy = favorable is DOWN (not UP)
- Added honest threshold disclaimers: "structural starting assumptions, NOT proven constants"
- Zero misspellings of aggressive/aggression verified via grep

### 4. Data Collection Started
- Collector connects **directly to Hyperliquid WebSocket** (not through MANTIS backend)
- Raw trade data: individual trades with price, qty, side, delta
- Rate: ~2 trades/second on BTC/USD
- Was collecting 1-hour dataset when session ended
- Output: `data/research/trades.jsonl` (raw trades), `data/research/auction_events.csv` (detected events)

## What Needs To Happen Next

### Immediate
1. **Check if the 1-hour collection completed** — run:
   ```bash
   cd /root/.openclaw/workspace/mantis
   wc -l data/research/trades.jsonl
   ```
2. **If collection completed**, run the analysis:
   ```bash
   python3 -m research.auction_failure.replay --input data/research/trades.jsonl --format trades
   ```
3. **If collection didn't complete**, restart it:
   ```bash
   python3 -u -m research.auction_failure.collector --duration 3600
   ```

### Analysis Phase
4. Review `AUCTION_FAILURE_RESEARCH_REPORT.md` for results
5. Check if ANY event class meets promotion criteria:
   - ≥100 occurrences
   - Positive gross at intended horizon
   - Net ≥ 0 at 4bps
   - Stable across chronological halves
   - Controlled MAE
   - Fast time-to-positive
   - No severe decay

### Decision Point
6. If NO class promotes → "No edge at these assumptions." Done.
7. If a class promotes → it's a **candidate**, not proof. Needs 1000+ events for confirmation.

## Key Files

| File | Purpose |
|------|---------|
| `research/auction_failure/` | Entire research module (13 files, 2657 lines) |
| `research/auction_failure/collector.py` | Direct Hyperliquid WS collector |
| `research/auction_failure/detectors.py` | Four primitive detectors |
| `research/auction_failure/models.py` | AuctionEvent with corrected directional returns |
| `research/auction_failure/config.py` | All relative thresholds (structural assumptions) |
| `research/auction_failure/analytics.py` | Statistics computation |
| `research/auction_failure/report.py` | Report generator with promotion criteria gate |
| `AUCTION_FAILURE_RESEARCH_REPORT.md` | Current report (likely "awaiting data") |
| `FORENSIC_AUDIT_REPORT.md` | Full audit of old detector system |
| `SHADOW_VALIDATION_REPORT.md` | Shadow scoring validation results |

## Architecture Decisions
- Collector uses **direct Hyperliquid WS** (`wss://api.hyperliquid.xyz/ws`) — NOT MANTIS backend
- MANTIS backend may or may not be running; research module is independent
- Trade format from Hyperliquid: `{"channel": "trades", "data": [{"coin": "BTC", "side": "B"/"A", "px": "...", "sz": "...", "time": ...}]}`
- "B" = buyer taker = aggressive buy, "A" = seller taker = aggressive sell
- Incremental delta = qty if buy, -qty if sell

## GitHub
- Repo: https://github.com/ShrPaw/mantis
- Latest push: `b96e3dd` — "feat: auction failure research module"
- Token: (already configured in git remote)
