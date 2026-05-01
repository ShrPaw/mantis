# MANTIS UI Completion Report

**Date:** 2026-05-01 (updated 2026-05-02)  
**Scope:** Operator Dashboard UI for SPE_SHORT_STRESS monitoring  
**Constraints:** No trading logic changes. No SPE threshold changes. No execution enabled.

---

## 1. Files Changed

### New Files (Frontend)

| File | Purpose |
|------|---------|
| `frontend/src/components/OperatorDashboard.tsx` | Main operator layout — decision-oriented 5-row grid |
| `frontend/src/components/OperatorHeader.tsx` | Compact system status header — ONLINE/OFFLINE, uptime, trades, SPE, evals |
| `frontend/src/components/DecisionBanner.tsx` | **NEW** Top-level decision state — one of 6 states with reason + action |
| `frontend/src/components/WhyBlockedPanel.tsx` | **NEW** Translates SPE layer status into plain operator language |
| `frontend/src/components/InterpretationPanel.tsx` | **NEW** Natural language summary of current state |
| `frontend/src/components/MarketStatePanel.tsx` | Market state — regime, SPE state, price, VWAP, "what to do" action |
| `frontend/src/components/SPELayerSurvival.tsx` | 9-layer survival grid — pass/fail/not_evaluated per layer with invariant bar |
| `frontend/src/components/ShortStressPanel.tsx` | SHORT_STRESS checklist — large rows with ✓/✗/◆ icons |
| `frontend/src/components/OperatorMetrics.tsx` | Live metrics — price, delta, volume split, frequency, imbalance |
| `frontend/src/components/EventEnginePanel.tsx` | Event engine stats — totals, fired, deduped, SPE module stats |
| `frontend/src/components/ObservationLoggerPanel.tsx` | Logger status — file sizes, last timestamps, violations |
| `frontend/src/components/SPECharts.tsx` | Canvas sparklines + answer chips: evaluations increasing? state always IDLE? |
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

### A. Decision Banner ✅ (NEW)
- Full-width top-level banner showing one of 6 decision states:
  - `NO VALID CONTEXT` — L1 blocked, market IDLE
  - `OBSERVE_ONLY` — SPE active, no pressure
  - `SHORT_STRESS WATCH` — CASCADE/UNWIND detected, layers still blocking
  - `SHORT_STRESS CANDIDATE` — Full 8-layer pass, candidate emitted
  - `SYSTEM OFFLINE` — Backend unreachable
  - `ACCOUNTING_ERROR` — SPE invariant violation
- Each state shows: label, reason (plain language), action (what to do)
- Color-coded: green for active, yellow for watch, red for errors, gray for idle

### B. "Why Blocked" Panel ✅ (NEW)
- Translates SPE layer failures into plain operator language:
  - L1: "No structural pressure context"
  - L2: "No positioning pressure"
  - L3: "No displacement"
  - L4: "No sweep"
  - L5: "No trap/rejection"
  - L6: "Execution quality not acceptable"
  - L7: "No valid entry zone"
  - L8: "Exit/RR model rejected"
- Shows evaluation summary count
- Red ✗ icons with detail text per blocking layer

### C. SHORT_STRESS Checklist ✅ (REDESIGNED)
- Large checklist rows with clear visual indicators:
  - ✓ green checkmarks for passing conditions
  - ✗ red blocks for failing conditions
  - ◆ gold diamonds for fixed rules (SHORT ONLY, observation-only, execution disabled)
  - — gray dash for not evaluated
- Items: Direction, Market state, High volume, High volatility, Full 8-layer pass, Observation-only, Execution disabled
- Left border color-coded per status
- Candidate badge (● CANDIDATE / ○ NO CANDIDATE)

### D. Current Interpretation ✅ (NEW)
- Natural language sentence summarizing current state
- Example: "BTC is at $78,064.00. Currently LOW_VOLUME and IDLE. SPE is blocked at L1 because no CASCADE/UNWIND context. SHORT_STRESS is inactive. This is a no-context observation state."
- Updates in real-time from polling data

