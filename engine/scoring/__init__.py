"""MANTIS Execution Engine — Scoring System.

Four independent scores:
1. Imbalance Score — how abnormal positioning/flow is
2. Execution Quality Score — how safe it is to execute
3. Risk Score — how dangerous the environment is
4. Trade Environment Score — composite classifier

NOT buy/sell signals. Environment classification only.
"""

from __future__ import annotations

import logging
import math
from collections import deque

from engine.models import (
    Scores, FundingFeatures, OIFeatures, LiquidationFeatures,
    TradeFlowFeatures, OrderBookFeatures, ExecutionQualityFeatures,
)

logger = logging.getLogger("mantis.scoring")


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _z_to_score(z: float, max_z: float = 4.0) -> float:
    """Convert z-score to 0-100 scale. Higher |z| = higher score."""
    return _clamp(abs(z) / max_z * 100)


class ScoringEngine:
    """Computes all four scores from feature snapshots."""

    def __init__(self, config: dict):
        self.cfg = config.get("scoring", {})
        self._imb_weights = self.cfg.get("imbalance", {}).get("weights", {})
        self._exec_weights = self.cfg.get("execution_quality", {}).get("weights", {})
        self._risk_weights = self.cfg.get("risk", {}).get("weights", {})
        self._env_weights = self.cfg.get("trade_environment", {})

    def score(self, funding: FundingFeatures, oi: OIFeatures,
              liq: LiquidationFeatures, flow: TradeFlowFeatures,
              book: OrderBookFeatures, exec_q: ExecutionQualityFeatures) -> Scores:
        """Compute all four scores."""
        s = Scores()
        s.imbalance = self._score_imbalance(funding, oi, liq, flow)
        s.execution_quality = self._score_execution_quality(exec_q, book, liq)
        s.risk = self._score_risk(book, liq, oi, exec_q)
        s.trade_environment = self._score_trade_environment(s)
        return s

    def _score_imbalance(self, funding: FundingFeatures, oi: OIFeatures,
                         liq: LiquidationFeatures, flow: TradeFlowFeatures) -> float:
        """Score how abnormal the current positioning/flow is (0-100)."""
        w = self._imb_weights

        funding_component = _z_to_score(funding.z_score) * w.get("funding_z", 0.25)
        oi_component = _z_to_score(oi.z_score) * w.get("oi_z", 0.25)
        liq_component = _z_to_score(liq.notional_z) * w.get("liquidation_z", 0.20)
        volume_component = _z_to_score(flow.delta_z) * w.get("volume_z", 0.15)
        delta_component = _z_to_score(flow.delta_z) * w.get("delta_z", 0.15)

        raw = funding_component + oi_component + liq_component + volume_component + delta_component
        return _clamp(raw)

    def _score_execution_quality(self, exec_q: ExecutionQualityFeatures,
                                 book: OrderBookFeatures,
                                 liq: LiquidationFeatures) -> float:
        """Score execution safety (0-100). Higher = safer."""
        w = self._exec_weights

        # Spread component: lower spread = higher score
        spread_score = max(0, 100 - exec_q.spread_bps * 25) * w.get("spread", 0.25)

        # Depth component: more depth = higher score
        depth_score = min(100, exec_q.available_depth_usd / 100000 * 100) * w.get("depth", 0.25)

        # Slippage component: lower slippage = higher score
        slip_score = max(0, 100 - exec_q.expected_slippage_bps * 20) * w.get("slippage", 0.20)

        # Volatility component: no burst = higher score
        vol_score = (50 if exec_q.volatility_burst else 100) * w.get("volatility", 0.15)

        # Book stability: stable = higher score
        book_score = (100 if exec_q.book_stable else 40) * w.get("book_stability", 0.15)

        raw = spread_score + depth_score + slip_score + vol_score + book_score
        return _clamp(raw)

    def _score_risk(self, book: OrderBookFeatures, liq: LiquidationFeatures,
                    oi: OIFeatures, exec_q: ExecutionQualityFeatures) -> float:
        """Score environment risk (0-100). Higher = more dangerous."""
        w = self._risk_weights

        # Volatility: burst = high risk
        vol_risk = (80 if exec_q.volatility_burst else 20) * w.get("volatility", 0.25)

        # Spread: wide = high risk
        spread_risk = min(100, exec_q.spread_bps * 50) * w.get("spread", 0.20)

        # Liquidation intensity
        liq_risk = min(100, liq.notional_z * 25) if liq.notional_z > 0 else 0
        liq_risk *= w.get("liquidation_intensity", 0.25)

        # OI instability
        oi_risk = min(100, abs(oi.acceleration) * 10) * w.get("oi_instability", 0.15)

        # Book thinning
        thin_risk = (80 if book.liquidity_thinning else 10) * w.get("book_thinning", 0.15)

        raw = vol_risk + spread_risk + liq_risk + oi_risk + thin_risk
        return _clamp(raw)

    def _score_trade_environment(self, scores: Scores) -> float:
        """Composite trade environment score.

        >= 75 = favorable
        60-74 = watchlist
        40-59 = poor
        < 40 = avoid
        """
        w = self._env_weights
        imbalance_w = w.get("imbalance_weight", 0.40)
        exec_w = w.get("execution_quality_weight", 0.35)
        risk_w = w.get("risk_weight", 0.25)

        raw = (scores.imbalance * imbalance_w +
               scores.execution_quality * exec_w -
               scores.risk * risk_w)

        return _clamp(raw)
