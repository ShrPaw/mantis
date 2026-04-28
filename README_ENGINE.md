# MANTIS Execution Engine

Real-time market context and execution-quality system for BTC/USD.

**NOT a trading bot. NOT a signal generator. NOT a prediction engine.**

MANTIS detects and classifies market states to help a discretionary trader avoid hostile execution environments and identify favorable conditions.

---

## What MANTIS Does

MANTIS classifies the current market into one of five states:

| State | Meaning | Action |
|-------|---------|--------|
| **IDLE** | Normal conditions | Standard execution |
| **CROWD_BUILDUP** | Positioning pressure building | Watch for unwind trigger |
| **LIQUIDATION_CASCADE** | Forced liquidation active | Avoid chasing |
| **UNWIND** | Trapped positions exiting | Monitor maturity |
| **EXHAUSTION_ABSORPTION** | Aggression failing | Watch for reversal |

**MANTIS does NOT say "buy" or "short."** It says: "this market is clean / dirty / dangerous / overloaded / executable / not executable."

---

## Architecture

```
┌─────────────────────┐     ┌─────────────────────┐
│  Hyperliquid DEX    │     │  Binance Futures     │
│  (trades, book,     │     │  (funding, OI,       │
│   candles)          │     │   liquidations)      │
└────────┬────────────┘     └────────┬─────────────┘
         │                           │
         └─────────┬─────────────────┘
                   ▼
        ┌─────────────────────┐
        │  Feature Pipeline   │
        │  - Funding metrics  │
        │  - OI metrics       │
        │  - Liquidation      │
        │  - Trade flow       │
        │  - Order book       │
        │  - Execution quality│
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  4 Detectors        │
        │  - Crowd Buildup    │
        │  - Liq Cascade      │
        │  - Unwind           │
        │  - Exhaustion       │
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  Scoring Engine     │
        │  - Imbalance 0-100  │
        │  - Exec Quality     │
        │  - Risk Score       │
        │  - Trade Env Score  │
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  Alert Manager      │
        │  Tier 1: Watch      │
        │  Tier 2: Actionable │
        │  Tier 3: Danger     │
        └────────┬────────────┘
                 ▼
        ┌─────────────────────┐
        │  Dashboard (Web)    │
        │  Event Logger       │
        │  Validation Script  │
        └─────────────────────┘
```

---

## Quick Start

### 1. Install Dependencies

```bash
cd mantis
pip install -r engine/requirements.txt
cd frontend && npm install && cd ..
```

### 2. Run the Engine

```bash
bash start_engine.sh
```

Or run components separately:

```bash
# Terminal 1: Engine
python3 -m engine.run --config config/mantis_execution_config.yaml

# Terminal 2: Dashboard server
python3 -c "from engine.dashboard_server import run_dashboard; run_dashboard(port=8001)"
```

### 3. Open Dashboard

Open `engine/dashboard.html` in your browser, or serve it:

```bash
# Simple HTTP server
cd engine && python3 -m http.server 3001
# Then open http://localhost:3001/dashboard.html
```

The dashboard connects to `ws://localhost:8001/ws` for real-time updates.

---

## Configuration

All thresholds live in `config/mantis_execution_config.yaml`.

**DO NOT tune thresholds without running validation first.**

Key sections:

```yaml
funding:
  z_extreme: 2.0          # Z-score threshold for funding extreme
  percentile_extreme: 0.95 # Top/bottom 5% = extreme

liquidations:
  cascade_percentile: 0.95 # Top 5% notional = cascade

execution:
  max_spread_bps: 2.0      # Max acceptable spread
  hostile_threshold: 39    # Below this = NO_TRADE

alerts:
  min_seconds_between_same_alert: 60
  max_alerts_per_hour: 20
```

---

## File Structure

