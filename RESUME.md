# MANTIS BTC Microstructure — Research Resume

**Project:** MANTIS — Real-time BTC microstructure dashboard + auction failure edge validation
**Platform:** Hyperliquid DEX (BTC/USD perpetuals)
**Status:** Data collection complete, analysis pending
**Last Updated:** 2026-04-28

---

## Executive Summary

MANTIS started as a real-time BTC microstructure dashboard. An 8-detector event engine was built to find tradeable patterns. A forensic audit proved the engine had **no statistically valid edge** — 3 of 8 detectors were actively harmful, the scoring system was non-monotonic, and sell-side capability was entirely absent.

A complete rewrite was undertaken: `research/auction_failure/` — four primitive detectors based on auction failure mechanics. One hour of BTC trade data was collected from Hyperliquid. **Analysis is pending.**

---

## Session 1 — Forensic Audit + Module Build

### Old System Analysis (8-detector engine)
- **277 events audited** across 8 detector types
- **3 detectors REJECTED** (sell_exhaustion, sell_imbalance, sell_cluster) — gross negative at all horizons
- **Scoring system: NON-FUNCTIONAL** — neither original nor shadow scores predict outcomes
- **Regime detection: DEAD** — 100% low_volatility classification
- **Directional filter: HARMFUL** — suppressed events outperformed preserved ones
- **Conclusion: No edge detectable with old system**

### New Module Built: `research/auction_failure/`
- **13 files, ~2,650 lines** of code
- Four primitive event classes based on auction mechanics:
  1. `failed_aggressive_sell` — strong selling fails → expect UP
  2. `failed_aggressive_buy` — strong buying fails → expect DOWN
  3. `breakout_acceptance` — price breaks range, holds, flow confirms → continuation
  4. `breakout_rejection` — price breaks range, returns, flow fails → reversal
- All thresholds are **relative** (bps, percentile, ratio) — no fixed USD amounts
- All thresholds are **structural starting assumptions**, NOT tuned constants
- Shadow mode only — no production integration
- Collector connects **directly to Hyperliquid WS**, independent of MANTIS backend

---

## Session 2 — Data Collection + Bug Fix

### Data Collection
- **1 hour of live BTC trades** from Hyperliquid WebSocket
- **~7,000+ trades** at ~2.4 trades/second
- **~25-30 events detected** across all four classes
- Event rate: ~1 event per 2 minutes (strict detection conditions)
- Files: `data/research/trades.jsonl` (raw), `data/research/auction_events.csv` (events)

### Bug Fixed
- **replay.py** had a critical bug: expected `data.get("type") == "large_trade"` but collector saves trades without a `type` field
- Every trade from collector output was silently skipped during replay
- **Fixed:** Added fallback detection by checking for `price`+`qty`+`delta` keys
- **Pushed to GitHub:** commit `8bbbd5f`

### Current Status
- Collector completed (or nearly completed) the 1-hour run
- Analysis NOT yet run — needs: `python3 -m research.auction_failure.replay --input data/research/trades.jsonl --format trades`
- Report NOT yet reviewed

---

## Honest Assessment

### What We Know
1. The old 8-detector system had **zero edge** — proven by forensic audit
2. The auction failure module is structurally sound — clean code, correct logic, no lookahead bias
3. Detection conditions are genuinely strict (top 15% delta, 40% directional ratio, top 30% volume)

### What We Don't Know
1. Whether the ~25-30 events produce any directional signal
2. Whether the detection conditions are *too* strict for practical data collection
3. Whether auction failure mechanics have edge in BTC microstructure at all

### Expected Result
With ~25-30 events across 4 classes (5-10 per class), **no class will meet the ≥100 promotion threshold**. The conclusion will almost certainly be:

> **"Insufficient data for validation. No edge detectable at current structural assumptions with 1 hour of collection."**

### If No Edge Is Found
The protocol is clear: **state "no edge" and stop.** Do NOT tune thresholds. Do NOT add features. Do NOT optimize. The falsification exercise is complete.

---

## Architecture

```
Hyperliquid DEX (wss://api.hyperliquid.xyz/ws)
        │
        ▼
┌─────────────────────────────┐
│  collector.py                │ ← Direct WS, no MANTIS backend
│  (1 hour raw trades)         │
│  → data/research/trades.jsonl│
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  replay.py                   │ ← FIXED: handles collector format
│  → runner.on_trade()         │
│  → detectors.detect_all()    │
│  → outcomes.update()         │
│  → report.generate()         │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  Output                      │
│  → auction_events.csv        │
│  → AUCTION_FAILURE_RESEARCH  │
│    _REPORT.md                │
└─────────────────────────────┘
```

---

## Key Files

| File | Lines | Purpose |
|------|-------|---------|
| `research/auction_failure/detectors.py` | 617 | Four primitive detectors |
| `research/auction_failure/config.py` | 124 | All relative thresholds |
| `research/auction_failure/models.py` | 186 | AuctionEvent data model |
| `research/auction_failure/runner.py` | 203 | Pipeline orchestrator |
| `research/auction_failure/report.py` | 640 | Report generator + promotion gate |
| `research/auction_failure/analytics.py` | 207 | Statistics engine |
| `research/auction_failure/outcomes.py` | 128 | Outcome tracker (no lookahead) |
| `research/auction_failure/collector.py` | 153 | Hyperliquid WS collector |
| `research/auction_failure/replay.py` | 130 | **FIXED** offline replay tool |
| `research/auction_failure/data_adapter.py` | 129 | Rolling window + data feed |
| `FORENSIC_AUDIT_REPORT.md` | ~500 | Old system audit (no edge) |
| `SESSION_CONTEXT.md` | — | Next session instructions |

---

## Promotion Criteria (All Must Pass)

| Criterion | Threshold |
|-----------|-----------|
| Event count | ≥ 100 per class |
| Gross return | > 0 at intended horizon |
| Net return | ≥ 0 at 4bps |
| Time stability | Consistent sign across chronological halves |
| MAE | Controlled (< 5bps adverse) |
| Time to positive | < 30 seconds average |
| Decay | No severe performance decay in 10-min blocks |

**If ANY criterion fails → class does NOT promote. No exceptions.**

---

## Next Steps (Priority Order)

1. **Check if collection completed:** `wc -l data/research/trades.jsonl`
2. **Run analysis:** `python3 -m research.auction_failure.replay --input data/research/trades.jsonl --format trades`
3. **Review report:** Check `AUCTION_FAILURE_RESEARCH_REPORT.md`
4. **Apply promotion criteria** — almost certainly no class will pass
5. **State conclusion:** "No edge at current assumptions" or "Insufficient data"
6. **STOP.** Do not tune. Do not optimize. Falsification exercise is over.
