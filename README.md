# MANTIS — BTCUSDT Microstructure Dashboard

Real-time decision-support dashboard for intraday BTC trading.  
**NOT a bot. NOT signals. Raw microstructure data visualization.**

![MANTIS](https://img.shields.io/badge/BTCUSDT-Live%20Microstructure-F7931A?style=flat&logo=bitcoin&logoColor=white)

---

## Quick Start

### Windows

```bash
# 1. Clone
git clone https://github.com/ShrPaw/mantis.git
cd mantis

# 2. Start frontend (Terminal 1)
cd frontend
npm install
npm run dev

# 3. Start backend (Terminal 2)
cd backend
pip install -r requirements.txt
python main.py
```

Open **http://localhost:3000**

### Proxy (if Binance is blocked)

If you're in a region where `fstream.binance.com` is blocked, set a proxy:

**Windows CMD:**
```cmd
set HTTPS_PROXY=socks5://127.0.0.1:1080
python main.py
```

**PowerShell:**
```powershell
$env:HTTPS_PROXY="socks5://127.0.0.1:1080"
python main.py
```

**Or use the startup script:**
```cmd
REM Edit start.bat, uncomment the HTTPS_PROXY line, then:
start.bat
```

**Common proxy ports:**
| App           | SOCKS5 Port | HTTP Port |
|---------------|-------------|-----------|
| Clash         | 7891        | 7890      |
| V2Ray         | 10808       | 10809     |
| Shadowsocks   | 1080        | —         |

For SOCKS5 proxies, also install: `pip install python-socks[asyncio]`

---

## Architecture

```
┌─────────────────────┐     WebSocket      ┌──────────────────┐
│   Binance Futures    │ ◄────────────────── │   MANTIS Backend  │
│   WebSocket API      │   (aggTrade,       │   Python/FastAPI  │
│   (no API key)       │    depth, kline)    │   :8000           │
└─────────────────────┘                     └────────┬─────────┘
                                                     │ WebSocket
                                                     ▼
                                            ┌──────────────────┐
                                            │  MANTIS Frontend  │
                                            │  React + Vite     │
                                            │  :3000            │
                                            └──────────────────┘
```

## What's Included (Phase 1)

- **Live candlestick chart** with large trade markers
- **Flow metrics** — taker buy/sell, delta, cumulative delta, imbalance, trade frequency
- **Bubble tape** — large trades (≥0.5 BTC) with size-scaled colored bubbles
- **Order book heatmap** — bid/ask liquidity with wall detection (Canvas)
- **Footprint chart** — volume clusters per price level per 1m candle (Canvas)
- **Absorption detection** — high volume + near-zero delta at a price level
- **Session stats** — VWAP, session high/low
- **Auto-reconnect** WebSocket to Binance
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
| Data     | Binance Futures WebSocket (free, no key)|

## File Structure

```
backend/
  main.py           — FastAPI app, WebSocket server
  binance_ws.py     — Binance WS client (with proxy support)
  metrics.py        — Microstructure engine
  config.py         — Configuration
  requirements.txt  — Python dependencies
  start.bat         — Windows startup script
frontend/
  App.jsx           — Main layout
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

## License

MIT
