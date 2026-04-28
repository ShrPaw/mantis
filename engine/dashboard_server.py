"""MANTIS Execution Engine — Dashboard WebSocket Server.

Serves real-time metrics to the frontend dashboard via WebSocket.
Reads from the metrics JSON snapshot and broadcasts to connected clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logger = logging.getLogger("mantis.dashboard")

app = FastAPI(title="MANTIS Execution Engine Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

METRICS_FILE = Path("data/metrics/realtime_metrics.json")
EVENTS_FILE = Path("data/events/mantis_events.jsonl")
ALERTS_FILE = Path("data/events/alerts.jsonl")

connected_clients: set[WebSocket] = set()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.add(ws)
    logger.info(f"Dashboard client connected. Total: {len(connected_clients)}")

    try:
        # Send current state immediately
        metrics = load_metrics()
        if metrics:
            await ws.send_json({"type": "metrics", "data": metrics})

        # Send recent events
        recent_events = load_recent_events(50)
        if recent_events:
            await ws.send_json({"type": "events", "data": recent_events})

        # Send recent alerts
        recent_alerts = load_recent_alerts(20)
        if recent_alerts:
            await ws.send_json({"type": "alerts", "data": recent_alerts})

        # Keep alive and broadcast updates
        last_sent = 0
        while True:
            await asyncio.sleep(0.5)
            now = time.time()
            if now - last_sent >= 1.0:  # send every 1 second
                metrics = load_metrics()
                if metrics:
                    await ws.send_json({"type": "metrics", "data": metrics})
                    last_sent = now

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        connected_clients.discard(ws)
        logger.info(f"Dashboard client disconnected. Total: {len(connected_clients)}")


def load_metrics() -> dict | None:
    """Load current metrics from JSON snapshot."""
    try:
        if METRICS_FILE.exists():
            with open(METRICS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return None


def load_recent_events(n: int = 50) -> list[dict]:
    """Load most recent events from JSONL."""
    events = []
    try:
        if EVENTS_FILE.exists():
            with open(EVENTS_FILE) as f:
                lines = f.readlines()
                for line in lines[-n:]:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
    except Exception:
        pass
    return events


def load_recent_alerts(n: int = 20) -> list[dict]:
    """Load most recent alerts from JSONL."""
    alerts = []
    try:
        if ALERTS_FILE.exists():
            with open(ALERTS_FILE) as f:
                lines = f.readlines()
                for line in lines[-n:]:
                    line = line.strip()
                    if line:
                        alerts.append(json.loads(line))
    except Exception:
        pass
    return alerts


@app.get("/health")
async def health():
    return {"status": "ok", "clients": len(connected_clients)}


@app.get("/api/metrics")
async def get_metrics():
    return load_metrics() or {}


@app.get("/api/events")
async def get_events(n: int = 100):
    return load_recent_events(n)


@app.get("/api/alerts")
async def get_alerts(n: int = 50):
    return load_recent_alerts(n)


def run_dashboard(host: str = "0.0.0.0", port: int = 8001):
    """Run the dashboard server."""
    uvicorn.run(app, host=host, log_level="info", port=port)


if __name__ == "__main__":
    run_dashboard()
