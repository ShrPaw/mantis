"""MANTIS Execution Engine — Core Manager.

Orchestrates: connectors → features → detectors → scoring → alerts → logging.
Single tick loop that processes all incoming data and produces state classification.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from pathlib import Path

import yaml

from .models import (
    MarketState, ExecutionMode, EngineEvent,
    CrowdBuildupState, LiquidationCascadeState, UnwindState,
    ExhaustionAbsorptionState, Scores,
)
from .connectors.hyperliquid import HyperliquidConnector
from .connectors.binance import BinanceConnector
from .features import FeaturePipeline
from .detectors import (
    CrowdBuildupDetector, LiquidationCascadeDetector,
    UnwindDetector, ExhaustionAbsorptionDetector,
)
from .scoring import ScoringEngine
from .alerts import AlertManager
from .logger import EventLogger

logger = logging.getLogger("mantis.engine")


class MantisEngine:
    """Core engine that orchestrates all components."""

    def __init__(self, config_path: str = "config/mantis_execution_config.yaml"):
        # Load config
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        # Components
        self.features = FeaturePipeline(self.config)
        self.detectors = {
            "crowd": CrowdBuildupDetector(self.config.get("detectors", {})),
            "cascade": LiquidationCascadeDetector(self.config.get("detectors", {})),
            "unwind": UnwindDetector(self.config.get("detectors", {})),
            "exhaustion": ExhaustionAbsorptionDetector(self.config.get("detectors", {})),
        }
        self.scoring = ScoringEngine(self.config)
        self.alerts = AlertManager(self.config)
        self.event_logger = EventLogger(self.config)

        # Connectors
        self._connectors = []
        self._setup_connectors()

        # State
        self._running = False
        self._last_event: EngineEvent | None = None
        self._tick_interval = 0.25  # 250ms tick
        self._event_count = 0
        self._price_history: deque[float] = deque(maxlen=10000)
        self._start_time = 0.0

    def _setup_connectors(self):
        """Initialize exchange connectors based on config."""
        ex_cfg = self.config.get("exchanges", {})

        hl = ex_cfg.get("hyperliquid", {})
        if hl.get("enabled", True):
            conn = HyperliquidConnector(
                ws_url=hl.get("ws_url", "wss://api.hyperliquid.xyz/ws"),
                rest_url=hl.get("rest_url", "https://api.hyperliquid.xyz"),
            )
            conn.on("trade", self._on_trade)
            conn.on("book", self._on_book)
            conn.on("funding", self._on_funding)
            conn.on("open_interest", self._on_oi)
            conn.on("candle", self._on_candle)
            self._connectors.append(conn)

        bn = ex_cfg.get("binance", {})
        if bn.get("enabled", True):
            conn = BinanceConnector(
                ws_url=bn.get("ws_url", "wss://fstream.binance.com/ws"),
                rest_url=bn.get("rest_url", "https://fapi.binance.com"),
            )
            conn.on("funding", self._on_funding)
            conn.on("open_interest", self._on_oi)
            conn.on("liquidation", self._on_liquidation)
            self._connectors.append(conn)

    # ── Data Handlers ──────────────────────────────────────────────────

    async def _on_trade(self, trade):
        self.features.on_trade(trade)
        self._price_history.append(trade.price)

    async def _on_book(self, book):
        self.features.on_book(book)

    async def _on_funding(self, funding):
        self.features.on_funding(funding)

    async def _on_oi(self, oi):
        self.features.on_open_interest(oi)

    async def _on_liquidation(self, liq):
        self.features.on_liquidation(liq)

    async def _on_candle(self, candle):
        self.features.on_candle(candle)

    # ── Main Loop ──────────────────────────────────────────────────────

    async def run(self):
        """Start the engine. Runs connectors + tick loop."""
        self._running = True
        self._start_time = time.time()
        logger.info("MANTIS Engine starting...")

        # Start connectors
        connector_tasks = [asyncio.create_task(c.run()) for c in self._connectors]

        # Start tick loop
        tick_task = asyncio.create_task(self._tick_loop())

        logger.info(f"MANTIS Engine running. {len(self._connectors)} connectors active.")

        try:
            await asyncio.gather(*connector_tasks, tick_task)
        except asyncio.CancelledError:
            logger.info("MANTIS Engine shutting down...")
        finally:
            await self.stop()

    async def _tick_loop(self):
        """Main processing loop — runs every tick_interval seconds."""
        while self._running:
            try:
                await self._process_tick()
            except Exception as e:
                logger.error(f"Tick error: {e}", exc_info=True)
            await asyncio.sleep(self._tick_interval)

    async def _process_tick(self):
        """Process one tick: compute features → detect → score → alert → log."""
        # 1. Compute all features
        feat = self.features.compute_all()

        # 2. Run detectors
        crowd = self.detectors["crowd"].detect(
            feat["funding"], feat["oi"], feat["trade_flow"],
            feat["last_price"], self._price_history,
        )
        cascade = self.detectors["cascade"].detect(
            feat["liquidation"], feat["trade_flow"],
            feat["last_price"], self._price_history,
        )
        unwind = self.detectors["unwind"].detect(
            feat["funding"], feat["oi"],
            feat["last_price"], self._price_history,
        )
        exhaustion = self.detectors["exhaustion"].detect(
            feat["trade_flow"], feat["liquidation"],
            feat["last_price"], self._price_history,
            feat["order_book"],
        )

        # 3. Determine market state
        market_state = self._classify_state(crowd, cascade, unwind, exhaustion)

        # 4. Compute scores
        scores = self.scoring.score(
            feat["funding"], feat["oi"], feat["liquidation"],
            feat["trade_flow"], feat["order_book"], feat["execution_quality"],
        )

        # 5. Determine execution mode
        execution_mode = self._determine_execution_mode(scores, cascade, exhaustion)

        # 6. Check for alerts
        alert = self.alerts.check(
            scores, market_state, crowd, cascade, unwind, exhaustion, execution_mode,
        )

        # 7. Build engine event
        event = EngineEvent(
            timestamp=time.time(),
            market_state=market_state,
            crowd=crowd,
            cascade=cascade,
            unwind=unwind,
            exhaustion=exhaustion,
            scores=scores,
            execution_mode=execution_mode,
            alert=alert,
            funding=feat["funding"],
            oi=feat["oi"],
            liquidation=feat["liquidation"],
            trade_flow=feat["trade_flow"],
            order_book=feat["order_book"],
        )

        # 8. Log event
        self.event_logger.log_event(event)
        self.event_logger.save_metrics_snapshot(event)

        if alert:
            self.event_logger.log_alert(alert)
            self._print_alert(alert)

        self._last_event = event
        self._event_count += 1

    def _classify_state(self, crowd: CrowdBuildupState,
                        cascade: LiquidationCascadeState,
                        unwind: UnwindState,
                        exhaustion: ExhaustionAbsorptionState) -> MarketState:
        """Determine the dominant market state. Priority: cascade > exhaustion > unwind > crowd."""
        if cascade.active:
            return MarketState.LIQUIDATION_CASCADE
        if exhaustion.active:
            return MarketState.EXHAUSTION_ABSORPTION
        if unwind.active:
            return MarketState.UNWIND
        if crowd.active:
            return MarketState.CROWD_BUILDUP
        return MarketState.IDLE

    def _determine_execution_mode(self, scores: Scores,
                                   cascade: LiquidationCascadeState,
                                   exhaustion: ExhaustionAbsorptionState) -> ExecutionMode:
        """Determine recommended execution mode."""
        hostile = self.config.get("execution", {}).get("hostile_threshold", 39)
        caution = self.config.get("execution", {}).get("caution_threshold", 69)

        # NO_TRADE if hostile
        if scores.execution_quality < hostile:
            return ExecutionMode.NO_TRADE

        # NO_TRADE if cascade and not confirmed continuation
        if cascade.active and cascade.intensity > 80:
            return ExecutionMode.NO_TRADE

        # WAIT if exhaustion
        if exhaustion.active:
            return ExecutionMode.WAIT

        # WAIT if elevated spread but strong imbalance
        if scores.imbalance > 60 and scores.execution_quality < 60:
            return ExecutionMode.WAIT

        # MAKER_ONLY if market calm and decent execution
        if scores.execution_quality >= 70 and scores.risk < 50:
            return ExecutionMode.MAKER_ONLY

        # TAKER_ALLOWED if cascade with confirmed continuation
        if cascade.active and cascade.intensity < 80:
            return ExecutionMode.TAKER_ALLOWED

        # REDUCE_SIZE if risk elevated
        if scores.risk > 60:
            return ExecutionMode.REDUCE_SIZE

        return ExecutionMode.MAKER_ONLY

    def _print_alert(self, alert):
        """Print alert to console."""
        tier_label = {1: "WATCH", 2: "ACTIONABLE", 3: "DANGER"}.get(alert.tier, "?")
        print(f"\n{'='*60}")
        print(f"  TIER {alert.tier} — {tier_label}")
        print(f"  STATE: {alert.state}")
        print(f"  SIDE: {alert.side}")
        print(f"  SEVERITY: {alert.severity:.0f}")
        print(f"  EXECUTION: {alert.execution_recommendation}")
        print(f"  REASON: {alert.reason}")
        print(f"  DO NOT: {alert.do_not}")
        print(f"{'='*60}\n")

    async def stop(self):
        """Stop the engine."""
        self._running = False
        for conn in self._connectors:
            await conn.stop()
        logger.info(f"MANTIS Engine stopped. {self._event_count} events processed.")

    def get_status(self) -> dict:
        """Get current engine status."""
        uptime = time.time() - self._start_time if self._start_time else 0
        return {
            "running": self._running,
            "uptime_seconds": uptime,
            "event_count": self._event_count,
            "connectors": [c.name for c in self._connectors],
            "last_state": self._last_event.market_state.value if self._last_event else "UNKNOWN",
            "last_scores": {
                "imbalance": self._last_event.scores.imbalance if self._last_event else 0,
                "execution_quality": self._last_event.scores.execution_quality if self._last_event else 0,
                "risk": self._last_event.scores.risk if self._last_event else 0,
                "trade_environment": self._last_event.scores.trade_environment if self._last_event else 0,
            } if self._last_event else {},
        }