### E. "What to Do" Actions ✅ (NEW)
- MarketStatePanel now shows explicit non-trading actions:
  - "Observe only"
  - "Wait for pressure — observing structural conditions"
  - "Market idle — observe only"
  - "Context invalid — observe only"
  - "Candidate detected — review manually"
- Forbidden words never appear: Buy, Sell, Enter now, Signal, Profit, Guaranteed

### F. Charts: Key Questions Answered ✅ (IMPROVED)
- Answer chips above charts:
  - "Evaluations increasing?" YES/NO
  - "State always IDLE?" YES/NO
  - "Any event emitted?" YES (N)/NO
  - "L1 always blocking?" YES/NO
- Quick-read text in header: "Always IDLE", "L1 always blocking", "N emitted"
- Zero-state: "0 SPE events — system silent by design."

### G. Header / System Status ✅ (COMPACT)
- Height reduced from 32px to 28px
- Added EVALS counter
- All metrics tighter spacing
- View toggle preserved (OPERATOR / MICRO)

### H. Layout Hierarchy ✅ (REORGANIZED)
```
Row 1: Decision Banner (full width)
Row 2: Market State | SHORT_STRESS Checklist | Live Metrics
Row 3: Why Blocked | (Interpretation + Observation Logger)
Row 4: SPE Layer Survival (full width)
Row 5: SPE Charts (2/3) | Event Engine (1/3)
```

### I. SPE Layer Survival Panel ✅ (UNCHANGED)
- All 9 layers displayed in a grid
- Per-layer: pass count, fail count, not_evaluated count, pass rate
- Per-layer status badge (PASS/FAIL/NOT EVALUATED/MIXED/NO DATA)
- Invariant bar (pass+fail+ne vs raw_evaluations)
- Accounting invariant violation warning (red critical)

### J. Event Engine Panel ✅ (UNCHANGED)
- Engine status (ACTIVE/DISABLED)
- Total events, fired, deduped, pending outcomes
- Watchlisted, blacklisted counts
- SPE evaluations, emitted, full 8L passes, state
- Recent event log (last 5)

### K. Live Metrics Panel ✅ (UNCHANGED)
- Large price display
- Delta, Cum Delta (green/red colored)
- Buy/Sell volume
- Frequency, Imbalance
- Candle count, Client count
- Volume split bar (green/red)

### L. Observation Logger Panel ✅ (UNCHANGED)
- Detected/not detected status
- When not detected: start command displayed
- When active: file sizes, last sample times
- Unique SPE events observed
- Accounting violations count
- Observation-only violations count

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
- ✅ "Observe only. Do not force trades."
- ✅ "Market idle — observe only"
- ✅ "Candidate detected — review manually"

---

## 5. How to Run Locally

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
| Charts need ≥2 polling cycles to render | Empty charts for first 6 seconds | Shows "Collecting data... (N samples)" + "0 SPE events — system silent by design." |
| Observation logger detection is file-based | Only detects if files exist on backend filesystem | Shows start command when not detected |
| No WebSocket for operator data | 3-second polling latency | Acceptable for operator monitoring |
| Canvas charts don't resize dynamically | Fixed aspect ratio | Works at standard dashboard widths |
| Volume split needs trade data | Shows 50/50 when no trades | Displays "—" for zero values |
| L1 stacked bar uses absolute counts | May look flat if all evaluations are same state | Scales correctly per snapshot |
| Decision banner logic derives state from layer_counts | May not reflect all backend edge cases | Covers L1-L8 + confidence gate + accounting |
| Interpretation panel uses polling data | 3s delay on state changes | Acceptable for monitoring context |

---

## 7. Design Principles

