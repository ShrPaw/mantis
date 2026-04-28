"""Exchange connector base class."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Callable, Any

logger = logging.getLogger("mantis.connector")


class BaseConnector(ABC):
    """Base class for exchange WebSocket connectors."""

    def __init__(self, name: str, ws_url: str, rest_url: str):
        self.name = name
        self.ws_url = ws_url
        self.rest_url = rest_url
        self._running = False
        self._ws = None
        self._callbacks: dict[str, list[Callable]] = {}
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0

    def on(self, event_type: str, callback: Callable):
        """Register callback for event type."""
        self._callbacks.setdefault(event_type, []).append(callback)

    async def _emit(self, event_type: str, data: Any):
        """Emit event to registered callbacks."""
        for cb in self._callbacks.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(data)
                else:
                    cb(data)
            except Exception as e:
                logger.error(f"[{self.name}] Callback error for {event_type}: {e}")

    @abstractmethod
    async def connect(self):
        """Establish WebSocket connection."""
        ...

    @abstractmethod
    async def subscribe(self):
        """Subscribe to data streams."""
        ...

    @abstractmethod
    async def _handle_message(self, raw: str):
        """Parse and dispatch a raw WebSocket message."""
        ...

    async def run(self):
        """Main loop with auto-reconnect."""
        self._running = True
        delay = self._reconnect_delay
        while self._running:
            try:
                logger.info(f"[{self.name}] Connecting to {self.ws_url}")
                await self.connect()
                await self.subscribe()
                delay = self._reconnect_delay
                logger.info(f"[{self.name}] Connected and subscribed")
                async for message in self._ws:
                    if not self._running:
                        break
                    try:
                        await self._handle_message(message)
                    except Exception as e:
                        logger.error(f"[{self.name}] Message handling error: {e}")
            except Exception as e:
                if not self._running:
                    break
                logger.warning(f"[{self.name}] Connection lost: {e}. Reconnecting in {delay:.1f}s")
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._max_reconnect_delay)

    async def stop(self):
        """Stop the connector."""
        self._running = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
