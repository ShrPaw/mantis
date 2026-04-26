# BTCUSDT Microstructure Dashboard

Real-time decision-support system for intraday trading. NOT a bot, NOT a signal generator — raw microstructure data visualization.

## Architecture

```
Binance Futures WS ──► Python Backend (FastAPI) ──► WebSocket ──► React Frontend
   aggTrade              metrics engine               broadcast      lightweight-charts
   depth@100ms           delta / cum delta                         canvas heatmaps
   kline_1m/5m           footprint / absorption                    bubble tape
```

## Quick Start

```bash
# Terminal 1: Backend
cd backend
pip install -r requirements.txt
python3 main.py

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

## What It Shows

### Live Price Panel
- 1m candles with VWAP overlay
- Session high/low
- Large trade markers on chart

### Order Flow Panel
- Taker buy/sell volume
- Delta (buy - sell)
- Cumulative delta
- Imbalance %
- Trade frequency (trades/sec)

### Bubble Tape
- Large trades only (≥0.5 BTC)
- Size-scaled bubbles
- Color-coded by side (green=buy, red=sell)
- Real-time streaming

### Footprint / Cluster
- Volume bucketed by price level per 1m candle
- Bid/ask volume, delta, imbalance per level
- High-volume nodes highlighted

### Order Book Heatmap
- Visualized bid/ask liquidity levels
- Large walls glow
- Mid-price line
- Volume proportional to bar width

## Design Rules

- **No buy/sell signals**
- **No predictive claims**
- **No indicator stacking**
- Only raw + processed microstructure data
- Everything explainable and observable

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python, FastAPI, asyncio, websockets |
| Frontend | React, lightweight-charts, Canvas |
| Data | Binance Futures WebSocket |
| Transport | WebSocket (backend ↔ frontend) |

## File Structure

```
backend/
  main.py           # FastAPI app + WebSocket server
  binance_ws.py     # Binance Futures stream manager
  metrics.py        # Microstructure computation engine
  requirements.txt

frontend/
  src/
    App.jsx          # Main layout (3-column grid)
    main.jsx         # Entry point
    hooks/useWebSocket.js
    components/
      PriceChart.jsx   # lightweight-charts + markers
      FlowPanel.jsx    # Delta, cum delta, imbalance
      BubbleTape.jsx   # Large trade stream
      Heatmap.jsx      # Order book visualization (canvas)
      Footprint.jsx    # Volume profile per candle (canvas)
      StatusBar.jsx    # Top bar with live price + metrics
    utils/format.js
```

## Configuration

In `metrics.py`:
- `LARGE_TRADE_THRESHOLD = 0.5` BTC — what counts as a "large trade"
- `ROLLING_WINDOW = 300` seconds for frequency calculation
- `MAX_FOOTPRINT_CANDLES = 60` kept in memory

## Phase Roadmap

- [x] Phase 1: Live data foundation (price, trades, delta, heatmap)
- [ ] Phase 2: Flow metrics (absorption, delta divergence, exhaustion labels)
- [ ] Phase 3: Session context (Asia/London/NY ranges, sweeps)
- [ ] Phase 4: News/events panel (macro calendar, countdown)
- [ ] Phase 5: Advanced (liquidation tracking, breakout quality assessment)