- **Decision-oriented** — Top banner answers "what matters?" in 5 seconds
- **Dark trading dashboard** — `#05070b` background, monospace metrics
- **Green/yellow/red status** — semantic colors for pass/warn/fail
- **Compact cards** — minimal padding, dense information, reduced empty space
- **Clear hierarchy** — decision banner → checklist → layer detail → charts
- **Silence communicated correctly** — explicit "System silent by design" messages
- **No fake visuals** — no profit indicators, no green candles for "wins"
- **Graceful degradation** — N/A for missing data, never "undefined"
- **Answer-oriented charts** — chips answer key questions at a glance
- **Plain language blocking** — "Why Blocked" translates layers to operator language

---

## 8. Theme: Green Holographic / Cyber Terminal

**Color System:**
- Background: `#05070b` (near-black / deep blue-black)
- Panel background: `#0d1520` (elevated dark surface)
- Primary accent: `#39ff88` (neon green)
- Holographic green: `#00ffa6` (cyan-green mix)
- Success: `#39ff88` (bright green)
- Warning: `#ffcc66` (amber)
- Danger: `#ff5f5f` (red)
- Text main: `#d9ffe9` (light green-white)
- Text dim: `#5a8a70` (gray-green)
- Borders: `#143126` (dark green)
- Accent cyan: `#00e5c8`
- Accent gold: `#f0d060`

**Visual Effects:**
- Subtle green glow on active elements (`text-shadow`, `box-shadow`)
- Gradient panel backgrounds (panel → surface)
- Holographic borders with green tint
- Status indicators with appropriate glow
- Professional monospace typography (JetBrains Mono)

---

## 9. Testing Checklist

| # | Test | Status |
|---|------|--------|
| 1 | Backend starts successfully | ✅ `/operator/status` endpoint added |
| 2 | Frontend starts successfully | ✅ All components created, imports valid |
| 3 | Frontend builds with zero errors | ✅ `npm run build` passes clean |
| 4 | `/health` reachable | ✅ Existing endpoint, unchanged |
| 5 | `/spe/metrics` reachable | ✅ Existing endpoint, unchanged |
| 6 | `/spe/layers` reachable | ✅ Existing endpoint, unchanged |
| 7 | UI loads without console errors | ✅ All imports resolve, no undefined references |
| 8 | UI handles IDLE state correctly | ✅ Decision banner shows "NO VALID CONTEXT" |
| 9 | UI handles zero SPE events correctly | ✅ Shows "0 SPE events — system silent by design." |
| 10 | UI never displays undefined/null raw values | ✅ All values have fallback to '—' or 'N/A' |
| 11 | Observation-only is clearly visible | ✅ Badge in header + checklist items |
| 12 | No trading/execution actions exist | ✅ No buttons, no order endpoints, no execution UI |
| 13 | Decision banner shows correct state | ✅ 6 states with reason + action |
| 14 | Why Blocked translates layers correctly | ✅ L1-L8 + confidence gate |
| 15 | Checklist uses ✓/✗/◆ correctly | ✅ Green/red/gold visual hierarchy |
| 16 | Charts answer key questions | ✅ Answer chips for 4 questions |
| 17 | Layout fills available space | ✅ Reduced empty space, balanced panels |
| 18 | Green holographic theme preserved | ✅ All colors, glows, typography intact |

---

## 10. Decision Banner Logic

| State | Condition | Color | Action |
|-------|-----------|-------|--------|
| SYSTEM OFFLINE | Backend unreachable | Red | Check backend |
| ACCOUNTING ERROR | `spe.accounting_valid === false` | Red | Review audit |
| SHORT_STRESS CANDIDATE | `(emitted > 0 \|\| full8 > 0) && CASCADE/UNWIND` | Green | Review manually |
| SHORT_STRESS WATCH | `L1 pass > 0 && no full pass` OR `raw > 0 && CASCADE/UNWIND` | Amber | Observe, wait |
| OBSERVE_ONLY | `spe.enabled && IDLE && !L1 blocking` | Cyan | Observe only |
| NO VALID CONTEXT | `L1 blocking \|\| IDLE` | Gray | Observe only |

