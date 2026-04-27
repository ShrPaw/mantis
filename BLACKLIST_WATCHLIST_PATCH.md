# BLACKLIST_WATCHLIST_PATCH.md

**Date:** 2026-04-27
**Status:** Structural patch — no parameter tuning, no detector modification

---

## 1. Summary

Based on forensic audit findings, three event types are blacklisted (structurally unsound) and three are watchlisted (candidates requiring further observation).

| Layer | Event Types | Action |
|-------|------------|--------|
| **Blacklist** | sell_exhaustion, sell_imbalance, sell_cluster | Logged only. Never boost score. Never pass filter. Never tradeable. |
| **Watchlist** | sell_absorption, down_break, up_break | Full snapshot capture. Candidate tracking. Not tradeable yet. |

---

## 2. Blacklist Rationale

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

## 3. Watchlist Rationale

### sell_absorption
- **Forensic finding:** Direct observation of passive absorption (not inference)
- **Evidence:** Net +0.12 bps at 60s with N=3. Structurally sound but insufficient sample.
- **Status:** Hypothesis, NOT signal. Requires 30-50 occurrences (preferably 100+).

### down_break
- **Forensic finding:** Range breaks have mechanical basis (stop cascade, liquidity vacuum)
- **Evidence:** Net +1.48 bps at 60s with N=4. Positive gross at ALL horizons.
- **Status:** Hypothesis, NOT signal. Requires larger sample for confirmation.

### up_break
- **Forensic finding:** Same mechanical basis as down_break
- **Evidence:** Net -0.85 bps at 60s with N=15. Positive gross at ALL horizons.
- **Status:** Candidate, but cost-sensitive. Requires 100+ events.

---

## 4. Files Modified

| File | Change |
|------|--------|
| `config.py` | Added `BlacklistConfig` and `WatchlistConfig` dataclasses |
| `directional_bias.py` | Blacklist check at filter entry. sell_exhaustion removed from structural set. |
| `confidence.py` | Blacklisted event types get reliability cap (0.10). |
| `manager.py` | Integrated `BlacklistWatchlistManager`. Blacklisted events logged but not tradeable. |
| `blacklist_watchlist.py` | NEW — enforcement layer, snapshot storage, CSV export. |
| `candidate_watchlist.py` | NEW — standalone snapshot module (alternative to blacklist_watchlist). |

## 5. Files NOT Modified

| File | Reason |
|------|--------|
| All detectors | Detector logic unchanged. Blacklist is enforcement-layer only. |
| Scoring engine | No threshold changes. Blacklisted score cap applied by directional_bias. |
| Validation scripts | Existing scripts work with the new structure. |

---

## 6. Enforcement Flow

```
Event detected by any detector
  │
  ├─ Is it blacklisted?
  │   YES → log_blacklisted(event)
  │         cap composite_score to 0.15
  │         cap confidence event_reliability to 0.10
  │         register for outcome tracking (for diagnostics)
  │         DO NOT add to tradeable history
  │         DO NOT pass directional filter
  │         CONTINUE to next event
  │
  ├─ Is it watchlisted?
  │   YES → capture_snapshot(event)
  │         record price/delta/CVD/volume paths
  │         continue normal processing (logged, scored, tracked)
  │
  └─ Normal processing → dedup, score, log, track
```

---

## 7. Promotion Rules

### Blacklist removal (sell_exhaustion, sell_imbalance, sell_cluster)
Only possible if:
1. New evidence shows detector logic is structurally sound
2. 100+ events with positive gross at some horizon
3. Formal re-audit with forensic methodology

### Watchlist promotion (sell_absorption, down_break, up_break)
Only possible if:
1. ≥100 completed events
2. Gross positive at ≥1 horizon
3. Net ≥0 at 4bps cost
4. Stable across two chronological splits
5. No parameter tuning between collection and validation

---

## 8. Verification

```bash
# Verify blacklist enforcement
python3 -c "
import sys; sys.path.insert(0, 'backend')
from event_engine.blacklist_watchlist import is_blacklisted, is_watchlisted
assert is_blacklisted('exhaustion', 'sell_exhaustion') == True
assert is_blacklisted('exhaustion', 'buy_exhaustion') == False
assert is_watchlisted('absorption', 'sell_absorption') == True
assert is_watchlisted('range_break', 'down_break') == True
assert is_watchlisted('range_break', 'up_break') == True
assert is_watchlisted('exhaustion', 'buy_exhaustion') == False
print('ALL VERIFIED')
"
```

---

## 9. Promotion Criteria Gate

**Final rule:**

No production integration until candidate watchlist demonstrates:
- Positive net expectancy after 4–6 bps costs
- Across at least two chronological splits
- With ≥100 events per candidate type

Do NOT tune thresholds. Do NOT modify detector internals.
If criteria fail, reject or keep collecting.