```
engine/
  __init__.py              # Package init
  models.py                # All data models (trades, features, states, scores, alerts)
  manager.py               # Core engine orchestrator
  run.py                   # Main entry point
  alerts.py                # Tiered alert system with rate limiting
  logger.py                # Event persistence (JSONL, CSV, JSON)
  dashboard_server.py      # WebSocket server for dashboard
  dashboard.html           # Real-time dashboard frontend
  requirements.txt         # Python dependencies
  connectors/
    __init__.py            # Base connector class
    hyperliquid.py         # Hyperliquid WS + REST connector
    binance.py             # Binance Futures WS + REST connector
  features/
    __init__.py            # Feature pipeline (all metric computation)
  detectors/
    __init__.py            # Four market state detectors
  scoring/
    __init__.py            # Four-score scoring engine

config/
  mantis_execution_config.yaml  # All thresholds and settings

scripts/
  validate_mantis.py       # Historical validation script

data/
  events/
    mantis_events.jsonl    # Event log (streaming)
    mantis_events.csv      # Event log (analysis)
    alerts.jsonl           # Alert history
  metrics/
    realtime_metrics.json  # Current state snapshot (for dashboard)
```

---

## Data Outputs

### Events (JSONL)
One JSON object per line. Each event contains:
- Timestamp, market state, all detector outputs
- All scores, execution mode
- Full feature snapshot (funding, OI, liquidation, flow, book)

### Events (CSV)
Flattened version for spreadsheet/analysis tools.

### Metrics (JSON)
Latest snapshot only. Read by the dashboard server.

### Alerts (JSONL)
Alert history with tier, reason, and execution recommendation.

---

## Scoring System

| Score | Range | Meaning |
|-------|-------|---------|
| Imbalance | 0-100 | How abnormal positioning/flow is |
| Execution Quality | 0-100 | How safe it is to execute (higher = safer) |
| Risk | 0-100 | How dangerous the environment is (higher = worse) |
| Trade Environment | 0-100 | Composite: 0.4×imbalance + 0.35×exec - 0.25×risk |

Trade Environment interpretation:
- **≥ 75** = Favorable environment
- **60-74** = Watchlist only
- **40-59** = Poor
- **< 40** = Avoid

**This is NOT a buy/sell signal. It is an environment classifier.**

---

## Alert Tiers

| Tier | Condition | Meaning |
|------|-----------|---------|
| **1 — Watch** | Imbalance ≥ 60, Exec ≥ 50 | Elevated awareness |
| **2 — Actionable** | Imbalance ≥ 75, Exec ≥ 70, Risk ≤ 60 | Good conditions for limits |
| **3 — Danger** | Risk ≥ 75 OR Exec ≤ 35 OR Cascade ≥ 80 | Avoid all entries |

Every alert includes:
- State, side, severity
- What NOT to do
- Execution recommendation (WAIT / MAKER_ONLY / NO_TRADE / etc.)

---

## Validation

After collecting events, run the validation script:

```bash
python3 scripts/validate_mantis.py \
    --events data/events/mantis_events.jsonl \
    --trades data/research/trades.jsonl \
    --output MANTIS_EXECUTION_VALIDATION_REPORT.md
```

The validation checks:
- Do detected states differ from random?
- Do they improve execution avoidance?
- Do they identify dangerous environments?
- Are results stable across time splits?
- Are results dependent on outliers?

### Final Verdict Classification

| Grade | Meaning |
|-------|---------|
| **A** | Useful Execution Context Engine — detects dangerous/favorable environments better than random |
| **B** | Weak Context Engine — detects abnormal states but limited improvement |
| **C** | Not Useful — noisy, unstable, or indistinguishable from random |

---

## Absolute Constraints

1. **No autonomous trading** — MANTIS classifies environments, not trades
2. **No signal spam** — Alerts are rare and meaningful
3. **No threshold tuning** without validation results
4. **No prediction claims** — Context detection ≠ edge
5. **No hiding negative results** — Report the truth

---

## Running the Existing Dashboard (Original MANTIS)

The original microstructure dashboard is still available:

```bash
bash start.sh
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
```

---

## License

MIT
