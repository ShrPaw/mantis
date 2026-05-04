"""
Hyperliquid WebSocket client for BTCUSDT microstructure data.
Connects to Hyperliquid DEX for trades, order book, and candles.

No API key needed. Decentralized — won't be blocked.
"""

import asyncio
import json
import logging
import time
from typing import Callable
import websockets

logger = logging.getLogger(__name__)

HYPERLIQUID_WS_URL = "wss://api.hyperliquid.xyz/ws"


class HyperliquidStreamManager:
    """Manages Hyperliquid WebSocket streams for BTC microstructure data."""

    COIN = "BTC"

    def __init__(self):
        self._callbacks: dict[str, list[Callable]] = {}
        self._running = False
        self._reconnect_delay = 1.0

    def on(self, event_type: str, callback: Callable):
        """Register a callback for an event type (e.g. 'trades', 'l2Book', 'candle')."""
        self._callbacks.setdefault(event_type, []).append(callback)

    async def _dispatch(self, event_type: str, data):
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
                    HYPERLIQUID_WS_URL,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    # Subscribe to trades
                    await ws.send(json.dumps({
                        "method": "subscribe",
                        "subscription": {"type": "trades", "coin": self.COIN}
                    }))
                    logger.info(f"Subscribed to {self.COIN} trades")

                    # Subscribe to l2 order book
                    await ws.send(json.dumps({
                        "method": "subscribe",
                        "subscription": {"type": "l2Book", "coin": self.COIN}
                    }))
                    logger.info(f"Subscribed to {self.COIN} l2Book")

                    # Subscribe to 1m candles
                    await ws.send(json.dumps({
                        "method": "subscribe",
                        "subscription": {"type": "candle", "coin": self.COIN, "interval": "1m"}
                    }))
                    logger.info(f"Subscribed to {self.COIN} candle 1m")

                    self._reconnect_delay = 1.0

                    async for msg in ws:
                        try:
                            data = json.loads(msg)
                            channel = data.get("channel", "")

                            if channel == "trades":
                                # data["data"] is a list of trades
                                for trade in data.get("data", []):
                                    await self._dispatch("trades", trade)

                            elif channel == "l2Book":
                                await self._dispatch("l2Book", data.get("data", {}))

                            elif channel == "candle":
                                await self._dispatch("candle", data.get("data", {}))

                            elif channel == "subscriptionResponse":
                                logger.info(f"Subscription confirmed: {data.get('data', {}).get('subscription', {}).get('type', '?')}")

                        except json.JSONDecodeError:
                            continue

            except Exception as e:
                logger.warning(f"Connection lost: {e}")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 30)

    async def stop(self):
        self._running = False
