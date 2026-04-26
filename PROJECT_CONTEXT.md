# MANTIS Project — Full Context for Next Session

## What This Is
MANTIS is a real-time BTC microstructure dashboard for Hyperliquid DEX. It visualizes aggressive buying/selling, liquidity walls, trade intensity, delta imbalance, large player activity — purely decision-support, NO signals/predictions.

## Repository
- GitHub: https://github.com/ShrPaw/mantis

## Architecture
```
Hyperliquid DEX (wss://api.hyperliquid.xyz/ws)
  ↓ WebSocket (trades, l2Book, candle 1m)
Backend: Python/FastAPI on :8000
  ↓ WebSocket /ws
Frontend: React/TypeScript/Vite on :3000
```

## File Structure (source files only)
```
backend/
  main.py              — FastAPI app, WS server, broadcasts metrics every 250ms
  hyperliquid_ws.py    — Hyperliquid WS client, auto-reconnect, 3 streams
  metrics.py           — MicrostructureEngine: delta, footprint, absorption, large trades
  requirements.txt     — fastapi, uvicorn, websockets, httpx

frontend/src/
  types.ts             — All TypeScript interfaces
  store.ts             — Zustand store, computes microstructure analysis (delta imbalance, absorption, liquidity pulls, breakout)
  hooks/useWebSocket.ts — WS connection, auto-reconnect, 15s ping, dispatches to store
  services/format.ts   — Number/time formatting (formatPrice, formatVol, formatDelta, formatPct, formatUSD, timeAgo)
  styles/theme.ts      — Color constants (teal #26a69a green, #ef5350 red, #f0b90b gold)
  styles/global.css    — Dark theme, scrollbar, animations
  App.tsx              — 4-column flex layout: left(230) | center(flex) | right(300) | far-right(220)
  components/
    PriceChart.tsx     — lightweight-charts candlestick + VWAP line + large trade markers
    FlowPanel.tsx      — Order flow metrics (taker buy/sell, delta, cum delta, imbalance, VWAP)
    Heatmap.tsx        — Canvas order book heatmap with wall detection
    BubbleTape.tsx     — Large trades (≥0.5 BTC) with size-scaled bubbles
    TradeTape.tsx      — Live trade table
    Footprint.tsx      — Canvas volume clusters per price level per candle
    MicroPanel.tsx     — Delta imbalance, absorption zones, liquidity pulls, breakout
    SessionContext.tsx  — Asia/London/NY sessions, UTC clock, range
    NewsPanel.tsx      — Macro events (FOMC, CPI, NFP) with countdown
    StatusBar.tsx      — Header bar with live metrics
```

## Backend WebSocket Message Types (DO NOT MODIFY BACKEND)
The backend sends these via the single `/ws` endpoint:
- `init` → full initial state: `{flow, heatmap, footprints, large_trades, absorption, candles}`
- `flow_metrics` → every 250ms: `{taker_buy_vol, taker_sell_vol, delta, cum_delta, trade_count, trade_frequency, imbalance, vwap, last_price, session_high, session_low}`
- `heatmap` → every 250ms: `{bids: [{price, qty}], asks: [{price, qty}], mid}`
- `footprints` → every 250ms: array of candle footprints with price levels
- `absorption` → every 250ms: absorption zones
- `large_trade` → on each large trade: `{price, qty, side, timestamp, value_usd}`
- `pong` → keepalive response

## Data Format
- Timestamps: Unix seconds (not milliseconds)
- Prices: float (e.g., 78064.00)
- Quantities: float in BTC
- Side: "buy" (aggressive buyer) or "sell" (aggressive seller)
- Hyperliquid convention: `is_buyer_maker=true` means seller is aggressive (taker sell)

## Key Design Decisions
1. Backend is UNTOUCHED — all changes are frontend-only
2. TradingView-style color palette: teal #26a69a (bull), #ef5350 (bear), gold #f0b90b (VWAP/accents)
3. Zustand for state management (not Redux)
4. Canvas for heatmap/footprint (performance), lightweight-charts for price
5. Single `/ws` endpoint (not multiple), all data via one connection
6. No signals, no predictions, no RSI/MACD — raw microstructure only
7. Layout: 4 horizontal flex columns, tuned for 1920×1080

## Git History (5 commits on main)
```
01f06bb improve: usability pass — visual clarity, legends, README
cfa8747 fix: layout using flex columns instead of broken CSS grid
890ab0b feat: complete microstructure dashboard rebuild
7e5a0c7 feat: historical candles, visual polish, Hyperliquid as default
c95dbd4 feat: switch to Hyperliquid DEX — no blocks, no proxy, no API key
```

## How to Run
```bash
cd mantis/backend && pip install -r requirements.txt
cd mantis/frontend && npm install
bash mantis/start.sh
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

## Verified Working (all 12 checks pass)
- Backend starts, connects to Hyperliquid, loads 101 historical candles
- Frontend builds with zero TypeScript errors
- WebSocket connects, data flows at ~4 trades/sec
- All panels render: chart, heatmap, bubbles, tape, flow, micro, sessions, news
- Zero console errors

## Current State
MVP is complete and verified. Dashboard shows live BTC microstructure data from Hyperliquid DEX with all panels functional. Next steps could include: additional data sources, persistent session tracking, alerts, or mobile responsiveness.
