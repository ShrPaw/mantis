"""
MANTIS — WebSocket endpoint handler.

Manages WebSocket connections, sends init payload, and handles ping/pong.
"""

import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


async def websocket_endpoint(
    ws: WebSocket,
    connected_clients: set,
    engine,
    event_mgr,
    candle_cache: list,
):
    """
    WebSocket endpoint: /ws

    Sends initial state on connect, then handles ping/pong.
    Clients are tracked in connected_clients set.
    """
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
            "candles": candle_cache,
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
