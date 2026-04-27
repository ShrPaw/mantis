# BLACKLIST_WATCHLIST_PATCH.md

**Date:** 2026-04-27
**Status:** SHADOW ONLY — no production enforcement
**Mode:** Diagnostic metadata + parallel logging

---

## 1. Summary

Based on forensic audit findings, three event types are blacklisted (structurally unsound) and three are watchlisted (candidates requiring further observation).

| Layer | Event Types | Action |
|-------|------------|--------|
| **Blacklist** | sell_exhaustion, sell_imbalance, sell_cluster | Shadow metadata tag only. NO score capping. NO filtering. |
| **Watchlist** | sell_absorption, down_break, up_break | Full snapshot capture. Candidate tracking. Parallel logging. |

**CRITICAL: All events flow through the original live pipeline unchanged.**

---

## 2. Shadow Mode Constraint

Blacklist/watchlist is implemented as **diagnostic shadow metadata only**:

- `event_type_blacklisted: true/false` — on every event
- `event_type_watchlisted: true/false` — on every event
- `blacklist_reason` — why it was flagged
- `watchlist_reason` — why it was flagged
- `shadow_tradeable_allowed: true/false` — shadow judgment

**No enforcement in production.** Events are NOT blocked, NOT score-capped, NOT filtered.

---

## 3. Blacklist Rationale

### sell_exhaustion
- **Forensic finding:** Detector fires on selling climax, not exhaustion
- **Evidence:** Gross negative at ALL horizons in 2/3 regimes. 0% WR in mild_up. 16.7% WR in mild_down.
- **Verdict:** Logic is inverted. Cannot be salvaged without rebuilding.

### sell_imbalance
- **Forensic finding:** Volume ratio without structural context = noise
- **Evidence:** Gross negative at 10s/30s/60s/120s. Classified as `detector_bad`.
- **Verdict:** No mechanical basis for edge.

### sell_cluster
- **Forensic finding:** Large sells in uptrend = absorption, not signal
- **Evidence:** Gross negative at 30s/60s/120s/300s. Classified as `detector_bad`.
- **Verdict:** No mechanical basis for edge.

---

## 4. Watchlist Rationale

### sell_absorption
- **Forensic finding:** Direct observation of passive absorption (not inference)
- **Evidence:** Net +0.12 bps at 60s with N=3. Structurally sound but insufficient sample.
- **Status:** Hypothesis, NOT signal. Requires 100+ occurrences.

### down_break
- **Forensic finding:** Range breaks have mechanical basis (stop cascade, liquidity vacuum)
- **Evidence:** Net +1.48 bps at 60s with N=4. Positive gross at ALL horizons.
- **Status:** Hypothesis, NOT signal. Requires larger sample for confirmation.

### up_break
- **Forensic finding:** Same mechanical basis as down_break
- **Evidence:** Net -0.85 bps at 60s with N=15. Positive gross at ALL horizons.
- **Status:** Candidate, but cost-sensitive. Requires 100+ events.

---

## 5. Files Modified (Shadow-Only Patch)

| File | Change |
|------|--------|
| `models.py` | Added shadow metadata fields to `MicrostructureEvent` |
| `manager.py` | Events flow through unchanged; shadow metadata tagging only |
| `directional_bias.py` | Removed blacklist blocking and score capping |
| `confidence.py` | Removed blacklist reliability cap |
| `blacklist_watchlist.py` | Replaced `log_blacklisted()` with `log_shadow_blacklisted()` (no enforcement) |
| `candidate_watchlist.py` | Standalone snapshot module (unchanged) |
| `config.py` | `BlacklistConfig`/`WatchlistConfig` kept for reference (not enforced) |

## 6. Files NOT Modified

| File | Reason |
|------|--------|
| All detectors | Detector logic unchanged. |
| Scoring engine | No threshold changes. Blacklist is metadata only. |
| Validation scripts | Existing scripts work with the new structure. |

---

## 7. Shadow Flow

```
Event detected by any detector
  │
  ├─ Is it blacklisted?
  │   YES → Tag: event_type_blacklisted=True
  │         Tag: blacklist_reason="blacklisted:type:side"
  │         Tag: shadow_tradeable_allowed=False
  │         Tag: validation_tags.append("SHADOW_BLACKLISTED")
  │         Log to shadow diagnostics
  │         DO NOT cap score
  │         DO NOT block from pipeline
  │         CONTINUE to normal processing
  │
  ├─ Is it watchlisted?
  │   YES → Tag: event_type_watchlisted=True
  │         Tag: watchlist_reason="watchlisted:type:side"
  │         Capture snapshot (parallel CSV)
  │         CONTINUE to normal processing
  │
  └─ Normal processing → dedup, score, log, track (UNCHANGED)
```

---

## 8. Parallel Logging

Two CSV files are exported periodically:

- `candidate_watchlist.csv` — full microstructure snapshots for watchlist events
- `blacklist_watchlist_report.csv` — blacklisted event diagnostics

These are **parallel diagnostic logs**. They do NOT affect the live pipeline.

---

## 9. Promotion Criteria Gate

**Final rule:**

No blacklist enforcement in production until validated with:

- ≥100 events per type
- Positive net expectancy at 4bps
- Stable across chronological splits
- No threshold tuning

Run `scripts/shadow_comparison.py` to check promotion criteria.

---

## 10. Verification

```bash
# Verify shadow metadata is present (no enforcement)
python3 -c "
import sys; sys.path.insert(0, 'backend')
from event_engine.blacklist_watchlist import is_blacklisted, is_watchlisted
assert is_blacklisted('exhaustion', 'sell_exhaustion') == True
assert is_blacklisted('exhaustion', 'buy_exhaustion') == False
assert is_watchlisted('absorption', 'sell_absorption') == True
assert is_watchlisted('range_break', 'down_break') == True
assert is_watchlisted('range_break', 'up_break') == True
assert is_watchlisted('exhaustion', 'buy_exhaustion') == False
print('ALL VERIFIED — shadow metadata only, no enforcement')
"

# Run shadow comparison
python3 scripts/shadow_comparison.py --input backend/data/events/events_with_outcomes.jsonl
```
