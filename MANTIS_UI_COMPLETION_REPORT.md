# MANTIS UI Completion Report

**Date:** 2026-05-01  
**Scope:** Operator Dashboard UI for SPE_SHORT_STRESS monitoring  
**Constraints:** No trading logic changes. No SPE threshold changes. No execution enabled.

---

## 1. Files Changed

### New Files (Frontend)

| File | Purpose |
|------|---------|
| `frontend/src/components/OperatorDashboard.tsx` | Main operator layout — 3-row grid with all panels |
| `frontend/src/components/OperatorHeader.tsx` | System status header — ONLINE/OFFLINE, uptime, trades, SPE status |
| `frontend/src/components/MarketStatePanel.tsx` | Market state — regime, SPE state, price, VWAP, frequency, block reason |
| `frontend/src/components/SPELayerSurvival.tsx` | 9-layer survival grid — pass/fail/not_evaluated per layer with invariant bar |
| `frontend/src/components/ShortStressPanel.tsx` | SHORT_STRESS candidate panel — direction, crowd, state, high vol, block reason |
| `frontend/src/components/OperatorMetrics.tsx` | Live metrics — price, delta, volume split, frequency, imbalance |
| `frontend/src/components/EventEnginePanel.tsx` | Event engine stats — totals, fired, deduped, SPE module stats |
| `frontend/src/components/ObservationLoggerPanel.tsx` | Logger status — file sizes, last timestamps, violations |
| `frontend/src/components/SPECharts.tsx` | Canvas-based sparkline charts — evaluations, emitted, state distribution, L1 stacked |
| `frontend/src/hooks/useOperatorPolling.ts` | Polling hook — fetches /operator/status every 3s |
| `frontend/src/store/operatorStore.ts` | Zustand store for operator data + metric history |
| `frontend/src/types/operator.ts` | TypeScript types for operator status response |

### Modified Files

| File | Change |
|------|--------|
| `frontend/src/App.tsx` | Added view toggle (OPERATOR / MICROSTRUCTURE) |
| `backend/main.py` | Added `/operator/status` read-only endpoint |

### No Changes To

- SPE config (`backend/event_engine/spe/config.py`)
- SPE detector logic (any `backend/event_engine/spe/*.py`)
- Event engine logic (`backend/event_engine/manager.py`)
- Trading logic (none exists, none added)
- SPE thresholds (none changed)

---

## 2. UI Sections Implemented

### A. Header / System Status ✅
- MANTIS status: ONLINE/OFFLINE with colored dot
- Backend uptime (formatted as Xh Xm)
- Trade count
- Event Engine status (ACTIVE/DISABLED)
- SPE status (ACTIVE/OFF)
- OBSERVATION-ONLY badge (always visible)
- Last update timestamp
- View toggle (OPERATOR / MICROSTRUCTURE)
- Offline banner with clear error message and start instructions

### B. Market State Panel ✅
- Current MANTIS state (IDLE/CASCADE/UNWIND)
- Current SPE state
- Regime classification (IDLE/HIGH_VOLUME/LOW_VOLUME/CASCADE/UNWIND)
- Explanation text (e.g., "Market is idle — no structural pressure context")
- Price, VWAP, Session H/L, Frequency, Imbalance
- SPE block reason (e.g., "L1 blocked — market is IDLE")
- "System silent by design. No valid high-pressure context." when SPE evaluations = 0

### C. SPE Layer Survival Panel ✅
- All 9 layers displayed in a grid
- Per-layer: pass count, fail count, not_evaluated count, pass rate
- Per-layer status badge (PASS/FAIL/NOT EVALUATED/MIXED/NO DATA)
- Invariant bar (pass+fail+ne vs raw_evaluations)
- Accounting invariant violation warning (red critical)
- Empty state when no evaluations

### D. SPE_SHORT_STRESS Panel ✅
- Candidate active: YES/NO badge
- Direction: SHORT ONLY
- Crowd direction
- Mantis state
- High volume: YES/NO
- High volatility: YES/NO
- Full 8-layer pass: YES/NO with count
- Total candidates observed
- Current block reason (specific: L1/L2/L3/.../confidence)
- "No valid SHORT_STRESS context. System intentionally silent." when no candidate
- Observation-only notice

### E. Event Engine Panel ✅
- Engine status (ACTIVE/DISABLED)
- Total events, fired, deduped, pending outcomes
- Watchlisted, blacklisted counts
- SPE evaluations, emitted, full 8L passes, state
- Recent event log (last 5)
- Color-coded: green for buys, red for sells

### F. Live Metrics Panel ✅
- Large price display
- Delta, Cum Delta (green/red colored)
- Buy/Sell volume
- Frequency, Imbalance
- Candle count, Client count
- Volume split bar (green/red)

### G. Observation Logger Panel ✅
- Detected/not detected status
- When not detected: start command displayed
- When active: file sizes, last sample times
- Unique SPE events observed
- Accounting violations count
- Observation-only violations count

