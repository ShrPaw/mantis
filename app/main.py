"""
MANTIS — BTCUSDT Microstructure Dashboard (Hyperliquid)
Real-time decision-support for intraday BTC trading.

Data source: Hyperliquid DEX (decentralized, no API key, no blocks)

Event Engine: additive layer, feature-flagged. If disabled or failing,
MANTIS continues to work exactly as before.
"""

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.services.engine import MicrostructureEngine
from app.services.stream import HyperliquidStreamManager
from app.services.event_manager import create_event_manager
from app.api.routes import create_routes
from app.api.ws import websocket_endpoint as ws_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Shared state ---
engine = MicrostructureEngine()
stream_mgr = HyperliquidStreamManager()
event_mgr = create_event_manager()
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


async def fetch_historical_candles(limit: int = 1000):
    """Fetch last N 1m candles from Hyperliquid REST API.

    Default 1000 candles (~16.7 hours of 1m data).
    Hyperliquid returns max 5000 per request.
    """
    global _candle_cache
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (limit * 60 * 1000)

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
                timeout=15,
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
# Original behavior preserved exactly. Event Engine hooks are additive
# and wrapped in try/except — failures never affect the core pipeline.

def on_trade(trade: dict):
    """Original trade handler — unchanged behavior."""
    bubble = engine.process_trade({
        "p": trade["px"],
        "q": trade["sz"],
        "m": trade["side"] == "A",
        "T": trade["time"],
        "a": trade["tid"],
    })
    if bubble:
        asyncio.ensure_future(broadcast({"type": "large_trade", "data": bubble}))

    # --- Instant price push (every trade, lightweight) ---
    price = float(trade["px"])
    ts = trade["time"]
    asyncio.ensure_future(broadcast({
        "type": "latest_price",
        "data": {
            "price": price,
            "timestamp": ts,
            "side": trade["side"],
            "qty": float(trade["sz"]),
        },
    }))

    # --- Event Engine hook (additive, non-breaking) ---
    if event_mgr is not None:
        try:
            if bubble:
                event_mgr.on_large_trade(
                    price=bubble["price"], qty=bubble["qty"],
                    side=bubble["side"], timestamp=bubble["timestamp"],
                )

            price = float(trade["px"])
            qty = float(trade["sz"])
            is_seller_aggressive = trade["side"] == "A"
            delta = -qty if is_seller_aggressive else qty
            ts = trade["time"] / 1000.0

            event_mgr.on_session_update(
                vwap=engine.flow.vwap,
                session_high=engine.flow.session_high,
                session_low=engine.flow.session_low if engine.flow.session_low != float("inf") else 0,
            )

            detected = event_mgr.on_trade(price, qty, delta, ts)
            if detected:
                # Separate SPE events from regular events
                spe_events = [d for d in detected if isinstance(d, dict) and d.get("event_type") == "structural_pressure_execution"]
                regular_events = [d for d in detected if not (isinstance(d, dict) and d.get("event_type") == "structural_pressure_execution")]

                if regular_events:
                    asyncio.ensure_future(broadcast({"type": "event_detected", "data": regular_events}))
                if spe_events:
                    asyncio.ensure_future(broadcast({"type": "spe_detected", "data": spe_events}))
        except Exception as e:
            logger.debug(f"Event Engine error (non-fatal): {e}")


def on_book(book: dict):
    """Original book handler — unchanged behavior."""
    bids = []
    asks = []
    levels = book.get("levels", [])
    if len(levels) >= 1:
        bids = [(l["px"], l["sz"]) for l in levels[0]]
    if len(levels) >= 2:
        asks = [(l["px"], l["sz"]) for l in levels[1]]
    engine.process_depth({"b": bids, "a": asks})

    # --- Event Engine hook (additive, non-breaking) ---
    if event_mgr is not None:
        try:
            if bids and asks:
                float_bids = [(float(p), float(q)) for p, q in bids]
                float_asks = [(float(p), float(q)) for p, q in asks]
                event_mgr.on_book(float_bids, float_asks)
        except Exception as e:
            logger.debug(f"Event Engine book error (non-fatal): {e}")


def on_candle(candle: dict):
    """Original candle handler — unchanged."""
    engine.process_candle(candle)


# --- Periodic broadcaster ---

async def metrics_broadcaster():
    """Broadcasts core metrics every 250ms. Event stats only when engine is active."""
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
            # Event stats — only when engine is active
            if event_mgr is not None:
                try:
                    await broadcast({
                        "type": "event_stats",
                        "data": event_mgr.get_event_stats(),
                    })
                except Exception:
                    pass

                # SPE stats broadcast (observation-only)
                if event_mgr.spe is not None:
                    try:
                        spe_layer = event_mgr.get_spe_layer_stats()
                        await broadcast({
                            "type": "spe_stats",
                            "data": {
                                **event_mgr.spe.get_stats(),
                                "observation_only": event_mgr.spe_observation_only,
                                "raw_evaluations": spe_layer.get("raw_evaluations", 0),
                                "full_8_layer_passes": spe_layer.get("full_8_layer_passes", 0),
                                "emitted_events": spe_layer.get("emitted_events", 0),
                                "suppressed_duplicates": spe_layer.get("suppressed_duplicates", 0),
                                "cooldown_hits": spe_layer.get("cooldown_hits", 0),
                            },
                        })
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Broadcast error: {e}")


# --- Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load historical candles (1000 1m candles ≈ 16.7h of context)
    await fetch_historical_candles(limit=1000)

    stream_mgr.on("trades", on_trade)
    stream_mgr.on("l2Book", on_book)
    stream_mgr.on("candle", on_candle)

    stream_task = asyncio.create_task(stream_mgr.start())
    broadcast_task = asyncio.create_task(metrics_broadcaster())

    if event_mgr is not None:
        logger.info("MANTIS engine started (Hyperliquid) — Event Engine Pro: ACTIVE")
    else:
        logger.info("MANTIS engine started (Hyperliquid) — Event Engine: OFF")
    yield

    # Shutdown: flush event logger
    if event_mgr is not None:
        try:
            event_mgr.flush()
        except Exception:
            pass

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

# Register REST routes
api_router = create_routes(engine, event_mgr, _candle_cache, connected_clients)
app.include_router(api_router)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_handler(ws, connected_clients, engine, event_mgr, _candle_cache)