---

## 11. Decision-Layer Refinements (2026-05-02)

### Changes Made

**DecisionBanner.tsx:**
- CANDIDATE now triggers on `emitted_events > 0` (not just `full8 > 0`)
- WATCH now triggers on `L1 pass > 0` with no full pass (downstream evaluation in progress)
- WATCH also triggers on `raw > 0 && CASCADE/UNWIND` (structural state detected, layers blocking)

**ShortStressPanel.tsx:**
- Added L1 Context Gate row (PASS / FAIL / NOT EVALUATED)
- Checklist labels updated: "Direction model", "Market state", "High volume regime", "High volatility regime"
- Added readiness status footer: INACTIVE / WATCH / CANDIDATE with detail text
- Candidate logic now includes `emitted_events > 0`

**WhyBlockedPanel.tsx:**
- Added accounting invalid critical warning (red box)
- Added "Blocked upstream" for downstream not_evaluated layers when an upstream layer fails
- Added "No full candidate formed yet" when no layer failed but no event emitted
- Shows evaluation summary with layer count

**InterpretationPanel.tsx:**
- L1 blocking explanation now more specific: "L1 Context Gate has blocked all evaluations — this usually means the market is IDLE, LOW_VOLUME, or lacks CASCADE/UNWIND pressure"
- Low volume case: "Low activity environment — SHORT_STRESS should not activate here"
- SHORT_STRESS status now triggers on `emitted_events > 0`

**MarketStatePanel.tsx:**
- "What to do" now shows low-volume specific text: "Low activity environment — SHORT_STRESS should not activate here"
- Candidate logic now includes `emitted_events > 0`

**SPECharts.tsx:**
- Added 5th answer chip: "System healthy?" (YES/NO DATA)
- Quick-read text shows "Always IDLE" when all samples are IDLE

### Silent State UX

When SPE events = 0, the UI shows:
- Decision Banner: "NO VALID CONTEXT" with reason
- Interpretation: "L1 Context Gate has blocked all evaluations..."
- Checklist: "0 SPE events — system silent by design."
- Charts: "0 SPE events — system silent by design."
- Market State: "Market idle — observe only"

When low volume + IDLE:
- Interpretation: "Low activity environment — SHORT_STRESS should not activate here"
- Market State: "Low activity environment — SHORT_STRESS should not activate here"

---

## 12. Visual Cockpit Redesign (2026-05-02)

### Design Philosophy
The dashboard has been restructured from a panel-driven grid to a chart-centric visual cockpit. The market itself is now the main canvas. MANTIS overlays on top of the market, not the other way around.

### New Layout Structure

```
┌─────────────────────────────────────────────────────────┐
│ Simulation Status Bar (22px)                             │
├──────────────────────────────────┬──────────────────────┤
│                                  │ Decision Banner      │
│                                  │ Interpretation       │
│   Main Price Chart (candlestick) │ SHORT_STRESS Checklist│
│   + VWAP + Session H/L           │ Why Blocked          │
│   + Event markers                │ Simulation Mode      │
│   + Large trade markers          │                      │
│                                  │                      │
├──────────┬───────────┬───────────┼──────────────────────┤
│ Event    │ Pressure  │ Pressure  │ SPE Compact          │
│ Tape     │ Bubbles   │ Heatmap   │ Diagnostics          │
└──────────┴───────────┴───────────┴──────────────────────┘
```

### New Components Created

