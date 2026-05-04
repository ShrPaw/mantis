"""Hyperliquid DEX WebSocket connector.

Streams: trades, l2Book, candle, funding, open interest.
Hyperliquid provides transparent order flow with no API key.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

import websockets

from engine.connectors import BaseConnector
from engine.models import (
    Trade, OrderBook, BookLevel, Candle, FundingRate, OpenInterest,
)

logger = logging.getLogger("mantis.connector.hyperliquid")


class HyperliquidConnector(BaseConnector):
    """Hyperliquid WebSocket connector for trades, book, candles, funding, OI."""

    def __init__(self, ws_url: str = "wss://api.hyperliquid.xyz/ws",
                 rest_url: str = "https://api.hyperliquid.xyz"):
        super().__init__("hyperliquid", ws_url, rest_url)
        self._last_funding_fetch = 0.0
        self._funding_interval = 60  # fetch funding every 60s via REST

    async def connect(self):
        import websockets
        self._ws = await websockets.connect(
            self.ws_url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        )

    async def subscribe(self):
        """Subscribe to trades, l2Book, and 1m candles for BTC."""
        subs = [
            {"method": "subscribe", "subscription": {"type": "trades", "coin": "BTC"}},
            {"method": "subscribe", "subscription": {"type": "l2Book", "coin": "BTC"}},
            {"method": "subscribe", "subscription": {"type": "candle", "coin": "BTC", "interval": "1m"}},
        ]
        for sub in subs:
            await self._ws.send(json.dumps(sub))
            logger.debug(f"[hyperliquid] Subscribed: {sub['subscription']['type']}")

    async def _handle_message(self, raw: str):
        msg = json.loads(raw)
        channel = msg.get("channel")

        if channel == "trades":
            await self._handle_trades(msg.get("data", []))
        elif channel == "l2Book":
            await self._handle_book(msg.get("data", {}))
        elif channel == "candle":
            await self._handle_candle(msg.get("data", {}))
        elif channel == "subscriptionResponse":
            logger.debug(f"[hyperliquid] Sub response: {msg}")

        # Periodically fetch funding + OI via REST
        now = time.time()
        if now - self._last_funding_fetch > self._funding_interval:
            self._last_funding_fetch = now
            asyncio.create_task(self._fetch_funding_oi())

    async def _handle_trades(self, trades_data: list):
        for t in trades_data:
            # Hyperliquid: is_buyer_maker=true means seller is aggressive (taker sell)
            is_buyer_maker = t.get("px") and t.get("sz") and t.get("side")
            side_raw = t.get("side", "")
            # side field: "A" = aggressive buy, "B" = aggressive sell in newer API
            # or use is_buyer_maker boolean
            if isinstance(side_raw, str):
                is_aggressive_buy = side_raw == "A"
                is_aggressive_sell = side_raw == "B"
            else:
                is_aggressive_buy = not t.get("isBuyerMaker", False)
                is_aggressive_sell = t.get("isBuyerMaker", False)

            side = "buy" if is_aggressive_buy else "sell"
            price = float(t.get("px", 0))
            qty = float(t.get("sz", 0))
            ts = float(t.get("time", 0)) / 1000 if t.get("time", 0) > 1e12 else float(t.get("time", 0))

            trade = Trade(
                timestamp=ts,
                price=price,
                qty=qty,
                side=side,
                value_usd=price * qty,
                exchange="hyperliquid",
            )
            await self._emit("trade", trade)

    async def _handle_book(self, book_data: dict):
        levels = book_data.get("levels", [[], []])
        bids_raw = levels[0] if len(levels) > 0 else []
        asks_raw = levels[1] if len(levels) > 1 else []

        bids = [BookLevel(price=float(l.get("px", 0)), qty=float(l.get("sz", 0))) for l in bids_raw[:20]]
        asks = [BookLevel(price=float(l.get("px", 0)), qty=float(l.get("sz", 0))) for l in asks_raw[:20]]

        ts = time.time()
        book = OrderBook(timestamp=ts, bids=bids, asks=asks)
        await self._emit("book", book)

    async def _handle_candle(self, candle_data: dict):
        c = candle_data
        candle = Candle(
            timestamp=float(c.get("t", 0)) / 1000 if c.get("t", 0) > 1e12 else float(c.get("t", 0)),
            open=float(c.get("o", 0)),
            high=float(c.get("h", 0)),
            low=float(c.get("l", 0)),
            close=float(c.get("c", 0)),
            volume=float(c.get("v", 0)),
            interval="1m",
        )
        await self._emit("candle", candle)

    async def _fetch_funding_oi(self):
        """Fetch funding rate and open interest via Hyperliquid REST API."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                # Funding rate
                resp = await client.post(
                    f"{self.rest_url}/info",
                    json={"type": "metaAndAssetCtxs"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # data[0] = meta (universe), data[1] = asset contexts
                    if isinstance(data, list) and len(data) >= 2:
                        contexts = data[1]
                        if contexts:
                            ctx = contexts[0]  # BTC is first
                            funding = FundingRate(
                                timestamp=time.time(),
                                rate=float(ctx.get("funding", 0)),
                                exchange="hyperliquid",
                                mark_price=float(ctx.get("markPx", 0)),
                                index_price=float(ctx.get("oraclePx", 0)),
                            )
                            await self._emit("funding", funding)

                            oi = OpenInterest(
                                timestamp=time.time(),
                                oi=float(ctx.get("openInterest", 0)),
                                exchange="hyperliquid",
                            )
                            await self._emit("open_interest", oi)
        except Exception as e:
            logger.warning(f"[hyperliquid] Failed to fetch funding/OI: {e}")
