# MANTIS SPE — Next Session Context

## What Was Done (2026-04-30)

SPE (Structural Pressure Execution) module fully integrated into MANTIS in **observation-only mode**.

### Commits on main:
1. `eb1ac76` — SECURITY_CHECK.md (repo clean)
2. `930837e` — SPE observation-only integration (backend: manager.py, main.py, __init__.py, start.sh)
3. `b300b4e` — SPE dashboard panel (frontend: SPEPanel.tsx, store.ts, types.ts, useWebSocket.ts, App.tsx)
4. `21c937d` — SPE smoke test script (scripts/smoke_test_spe.py)
5. `c3b3761` — SPE validation script (scripts/validate_spe.py)
6. `2fcb12c` — Three-state layer accounting fix (pass/fail/not_evaluated)
7. `1c74e17` — Verification commit

### Key Architecture:
- SPE lives in `backend/event_engine/spe/` — 8-layer pipeline (all implemented)
- Wired into `backend/event_engine/manager.py` — additive, non-breaking
- Feature flags: `SPE_ENABLED=true`, `SPE_OBSERVATION_ONLY=true`
- Events stored: `data/events/spe_events.jsonl`, `spe_events.csv`
- Metrics: `data/metrics/spe_metrics.json`
- Frontend: `SPEPanel.tsx` in far-right column, observation-only language
- Broadcast: `spe_stats` and `spe_detected` message types

### Current State:
- Backend starts, SPE loads, Hyperliquid connects
- L1_context_gate blocks all evaluations (market is IDLE, not CASCADE/UNWIND)
- Three-state accounting confirmed: L1=fail, L2-L8=not_evaluated
- spe_metrics.json persists correctly (backend runs from `backend/` dir)
- 0 SPE events emitted (expected — no structural pressure conditions yet)

## What's Left

### Phase 5: 30-Minute Smoke Test
- Run: `python3 scripts/smoke_test_spe.py --duration 1800`
- Needs: MANTIS running + live Hyperliquid data
- Output: `MANTIS_SPE_SMOKE_TEST_REPORT.md`
- Verdict: A / B / C

### Phase 6: 6-Hour Live Observation Audit (only if smoke test = A or strong B)
- Run: `python3 scripts/smoke_test_spe.py --duration 21600 --output MANTIS_SPE_6H_LIVE_AUDIT.md`
- Track: market state before/after SPE events, timing, noise
- Verdict: A / B / C

### Phase 7: Historical Validation
- Run: `python3 scripts/validate_spe.py --events data/events/spe_events.jsonl --candles data/candles.jsonl`
- Needs: collected SPE events + candle history
- Compares SPE vs random/vol-matched/opposite baselines
- Output: `MANTIS_SPE_VALIDATION_REPORT.md` + `data/spe_validation.json`
- Verdict: A / B / C / D

### Phase 8: Final Reporting
- Classify SPE: A (useful layer) / B (too restrictive) / C (not useful) / D (kill module)
- Separate: detection quality, execution usefulness, directional edge, noise risk, cost survivability

### Known Issue:
- Backend runs from `backend/` dir, so `data/` paths are relative to that
- `spe_events.jsonl` goes to `backend/data/events/` not root `data/events/`
- Validation script needs path adjustment: `--events backend/data/events/spe_events.jsonl`

### Security Reminder:
- GitHub PAT `ghp_...` was shared in plaintext chat — **rotate it**
- Repo itself is clean, no secrets committed

### Commands:
```bash
# Start MANTIS
cd mantis && bash start.sh

# 30-min smoke test
python3 scripts/smoke_test_spe.py --duration 1800

# 6-hour audit
python3 scripts/smoke_test_spe.py --duration 21600 --output MANTIS_SPE_6H_LIVE_AUDIT.md

# Historical validation
python3 scripts/validate_spe.py --events backend/data/events/spe_events.jsonl --candles <candles.jsonl>

# Check health
curl http://localhost:8000/health
curl http://localhost:8000/spe/layers
curl http://localhost:8000/spe/metrics
```

### Absolute Constraints (DO NOT VIOLATE):
- Do NOT enable real trading
- Do NOT change thresholds after seeing results
- Do NOT remove existing MANTIS functionality
- Do NOT break dashboard
- Do NOT hide negative findings
- Do NOT claim smart money detection
- Do NOT call SPE a signal before validation
- Do NOT optimize for backtest PnL
- Do NOT use cherry-picked examples
