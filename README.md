# MANTIS — BTCUSDT Microstructure Dashboard

Real-time decision-support dashboard for intraday BTC trading.  
**NOT a bot. NOT signals. Raw microstructure data visualization.**

**Data source: [Hyperliquid](https://hyperliquid.xyz) DEX** — decentralized, no API key, no blocks.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/ShrPaw/mantis.git
cd mantis

# 2. Start backend (Terminal 1)
cd backend
pip install -r requirements.txt
python main.py

# 3. Open http://localhost:3000
# (frontend is served by backend — no separate server needed)
```

That's it. No proxy. No VPN. No API key. Works from anywhere.

---

## Architecture

```
┌──────────────────────┐     WebSocket      ┌──────────────────┐
│   Hyperliquid DEX    │ ◄────────────────── │   MANTIS Backend  │
│   wss://api.hyper... │   (trades,         │   Python/FastAPI  │
│   (decentralized)    │    l2Book, candle)  │   :8000           │
└──────────────────────┘                     └────────┬─────────┘
                                                      │ WebSocket
                                                      ▼
                                             ┌──────────────────┐
                                             │  MANTIS Frontend  │
                                             │  React + Vite     │
                                             │  :3000            │
                                             └──────────────────┘
```

## What's Included

- **Live candlestick chart** with large trade markers
- **Flow metrics** — taker buy/sell, delta, cumulative delta, imbalance, trade frequency
- **Bubble tape** — large trades (≥0.5 BTC) with size-scaled colored bubbles
- **Order book heatmap** — bid/ask liquidity with wall detection (Canvas)
- **Footprint chart** — volume clusters per price level per 1m candle (Canvas)
- **Absorption detection** — high volume + near-zero delta at a price level
- **Session stats** — VWAP, session high/low
- **Auto-reconnect** WebSocket
- **Dark theme**

## Design Rules

- ❌ No buy/sell signals
- ❌ No predictive claims
- ❌ No indicator stacking
- ✅ Only raw + processed microstructure data
- ✅ Everything explainable and observable

## Tech Stack

| Layer    | Tech                                    |
|----------|-----------------------------------------|
| Backend  | Python, FastAPI, asyncio, websockets    |
| Frontend | React, lightweight-charts, Canvas       |
| Data     | Hyperliquid DEX (free, no key, no block)|

## File Structure

```
backend/
  main.py              — FastAPI app, WebSocket server
  hyperliquid_ws.py    — Hyperliquid WS client
  metrics.py           — Microstructure engine
  requirements.txt     — Python dependencies
frontend/
  App.jsx              — Main layout
  hooks/useWebSocket.js — WS connection with auto-reconnect
  components/
    PriceChart.jsx   — Candlestick + trade markers
    FlowPanel.jsx    — Flow metrics panel
    BubbleTape.jsx   — Large trade bubbles
    Heatmap.jsx      — Order book heatmap (Canvas)
    Footprint.jsx    — Volume clusters (Canvas)
    StatusBar.jsx    — Top status bar
  utils/format.js   — Number formatting
```

## Configuration

In `metrics.py`:
- `LARGE_TRADE_THRESHOLD = 0.5` BTC — what counts as a "large trade"
- `ROLLING_WINDOW = 300` seconds for frequency calculation
- `MAX_FOOTPRINT_CANDLES = 60` kept in memory

## License

MIT
