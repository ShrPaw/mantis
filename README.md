# MANTIS — BTC Microstructure Dashboard

Real-time decision-support dashboard for BTC/USD microstructure analysis.  
**NOT a bot. NOT signals. Raw data visualization only.**

Data source: [Hyperliquid](https://hyperliquid.xyz) DEX — decentralized, no API key, no blocks.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/ShrPaw/mantis.git
cd mantis

# 2. Install backend dependencies
cd backend
pip install -r requirements.txt
cd ..

# 3. Install frontend dependencies
cd frontend
npm install
cd ..

# 4. Start everything
bash start.sh
```

Open **http://localhost:3000** in your browser.

Backend health check: http://localhost:8000/health

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

---

## What Each Panel Means

### Header Bar
- **LIVE/OFFLINE** — WebSocket connection status
- **Price** — Last traded price
- **VWAP** — Volume-Weighted Average Price (session)
- **H/L** — Session high and low
- **Δ** — Delta (taker buy volume − taker sell volume)
- **ΣΔ** — Cumulative delta (running total since session start)
- **IMB** — Imbalance (buy−sell as % of total volume)

### Left Column — Order Flow
- **Taker Buy/Sell** — Aggressive volume on each side
- **Delta** — Net buying vs selling pressure (positive = buyers dominating)
- **Cum Delta** — Running sum of delta. Rising = sustained buying, falling = sustained selling
- **Imbalance** — How skewed the flow is. >0 = buy bias, <0 = sell bias
- **Trades** — Total trade count since session start
- **Freq** — Trades per second (activity level)
- **VWAP** — Volume-weighted average price. Price above VWAP = bullish context
- **Volume Split** — Visual bar showing buy vs sell percentage
- **Cumulative Delta** — Large number showing net direction

### Left Column — Microstructure
- **Delta Imbalance** — Whether buying or selling is dominating. Strength bar shows intensity
- **Absorption** — Price levels where high volume traded but price barely moved. Indicates someone absorbing orders
- **Liquidity Pulls** — Large order book walls that disappeared. May precede price moves
- **Breakout** — Whether price is at session extremes with volume confirmation

### Center — Price Chart
- **Candlesticks** — 1-minute OHLC candles. Green = bullish (close > open), Red = bearish
- **VWAP line** — Dashed gold line showing volume-weighted average
- **Arrows** — Large trade markers (≥0.5 BTC). Size indicates trade magnitude
- Scroll to zoom, drag to pan

### Center — Footprint
- **Volume clusters** — Shows how much volume traded at each price level within each candle
- **Green bars** — Bid-side volume (passive buying)
- **Red bars** — Ask-side volume (passive selling)
- **Δ** — Delta per candle (net direction)
- **Bordered levels** — Imbalance (one side dominating at that price)

### Center — Trade Tape
- Live feed of large trades (≥0.5 BTC)
- Shows time, side, price, size, and USD value

### Right — Order Book Heatmap
- **Green bars** — Bid liquidity (buy orders waiting)
- **Red bars** — Ask liquidity (sell orders waiting)
- **Bar length** — Relative size vs largest order
- **Glowing bars** — Walls (large orders, >40% of max)
- **Gold line** — Mid price (average of best bid/ask)
- **Spread** — Gap between best bid and ask

### Right — Large Trades
- **Bubble size** — Proportional to trade size (0.5 BTC → small, 5+ BTC → large)
- **Color** — Green = buy (aggressive), Red = sell (aggressive)
- **USD value** — Dollar value of the trade

### Far Right — Sessions
- **Asia/London/NY** — Current active session with UTC clock
- **Range** — Session high-low range

### Far Right — Macro Events
- Economic calendar with countdown timers
- **HIGH** badge = market-moving event (CPI, FOMC, NFP)
- ⚡ HIGH VOL warning when event is within 1 hour

---

## What This Is NOT

- ❌ **NOT a trading signal generator** — No buy/sell recommendations
- ❌ **NOT predictive** — Shows what IS happening, not what WILL happen
- ❌ **NOT an indicator platform** — No RSI, MACD, Bollinger Bands, etc.
- ❌ **NOT a bot** — No automated execution

## What This IS

- ✅ **Decision-support visualization** — See the data, make your own call
- ✅ **Microstructure context** — Understand if a price move has real flow behind it
- ✅ **Liquidity awareness** — See where the walls are, see when they vanish
- ✅ **Real-time** — Sub-second updates from live market data

---

## Configuration

In `backend/metrics.py`:
- `LARGE_TRADE_THRESHOLD = 0.5` — Minimum BTC to count as "large"
- `ROLLING_WINDOW = 300` — Seconds for trade frequency calculation
- `MAX_FOOTPRINT_CANDLES = 60` — Footprint candles kept in memory

---

## Tech Stack

| Layer    | Tech                                    |
|----------|-----------------------------------------|
| Backend  | Python, FastAPI, asyncio, websockets    |
| Frontend | React, TypeScript, Zustand, lightweight-charts, Canvas |
| Data     | Hyperliquid DEX (free, no key, no block)|

## License

MIT
