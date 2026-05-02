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
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from hyperliquid_ws import HyperliquidStreamManager
from metrics import MicrostructureEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# Feature flag: set EVENT_ENGINE_ENABLED=false to disable
# ============================================================
EVENT_ENGINE_ENABLED = os.environ.get("EVENT_ENGINE_ENABLED", "true").lower() in ("true", "1", "yes")

# Lazy-load event engine — never crash MANTIS if it fails
event_mgr = None
if EVENT_ENGINE_ENABLED:
    try:
        from event_engine import EventManager
        event_mgr = EventManager()
        logger.info("Event Engine Pro: ENABLED")
    except Exception as e:
        logger.warning(f"Event Engine Pro: FAILED TO LOAD — {e}. MANTIS continues without it.")
        event_mgr = None
else:
    logger.info("Event Engine Pro: DISABLED (EVENT_ENGINE_ENABLED=false)")

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


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.add(ws)
    logger.info(f"Client connected ({len(connected_clients)} total)")
    try:
        # Init payload — original fields always present, event fields conditional
        init_data = {
            "flow": engine.get_flow_metrics(),
            "heatmap": engine.get_heatmap_data(),
            "footprints": engine.get_footprints(),
            "large_trades": engine.get_large_trades(),
            "absorption": engine.get_absorption_zones(),
            "candles": _candle_cache,
        }
        # Add event data only if engine is active
        if event_mgr is not None:
            try:
                init_data["events"] = event_mgr.get_events(limit=50)
                init_data["event_stats"] = event_mgr.get_event_stats()
            except Exception:
                init_data["events"] = []
                init_data["event_stats"] = {}

            # Add SPE data if available
            if event_mgr.spe is not None:
                try:
                    init_data["spe_events"] = event_mgr.get_spe_events(limit=50)
                    spe_layer = event_mgr.get_spe_layer_stats()
                    init_data["spe_stats"] = {
                        **event_mgr.spe.get_stats(),
                        "observation_only": event_mgr.spe_observation_only,
                        "raw_evaluations": spe_layer.get("raw_evaluations", 0),
                        "full_8_layer_passes": spe_layer.get("full_8_layer_passes", 0),
                        "emitted_events": spe_layer.get("emitted_events", 0),
                        "suppressed_duplicates": spe_layer.get("suppressed_duplicates", 0),
                        "cooldown_hits": spe_layer.get("cooldown_hits", 0),
                    }
                except Exception:
                    init_data["spe_events"] = []
                    init_data["spe_stats"] = {}

        await ws.send_text(json.dumps({"type": "init", "data": init_data}))

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
    """Health endpoint — event fields only when engine is active."""
    result = {
        "status": "ok",
        "source": "hyperliquid",
        "clients": len(connected_clients),
        "trade_count": engine.flow.trade_count,
        "candles_loaded": len(_candle_cache),
        "uptime": time.time() - engine._session_start,
        "event_engine": "active" if event_mgr is not None else "disabled",
    }
    if event_mgr is not None:
        try:
            stats = event_mgr.get_event_stats()
            result["events_total"] = stats["total"]
            result["events_fired"] = stats["fired"]
            result["events_deduped"] = stats["deduped"]
            result["pending_outcomes"] = stats["pending_outcomes"]
        except Exception:
            result["event_engine"] = "error"

        # SPE status
        if event_mgr.spe is not None:
            result["spe"] = "active"
            result["spe_observation_only"] = event_mgr.spe_observation_only
            try:
                spe_stats = event_mgr.spe.get_stats()
                result["spe_evaluations"] = spe_stats["signals_evaluated"]
                result["spe_events"] = spe_stats["events_emitted"]
            except Exception:
                pass
        else:
            result["spe"] = "disabled" if event_mgr.spe_enabled else "not_loaded"
    return result


@app.get("/events/export")
async def events_export():
    """
    Export all events with current forward outcomes to JSONL.
    This is the file the validation script should read — it includes
    outcome data that the initial JSONL snapshot does not.
    """
    if event_mgr is None:
        return {"status": "event_engine_disabled"}

    try:
        events = event_mgr.get_events(limit=1000)
        export_path = "data/events/events_with_outcomes.jsonl"
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        with open(export_path, "w") as f:
            for evt in events:
                f.write(json.dumps(evt) + "\n")
        return {"status": "ok", "exported": len(events), "path": export_path}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/events")
async def events_list(limit: int = 20):
    """Return recent events as JSON (for debugging)."""
    if event_mgr is None:
        return {"events": [], "stats": {}}
    try:
        return {
            "events": event_mgr.get_events(limit=limit),
            "stats": event_mgr.get_event_stats(),
        }
    except Exception:
        return {"events": [], "stats": {}}


