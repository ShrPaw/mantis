"""
MANTIS — BTCUSDT Microstructure Dashboard (Hyperliquid)
Real-time decision-support for intraday BTC trading.

Data source: Hyperliquid DEX (decentralized, no API key, no blocks)
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from hyperliquid_ws import HyperliquidStreamManager
from metrics import MicrostructureEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = MicrostructureEngine()
stream_mgr = HyperliquidStreamManager()
connected_clients: set[WebSocket] = set()

# Historical candle cache
_candle_cache: list[dict] = []


async def broadcast(message: dict):
    if not connected_clients:
        return
    payload = json.dumps(message)
    dead = set()
    for ws in connected_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    connected_clients.difference_update(dead)


async def fetch_historical_candles():
    """Fetch last 100 1m candles from Hyperliquid REST API."""
    global _candle_cache
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (100 * 60 * 1000)  # 100 minutes back

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.hyperliquid.xyz/info",
                json={
                    "type": "candleSnapshot",
                    "req": {
                        "coin": "BTC",
                        "interval": "1m",
                        "startTime": start_ms,
                        "endTime": now_ms,
                    }
                },
                timeout=10,
            )
            candles = resp.json()
            _candle_cache = [
                {
                    "time": c["t"] // 1000,  # Unix seconds
                    "open": float(c["o"]),
                    "high": float(c["h"]),
                    "low": float(c["l"]),
                    "close": float(c["c"]),
                    "volume": float(c["v"]),
                }
                for c in candles
            ]
            logger.info(f"Loaded {len(_candle_cache)} historical candles")
    except Exception as e:
        logger.warning(f"Failed to fetch historical candles: {e}")


# --- Hyperliquid stream handlers ---

def on_trade(trade: dict):
    bubble = engine.process_trade({
        "p": trade["px"],
        "q": trade["sz"],
        "m": trade["side"] == "A",
        "T": trade["time"],
        "a": trade["tid"],
    })
    if bubble:
        asyncio.ensure_future(broadcast({"type": "large_trade", "data": bubble}))


def on_book(book: dict):
    bids = []
    asks = []
    levels = book.get("levels", [])
    if len(levels) >= 1:
        bids = [(l["px"], l["sz"]) for l in levels[0]]
    if len(levels) >= 2:
        asks = [(l["px"], l["sz"]) for l in levels[1]]
    engine.process_depth({"b": bids, "a": asks})


def on_candle(candle: dict):
    engine.process_candle(candle)


# --- Periodic broadcaster ---

async def metrics_broadcaster():
    while True:
        await asyncio.sleep(0.25)
        try:
            await broadcast({
                "type": "flow_metrics",
                "data": engine.get_flow_metrics(),
            })
            await broadcast({
                "type": "heatmap",
                "data": engine.get_heatmap_data(depth_levels=25),
            })
            await broadcast({
                "type": "footprints",
                "data": engine.get_footprints(),
            })
            await broadcast({
                "type": "absorption",
                "data": engine.get_absorption_zones(),
            })
        except Exception as e:
            logger.error(f"Broadcast error: {e}")


# --- Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load historical candles
    await fetch_historical_candles()

    stream_mgr.on("trades", on_trade)
    stream_mgr.on("l2Book", on_book)
    stream_mgr.on("candle", on_candle)

    stream_task = asyncio.create_task(stream_mgr.start())
    broadcast_task = asyncio.create_task(metrics_broadcaster())

    logger.info("MANTIS engine started (Hyperliquid)")
    yield

    broadcast_task.cancel()
    stream_task.cancel()
    await stream_mgr.stop()


# --- App ---

app = FastAPI(title="MANTIS — BTC Microstructure", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.add(ws)
    logger.info(f"Client connected ({len(connected_clients)} total)")
    try:
        await ws.send_text(json.dumps({
            "type": "init",
            "data": {
                "flow": engine.get_flow_metrics(),
                "heatmap": engine.get_heatmap_data(),
                "footprints": engine.get_footprints(),
                "large_trades": engine.get_large_trades(),
                "absorption": engine.get_absorption_zones(),
                "candles": _candle_cache,
            }
        }))

        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.discard(ws)
        logger.info(f"Client disconnected ({len(connected_clients)} total)")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "source": "hyperliquid",
        "clients": len(connected_clients),
        "trade_count": engine.flow.trade_count,
        "candles_loaded": len(_candle_cache),
        "uptime": time.time() - engine._session_start,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
