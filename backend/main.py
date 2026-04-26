"""
BTCUSDT Microstructure Dashboard — FastAPI backend.
Connects to Binance Futures WebSocket streams and broadcasts
processed microstructure data to frontend via WebSocket.
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from binance_ws import BinanceStreamManager
from metrics import MicrostructureEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- State ---
engine = MicrostructureEngine()
stream_mgr = BinanceStreamManager()
connected_clients: set[WebSocket] = set()


async def broadcast(message: dict):
    """Send a message to all connected frontend clients."""
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


# --- Binance stream handlers ---

def on_agg_trade(data: dict):
    """Handle incoming aggTrade event."""
    bubble = engine.process_trade(data)
    if bubble:
        asyncio.ensure_future(broadcast({"type": "large_trade", "data": bubble}))


def on_depth(data: dict):
    engine.process_depth(data)


# --- Periodic broadcast task ---

async def metrics_broadcaster():
    """Broadcast flow metrics and heatmap every 250ms."""
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
    # Register handlers
    stream_mgr.on("aggTrade", on_agg_trade)
    stream_mgr.on("depthUpdate", on_depth)

    # Start Binance streams
    stream_task = asyncio.create_task(stream_mgr.start())
    # Start broadcaster
    broadcast_task = asyncio.create_task(metrics_broadcaster())

    logger.info("Microstructure engine started")
    yield

    broadcast_task.cancel()
    stream_task.cancel()
    await stream_mgr.stop()


# --- App ---

app = FastAPI(title="BTC Microstructure Dashboard", lifespan=lifespan)

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
        # Send initial state
        await ws.send_text(json.dumps({
            "type": "init",
            "data": {
                "flow": engine.get_flow_metrics(),
                "heatmap": engine.get_heatmap_data(),
                "footprints": engine.get_footprints(),
                "large_trades": engine.get_large_trades(),
                "absorption": engine.get_absorption_zones(),
            }
        }))

        # Keep connection alive, listen for client messages
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
        "clients": len(connected_clients),
        "trade_count": engine.flow.trade_count,
        "uptime": time.time() - engine._session_start,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