@app.get("/spe/events")
async def spe_events_list(limit: int = 20):
    """Return recent SPE events as JSON (observation-only)."""
    if event_mgr is None or event_mgr.spe is None:
        return {"spe_events": [], "spe_stats": {}}
    try:
        spe_layer = event_mgr.get_spe_layer_stats()
        return {
            "spe_events": event_mgr.get_spe_events(limit=limit),
            "spe_stats": {
                **event_mgr.spe.get_stats(),
                "observation_only": event_mgr.spe_observation_only,
                "raw_evaluations": spe_layer.get("raw_evaluations", 0),
                "full_8_layer_passes": spe_layer.get("full_8_layer_passes", 0),
                "emitted_events": spe_layer.get("emitted_events", 0),
                "suppressed_duplicates": spe_layer.get("suppressed_duplicates", 0),
                "cooldown_hits": spe_layer.get("cooldown_hits", 0),
            },
        }
    except Exception:
        return {"spe_events": [], "spe_stats": {}}


@app.get("/spe/layers")
async def spe_layer_stats():
    """Return SPE layer pass/fail statistics."""
    if event_mgr is None or event_mgr.spe is None:
        return {"layer_stats": {}}
    try:
        return {"layer_stats": event_mgr.get_spe_layer_stats()}
    except Exception:
        return {"layer_stats": {}}


@app.get("/spe/metrics")
async def spe_metrics():
    """Return SPE metrics (flushed to disk)."""
    if event_mgr is None:
        return {"status": "event_engine_disabled"}
    try:
        event_mgr.flush_spe_metrics()
        import json as _json
        with open("data/metrics/spe_metrics.json") as f:
            data = _json.load(f)
        # Include accounting validation
        if event_mgr.spe is not None:
            validation = event_mgr.spe.validate_layer_accounting()
            data["accounting_valid"] = validation["accounting_valid"]
            data["accounting_errors"] = validation["accounting_errors"]
        return data
    except Exception:
        return {"status": "no_data"}


@app.get("/market/candles")
async def market_candles(limit: int = 500):
    """Read-only endpoint: return recent 1m candles for chart display.

    No mutation. No trading. No logic changes.
    Returns: time, open, high, low, close, volume
    """
    if limit < 1:
        limit = 1
    if limit > 5000:
        limit = 5000
    return _candle_cache[-limit:]


@app.get("/l3/calibration")
async def l3_calibration():
    """
    L3 1m displacement shadow diagnostic.
    Returns production L3 status + 5 shadow variant evaluations.
    Does NOT modify production SPE. Observation-only.
    ALWAYS returns status:ok with all required fields.
    """
    if event_mgr is None:
        return _l3_safe_fallback("event_engine_disabled")
    if event_mgr.l3_calibrator is None:
        return _l3_safe_fallback("l3_calibrator_not_loaded")
    try:
        result = event_mgr.l3_calibrator.evaluate()
        # Ensure status field exists (calibrator always returns it, but be safe)
        if "status" not in result:
            result["status"] = "ok"
        return result
    except Exception as e:
        logger.error(f"L3 calibration error: {e}", exc_info=True)
        return _l3_safe_fallback(f"endpoint_error: {e}")


def _l3_safe_fallback(reason: str) -> dict:
    """Guaranteed-safe fallback for /l3/calibration."""
    return {
        "status": "ok",
        "production_l3_status": "NOT_EVALUATED",
        "production_l3_block_reason": reason,
        "shadow_3c_pass": False,
        "shadow_stress_pass": False,
        "shadow_single_candle_pass": False,
        "shadow_5c_pass": False,
        "metrics": {
            "body_bps": None,
            "range_bps": None,
            "close_to_close_bps": None,
            "leg_3c_bps": None,
            "leg_5c_bps": None,
            "directional_efficiency_3c": None,
            "directional_efficiency_5c": None,
            "pullback_ratio": None,
            "max_extension_bps": None,
            "volume_percentile": None,
            "volatility_percentile": None,
        },
        "interpretation": reason,
        "ready": False,
        "candles_evaluated": 0,
        "percentile_ranks": {},
        "percentile_thresholds": {},
    }


