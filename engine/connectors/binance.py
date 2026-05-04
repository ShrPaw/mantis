"""Binance Futures WebSocket connector.

Streams: funding rate, open interest, liquidations, mark price.
Used as reference data source alongside Hyperliquid.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

import websockets
import httpx

from engine.connectors import BaseConnector
from engine.models import FundingRate, OpenInterest, Liquidation

logger = logging.getLogger("mantis.connector.binance")


class BinanceConnector(BaseConnector):
    """Binance Futures connector for funding, OI, and liquidations."""

    def __init__(self, ws_url: str = "wss://fstream.binance.com/ws",
                 rest_url: str = "https://fapi.binance.com"):
        super().__init__("binance", ws_url, rest_url)
        self._last_rest_fetch = 0.0
        self._rest_interval = 30  # fetch OI/funding every 30s via REST

    async def connect(self):
        # Binance combined stream
        streams = "btcusdt@markPrice@1s/btcusdt@forceOrder"
        url = f"{self.ws_url}/{streams}"
        self._ws = await websockets.connect(url, ping_interval=20, ping_timeout=10)

    async def subscribe(self):
        """Binance subscriptions are done via URL path for combined streams."""
        pass  # Subscriptions handled in connect()

    async def _handle_message(self, raw: str):
        msg = json.loads(raw)
        event = msg.get("e")

        if event == "markPriceUpdate":
            await self._handle_mark_price(msg)
        elif event == "forceOrder":
            await self._handle_liquidation(msg)

        # Periodically fetch funding + OI via REST
        now = time.time()
        if now - self._last_rest_fetch > self._rest_interval:
            self._last_rest_fetch = now
            asyncio.create_task(self._fetch_rest_data())

    async def _handle_mark_price(self, msg: dict):
        """Handle mark price update (includes funding rate)."""
        funding = FundingRate(
            timestamp=float(msg.get("E", 0)) / 1000,
            rate=float(msg.get("r", 0)),
            exchange="binance",
            mark_price=float(msg.get("p", 0)),
            index_price=float(msg.get("i", 0)),
        )
        await self._emit("funding", funding)

    async def _handle_liquidation(self, msg: dict):
        """Handle forced order (liquidation) event."""
        order = msg.get("o", {})
        side = "long" if order.get("S") == "SELL" else "short"  # SELL = long liquidated
        price = float(order.get("p", 0))
        qty = float(order.get("q", 0))

        liq = Liquidation(
            timestamp=float(order.get("T", 0)) / 1000,
            side=side,
            qty=qty,
            price=price,
            notional_usd=price * qty,
            exchange="binance",
        )
        await self._emit("liquidation", liq)

    async def _fetch_rest_data(self):
        """Fetch funding rate and open interest via REST API."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Funding rate history
                resp = await client.get(
                    f"{self.rest_url}/fapi/v1/fundingRate",
                    params={"symbol": "BTCUSDT", "limit": 1},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        fr = data[-1]
                        funding = FundingRate(
                            timestamp=float(fr.get("fundingTime", 0)) / 1000,
                            rate=float(fr.get("fundingRate", 0)),
                            exchange="binance",
                        )
                        await self._emit("funding", funding)

                # Open interest
                resp = await client.get(
                    f"{self.rest_url}/fapi/v1/openInterest",
                    params={"symbol": "BTCUSDT"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    oi = OpenInterest(
                        timestamp=time.time(),
                        oi=float(data.get("openInterest", 0)),
                        exchange="binance",
                    )
                    await self._emit("open_interest", oi)

        except Exception as e:
            logger.warning(f"[binance] REST fetch failed: {e}")
