"""
Binance Futures WebSocket streams for BTCUSDT microstructure data.
Uses the subscribe method on a single connection for reliability.
"""

import asyncio
import json
import logging
from typing import Callable
import websockets

logger = logging.getLogger(__name__)

BINANCE_WS_URL = "wss://fstream.binance.com/ws"


class BinanceStreamManager:
    """Manages Binance Futures WebSocket streams on a single connection."""

    SYMBOL = "btcusdt"
    STREAMS = [
        f"{SYMBOL}@aggTrade",
        f"{SYMBOL}@depth@100ms",
        f"{SYMBOL}@kline_1m",
        f"{SYMBOL}@kline_5m",
    ]

    def __init__(self):
        self._callbacks: dict[str, list[Callable]] = {}
        self._running = False
        self._reconnect_delay = 1.0

    def on(self, event_type: str, callback: Callable):
        """Register a callback for an event type (e.g. 'aggTrade', 'depthUpdate')."""
        self._callbacks.setdefault(event_type, []).append(callback)

    async def _dispatch(self, event_type: str, data: dict):
        for cb in self._callbacks.get(event_type, []):
            try:
                result = cb(data)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Callback error on {event_type}: {e}")

    async def start(self):
        """Connect and subscribe to all streams with auto-reconnect."""
        self._running = True
        while self._running:
            try:
                async with websockets.connect(
                    BINANCE_WS_URL,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    # Subscribe to all streams
                    sub_msg = {
                        "method": "SUBSCRIBE",
                        "params": self.STREAMS,
                        "id": 1,
                    }
                    await ws.send(json.dumps(sub_msg))
                    logger.info(f"Subscribed to {len(self.STREAMS)} streams")
                    self._reconnect_delay = 1.0

                    async for msg in ws:
                        try:
                            data = json.loads(msg)
                            # Combined stream: {"stream": "...", "data": {...}}
                            if "stream" in data and "data" in data:
                                payload = data["data"]
                                event = payload.get("e", "")
                                if event:
                                    await self._dispatch(event, payload)
                            # Subscription response: {"result": null, "id": 1}
                            elif "result" in data:
                                logger.info(f"Subscription confirmed")
                            # Direct event
                            elif "e" in data:
                                await self._dispatch(data["e"], data)
                        except json.JSONDecodeError:
                            continue

            except Exception as e:
                logger.warning(f"Connection lost: {e}")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 30)

    async def stop(self):
        self._running = False