@app.get("/operator/status")
async def operator_status():
    """
    Read-only operator dashboard endpoint.
    Combines health, SPE metrics, and observation logger status.
    No execution. No mutation. Purely informational.
    """
    import glob as _glob

    result = {
        "timestamp": time.time(),
        "backend": {
            "status": "ok",
            "source": "hyperliquid",
            "uptime": time.time() - engine._session_start,
            "trade_count": engine.flow.trade_count,
            "candles_loaded": len(_candle_cache),
            "clients": len(connected_clients),
        },
        "market": {
            "last_price": engine.flow.last_price,
            "vwap": engine.flow.vwap,
            "session_high": engine.flow.session_high,
            "session_low": engine.flow.session_low if engine.flow.session_low != float("inf") else 0,
            "delta": engine.flow.delta,
            "cum_delta": engine.flow.cum_delta,
            "taker_buy_vol": engine.flow.taker_buy_vol,
            "taker_sell_vol": engine.flow.taker_sell_vol,
            "trade_frequency": engine.flow.trade_frequency,
            "imbalance": engine.flow.imbalance,
        },
        "event_engine": {
            "enabled": event_mgr is not None,
            "status": "active" if event_mgr is not None else "disabled",
        },
        "spe": {
            "enabled": False,
            "observation_only": True,
            "current_state": "IDLE",
            "raw_evaluations": 0,
            "full_8_layer_passes": 0,
            "emitted_events": 0,
            "accounting_valid": True,
            "accounting_errors": [],
            "layer_counts": {},
        },
        "observation_logger": {
            "detected": False,
            "health_file": None,
            "metrics_file": None,
            "events_file": None,
            "summary_file": None,
            "last_health_ts": None,
            "last_metrics_ts": None,
            "last_event_ts": None,
            "unique_events": 0,
            "accounting_violations": 0,
            "observation_only_violations": 0,
        },
    }

    # Event engine stats
    if event_mgr is not None:
        try:
            stats = event_mgr.get_event_stats()
            result["event_engine"]["total"] = stats.get("total", 0)
            result["event_engine"]["fired"] = stats.get("fired", 0)
            result["event_engine"]["deduped"] = stats.get("deduped", 0)
            result["event_engine"]["pending_outcomes"] = stats.get("pending_outcomes", 0)
            result["event_engine"]["watchlisted"] = stats.get("watchlisted", 0)
            result["event_engine"]["blacklisted"] = stats.get("blacklisted", 0)
        except Exception:
            pass

        # SPE details
        if event_mgr.spe is not None:
            try:
                spe_stats = event_mgr.spe.get_stats()
                spe_layer = event_mgr.get_spe_layer_stats()
                result["spe"]["enabled"] = True
                result["spe"]["observation_only"] = event_mgr.spe_observation_only
                result["spe"]["current_state"] = spe_stats.get("state", "IDLE")
                result["spe"]["raw_evaluations"] = spe_layer.get("raw_evaluations", 0)
                result["spe"]["full_8_layer_passes"] = spe_layer.get("full_8_layer_passes", 0)
                result["spe"]["emitted_events"] = spe_layer.get("emitted_events", 0)
                result["spe"]["accounting_valid"] = spe_layer.get("accounting_valid", True)
                result["spe"]["accounting_errors"] = spe_layer.get("accounting_errors", [])
                result["spe"]["layer_counts"] = spe_layer.get("layer_pass_fail", {})
            except Exception:
                pass

    # Observation logger status (check if files exist)
    obs_dir = os.path.join(os.path.dirname(__file__), "..", "data", "observation")
    obs_files = {
        "health_file": os.path.join(obs_dir, "short_stress_health.jsonl"),
        "metrics_file": os.path.join(obs_dir, "short_stress_metrics.jsonl"),
        "events_file": os.path.join(obs_dir, "short_stress_events.jsonl"),
        "summary_file": os.path.join(obs_dir, "SHORT_STRESS_OBSERVATION_SESSION_SUMMARY.md"),
    }

    detected = False
    for key, fpath in obs_files.items():
        if os.path.exists(fpath):
            result["observation_logger"][key] = {
                "exists": True,
                "size": os.path.getsize(fpath),
                "modified": os.path.getmtime(fpath),
            }
            detected = True
        else:
            result["observation_logger"][key] = {"exists": False}

    result["observation_logger"]["detected"] = detected

    # Read last lines from observation files for timestamps
    for file_key, ts_key in [
        ("health_file", "last_health_ts"),
        ("metrics_file", "last_metrics_ts"),
        ("events_file", "last_event_ts"),
    ]:
        fpath_info = result["observation_logger"][file_key]
        if isinstance(fpath_info, dict) and fpath_info.get("exists"):
            try:
                with open(obs_files[file_key], "rb") as f:
                    # Seek to end, read last line
                    f.seek(0, 2)
                    fsize = f.tell()
                    if fsize > 0:
                        f.seek(max(0, fsize - 2048))
                        lines = f.read().decode("utf-8", errors="replace").strip().split("\n")
                        if lines:
                            last = json.loads(lines[-1])
                            result["observation_logger"][ts_key] = last.get("poll_ts") or last.get("log_ts")
            except Exception:
                pass

    # Count unique events in observation events file
    evt_fpath = obs_files["events_file"]
    if os.path.exists(evt_fpath):
        try:
            with open(evt_fpath, "r", encoding="utf-8") as f:
                result["observation_logger"]["unique_events"] = sum(1 for _ in f)
        except Exception:
            pass

    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