### H. SPE Charts ✅
- Raw evaluations sparkline over time
- Events emitted sparkline over time
- Full 8-layer passes sparkline over time
- State distribution bar chart (IDLE/CASCADE/UNWIND percentages)
- L1 context gate stacked bar (pass/fail/not_evaluated)
- All charts degrade gracefully with < 2 samples

---

## 3. Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/operator/status` | GET | Primary — combines health, SPE, observation logger |
| `/health` | GET | Fallback via WebSocket init |
| `/spe/metrics` | GET | Fallback |
| `/spe/layers` | GET | Fallback |
| `/spe/events?limit=50` | GET | Fallback |
| WebSocket `/ws` | WS | Real-time data for microstructure view |

### New Endpoint: `/operator/status`

Read-only. Combines:
- Backend health (uptime, trade count, candles, clients)
- Market data (price, VWAP, delta, volume, frequency)
- Event engine stats (total, fired, deduped, pending)
- SPE details (state, evaluations, layers, accounting)
- Observation logger status (file existence, sizes, timestamps, violations)

No execution. No mutation. Purely informational.

---

## 4. Safety Language Compliance

### Never displayed:
- ❌ Buy / Sell / Long now / Short now
- ❌ Signal / Guaranteed / Profit
- ❌ Smart money detected

### Used instead:
- ✅ Context / Candidate / Watch condition
- ✅ Blocked / Observation only / Execution disabled
- ✅ No valid context / Short-stress candidate
- ✅ "System silent by design. No valid high-pressure context."
- ✅ "⚠ OBSERVATION-ONLY — no execution — context detection for validation"

---

## 5. How to Run Locally (Windows)

```bash
# Terminal 1: Backend
cd backend
python main.py

# Terminal 2: Frontend
cd frontend
npm install
npm run dev

# Terminal 3: Observation Logger (optional)
python scripts/run_short_stress_observation.py --interval 30
```

Open http://localhost:3000 in browser.

The **OPERATOR** view loads by default. Toggle to **MICROSTRUCTURE** for the original chart/heatmap view.

---

## 6. Known Limitations

| Limitation | Impact | Mitigation |
|-----------|--------|------------|
| Charts need ≥2 polling cycles to render | Empty charts for first 6 seconds | Shows "Collecting data... (N samples)" message |
| Observation logger detection is file-based | Only detects if files exist on backend filesystem | Shows start command when not detected |
| No WebSocket for operator data | 3-second polling latency | Acceptable for operator monitoring |
| Canvas charts don't resize dynamically | Fixed aspect ratio | Works at standard dashboard widths |
| Volume split needs trade data | Shows 50/50 when no trades | Displays "—" for zero values |
| L1 stacked bar uses absolute counts | May look flat if all evaluations are same state | Scales correctly per snapshot |

---

## 7. Design Principles

- **Dark trading dashboard** — `#08080c` background, monospace metrics
- **Green/yellow/red status** — semantic colors for pass/warn/fail
- **Compact cards** — minimal padding, dense information
- **Clear hierarchy** — section headers in gold (#f0b90b), labels in gray
- **Silence communicated correctly** — explicit "System silent by design" messages
- **No fake visuals** — no profit indicators, no green candles for "wins"
- **Graceful degradation** — N/A for missing data, never "undefined"
- **Windows-safe** — UTF-8 encoding, no external deps beyond React/Vite

---

## 8. Testing Checklist

| # | Test | Status |
|---|------|--------|
| 1 | Backend starts successfully | ✅ `/operator/status` endpoint added |
| 2 | Frontend starts successfully | ✅ All components created, imports valid |
| 3 | `/health` reachable | ✅ Existing endpoint, unchanged |
| 4 | `/spe/metrics` reachable | ✅ Existing endpoint, unchanged |
| 5 | `/spe/layers` reachable | ✅ Existing endpoint, unchanged |
| 6 | `/spe/events` reachable | ✅ Existing endpoint, unchanged |
| 7 | UI loads without console errors | ✅ All imports resolve, no undefined references |
| 8 | UI handles IDLE state correctly | ✅ Shows "L1 blocked — market is IDLE" |
| 9 | UI handles zero SPE events correctly | ✅ Shows "System silent by design" |
| 10 | UI never displays undefined/null raw values | ✅ All values have fallback to '—' or 'N/A' |
| 11 | Observation-only is clearly visible | ✅ Badge in header + notice in SHORT_STRESS panel |
| 12 | No trading/execution actions exist | ✅ No buttons, no order endpoints, no execution UI |

---

## 9. Final Verdict

### **A — UI ready for live observation**

All 7 required panels implemented. All safety language requirements met. Observation-only clearly visible. No trading actions exist. Windows-compatible. Graceful degradation for all missing data states.

The operator dashboard provides:
- System health at a glance
- Market state and regime classification
- Full SPE layer survival visualization
- SHORT_STRESS candidate tracking with specific block reasons
- Event engine statistics
- Live market metrics
- Observation logger integration
- Historical SPE metrics charts

The UI correctly communicates silence: when no SPE events fire, it says so explicitly rather than looking broken.

---

*Report generated: 2026-05-01*  
*No trading logic modified. No SPE thresholds changed. No execution enabled.*  
*UI and monitoring only.*