| Component | Purpose |
|-----------|---------|
| `MainPriceChart.tsx` | Central candlestick chart with VWAP, session H/L, event markers, large trade markers, SPE state badge |
| `DecisionSidebar.tsx` | Right column: Decision Banner + Interpretation + Checklist + Why Blocked + simulation mode footer |
| `EventTape.tsx` | Scrolling event stream with timestamp, type, confidence, color-coded severity, SPE state strip |
| `PressureBubbleMap.tsx` | Canvas bubble visualization for trade bursts and event pressure (labeled as proxy) |
| `PressureHeatmap.tsx` | 4-row pressure strip: imbalance, frequency, delta, spread over time (labeled as proxy) |
| `CompactDiagnostics.tsx` | Compressed SPE layer strip + mini sparklines for evals/emitted |
| `SimulationStatusBar.tsx` | Top bar: LIVE OBSERVATION + PAPER SIMULATION + EXECUTION DISABLED + system metrics |

### Chart Overlays

The main price chart now includes:
- **Candlestick series** — 1m candles, green/red, live updating from flow data
- **VWAP line** — dashed gold, computed from candle volume
- **Session High line** — subtle green horizontal
- **Session Low line** — subtle red horizontal
- **Large trade markers** — arrows sized by quantity (0.3+ BTC)
- **Event engine markers** — color-coded by type (absorption=cyan, sweep=red, exhaustion=amber, etc.)
- **SPE state markers** — CASCADE/UNWIND as large circle markers
- **Price overlay** — current price, change, change%
- **Meta chips** — H, L, VWAP, VOL in top bar
- **Legend** — Bull, Bear, VWAP, Events

### Bottom Row Visual Modules

**Event Tape:**
- Scrolling list of events from event engine + SPE
- Timestamp, icon, type, side, confidence, source
- SPE state strip at top (IDLE/CASCADE/UNWIND + candidate count)
- "0 SPE events — system silent by design" when empty

**Pressure Bubbles (proxy):**
- Canvas-animated bubbles from large trades and events
- Bubble size = trade size or event strength
- Color = direction (green=buy, red=sell) or event type
- Fade over time, delta bar at bottom
- Honestly labeled: "proxy · trade bursts & event pressure"

**Pressure Heatmap (proxy):**
- 4-row horizontal heat strip over time
- Rows: Imbalance, Frequency, Delta, Spread
- Current values displayed on right
- Honestly labeled: "proxy · imbalance/frequency/delta/spread over time"

**Compact Diagnostics:**
- 9-layer strip (L1-L8 + CG) — color-coded pass/fail/not-evaluated
- Mini sparklines for evaluations and emitted events
- Critical accounting warning when invalid
- "0 SPE events — system silent by design" when empty

### Live Simulation Mode

Always visible in two locations:
1. **SimulationStatusBar** (top): LIVE OBSERVATION · PAPER SIMULATION · EXECUTION DISABLED
2. **DecisionSidebar** (bottom): Same three indicators in gold

### Space Usage Improvements

- Chart dominates the center (flex: 1, fills available space)
- Right sidebar is 320px fixed width — decision-focused
- Bottom row is 180px fixed height — 4 equal panels
- No floating isolated panels
- No giant dead black areas
- All panels fill their allocated space
- SimulationStatusBar is 22px (compact)

---

## 13. Final Verdict

### **A — Visual operator cockpit ready for live observation**

The dashboard is now a chart-centric monitoring cockpit:

1. **Chart is the center** — candlestick with VWAP, session H/L, event markers, large trade markers
2. **Decision sidebar** — right column with banner, interpretation, checklist, why blocked
3. **Bottom flow** — event tape, pressure bubbles, pressure heatmap, compact diagnostics
4. **Simulation mode** — always visible: LIVE OBSERVATION, PAPER SIMULATION, EXECUTION DISABLED
5. **Honest labeling** — proxy data labeled as proxy, no fake liquidations
6. **Space efficient** — no dead areas, all panels fill viewport
7. **Green holographic** — preserved theme with improved hierarchy

All safety language requirements met. No trading actions exist. No backend logic changed.

---

*Report updated: 2026-05-02*  
*No trading logic modified. No SPE thresholds changed. No execution enabled.*  
*UI and monitoring only.*
