"""MANTIS Execution Engine — Four Market State Detectors.

Each detector is independent and produces a state output.
No detector generates trade signals — only context classification.
"""

from __future__ import annotations

import logging
import time
from collections import deque

from ..models import (
    CrowdBuildupState, LiquidationCascadeState, UnwindState,
    ExhaustionAbsorptionState, FundingFeatures, OIFeatures,
    LiquidationFeatures, TradeFlowFeatures, OrderBookFeatures,
)

logger = logging.getLogger("mantis.detectors")


class CrowdBuildupDetector:
    """Detects crowd positioning pressure building up.

    Long crowd: funding extreme positive + OI rising + price not moving
    Short crowd: funding extreme negative + OI rising + price not moving
    """

    def __init__(self, config: dict):
        self.cfg = config.get("crowd_buildup", {})
        self._funding_z_thresh = self.cfg.get("funding_z_threshold", 2.0)
        self._oi_pct_thresh = self.cfg.get("oi_percentile_threshold", 0.80)
        self._price_stall_bps = self.cfg.get("price_stall_bps", 10)
        self._last_state = CrowdBuildupState()

    def detect(self, funding: FundingFeatures, oi: OIFeatures,
               flow: TradeFlowFeatures, price: float,
               price_history: deque) -> CrowdBuildupState:
        state = CrowdBuildupState()

        # Long crowd buildup
        if (funding.positive_extreme and
            oi.strong_rise and
            self._price_is_stalling(price, price_history)):
            state.active = True
            state.crowd_side = "LONGS"
            state.severity = self._compute_severity(funding, oi, "long")
            state.trade_signal = False
            state.message = f"Crowd fuel building (LONGS). Funding z={funding.z_score:.1f}, OI +p{oi.percentile*100:.0f}. No entry yet."

        # Short crowd buildup
        elif (funding.negative_extreme and
              oi.strong_rise and
              self._price_is_stalling(price, price_history)):
            state.active = True
            state.crowd_side = "SHORTS"
            state.severity = self._compute_severity(funding, oi, "short")
            state.trade_signal = False
            state.message = f"Crowd fuel building (SHORTS). Funding z={funding.z_score:.1f}, OI +p{oi.percentile*100:.0f}. No entry yet."

        self._last_state = state
        return state

    def _price_is_stalling(self, price: float, history: deque) -> bool:
        """Check if price hasn't moved significantly despite OI build-up."""
        if len(history) < 10:
            return False
        recent = list(history)[-60:]  # last 60 ticks
        if not recent:
            return False
        price_range = max(recent) - min(recent)
        if price <= 0:
            return False
        stall_bps = price_range / price * 10000
        return stall_bps <= self._price_stall_bps

    def _compute_severity(self, funding: FundingFeatures, oi: OIFeatures, side: str) -> float:
        """Compute severity score 0-100."""
        # Combine funding z-score and OI percentile
        funding_component = min(1.0, abs(funding.z_score) / 4.0) * 50
        oi_component = oi.percentile * 30
        persistence_component = funding.persistence * 20
        return min(100, funding_component + oi_component + persistence_component)


class LiquidationCascadeDetector:
    """Detects violent forced-position unwinds.

    Cascade = extreme liquidation notional + price displacement + volume spike
    """

    def __init__(self, config: dict):
        self.cfg = config.get("liquidation_cascade", {})
        self._notional_pct = self.cfg.get("notional_percentile", 0.95)
        self._price_return_pct = self.cfg.get("price_return_percentile", 0.90)
        self._volume_pct = self.cfg.get("volume_percentile", 0.90)

    def detect(self, liq: LiquidationFeatures, flow: TradeFlowFeatures,
               price: float, price_history: deque) -> LiquidationCascadeState:
        state = LiquidationCascadeState()

        if not liq.cascade_active:
            return state

        # Check price displacement
        price_return = self._compute_price_return_1m(price, price_history)

        # Check volume spike
        volume_spike = flow.volume_spike

        if liq.cascade_active and volume_spike:
            state.active = True
            state.cascade_direction = liq.cascade_direction
            state.intensity = self._compute_intensity(liq, flow, price_return)
            state.execution_mode = "DANGER"
            state.message = (
                f"Forced liquidation active. Direction: {state.cascade_direction}. "
                f"Intensity: {state.intensity:.0f}. Avoid chasing unless continuation confirmed."
            )

        return state

    def _compute_price_return_1m(self, price: float, history: deque) -> float:
        """Compute 1-minute price return in bps."""
        if len(history) < 10 or price <= 0:
            return 0.0
        recent = list(history)[-60:]  # ~60 ticks = 1 min at 1/sec
        if not recent:
            return 0.0
        old_price = recent[0]
        if old_price <= 0:
            return 0.0
        return (price - old_price) / old_price * 10000

    def _compute_intensity(self, liq: LiquidationFeatures,
                           flow: TradeFlowFeatures, price_return: float) -> float:
        """Compute cascade intensity 0-100."""
        liq_component = min(1.0, liq.notional_z / 4.0) * 40 if liq.notional_z > 0 else 0
        price_component = min(1.0, abs(price_return) / 50) * 30
        volume_component = min(1.0, flow.delta_z / 4.0) * 30 if flow.delta_z > 0 else 0
        return min(100, liq_component + price_component + volume_component)


class UnwindDetector:
    """Detects structured release of crowd pressure.

    Unwind = funding extreme + OI falling + price moving against crowd
    """

    def __init__(self, config: dict):
        self.cfg = config.get("unwind", {})
        self._funding_z_thresh = self.cfg.get("funding_z_threshold", 2.0)
        self._oi_fall_window = self.cfg.get("oi_fall_window_minutes", 15) * 60
        self._price_move_bps = self.cfg.get("price_move_bps", 5)

    def detect(self, funding: FundingFeatures, oi: OIFeatures,
               price: float, price_history: deque) -> UnwindState:
        state = UnwindState()

        # Long unwind: longs were crowded, now exiting
        if (funding.positive_extreme and
            oi.change_15m < 0 and
            self._price_moving_down(price, price_history)):
            state.active = True
            state.unwind_side = "LONGS_EXITING"
            state.direction = "DOWN"
            state.maturity = self._classify_maturity(oi)
            state.message = f"Positioning unwind active (LONGS_EXITING). Direction: DOWN. Maturity: {state.maturity}."

        # Short unwind: shorts were crowded, now exiting
        elif (funding.negative_extreme and
              oi.change_15m < 0 and
              self._price_moving_up(price, price_history)):
            state.active = True
            state.unwind_side = "SHORTS_EXITING"
            state.direction = "UP"
            state.maturity = self._classify_maturity(oi)
            state.message = f"Positioning unwind active (SHORTS_EXITING). Direction: UP. Maturity: {state.maturity}."

        return state

    def _price_moving_down(self, price: float, history: deque) -> bool:
        if len(history) < 10 or price <= 0:
            return False
        recent = list(history)[-60:]
        if not recent:
            return False
        old_price = recent[0]
        if old_price <= 0:
            return False
        return (price - old_price) / old_price * 10000 <= -self._price_move_bps

    def _price_moving_up(self, price: float, history: deque) -> bool:
        if len(history) < 10 or price <= 0:
            return False
        recent = list(history)[-60:]
        if not recent:
            return False
        old_price = recent[0]
        if old_price <= 0:
            return False
        return (price - old_price) / old_price * 10000 >= self._price_move_bps

    def _classify_maturity(self, oi: OIFeatures) -> str:
        """Classify unwind maturity based on OI decline rate."""
        if oi.change_15m < -5:
            return "LATE"
        elif oi.change_15m < -2:
            return "MID"
        else:
            return "EARLY"


class ExhaustionAbsorptionDetector:
    """Detects when aggressive flow appears but price no longer follows.

    Exhaustion = strong pressure + liquidation cluster + limited new extreme
                 + delta extreme + follow-through failure
    """

    def __init__(self, config: dict):
        self.cfg = config.get("exhaustion", {})
        self._follow_through_bps = self.cfg.get("follow_through_bps", 5)
        self._follow_through_bars = self.cfg.get("follow_through_bars", 3)
        self._delta_z_extreme = self.cfg.get("delta_z_extreme", 2.0)
        self._vol_cluster_pct = self.cfg.get("volume_cluster_percentile", 0.90)

        # Track recent price extremes for follow-through check
        self._recent_highs: deque[float] = deque(maxlen=100)
        self._recent_lows: deque[float] = deque(maxlen=100)
        self._spike_prices: deque[tuple[float, float]] = deque(maxlen=50)  # (ts, price_at_spike)

    def detect(self, flow: TradeFlowFeatures, liq: LiquidationFeatures,
               price: float, price_history: deque,
               book: OrderBookFeatures) -> ExhaustionAbsorptionState:
        state = ExhaustionAbsorptionState()

        # Update extremes
        if price > 0:
            self._recent_highs.append(price)
            self._recent_lows.append(price)

        # Sell exhaustion
        if (flow.strong_sell and
            liq.cluster_detected and
            self._limited_new_low(price, price_history) and
            flow.delta_z <= -self._delta_z_extreme):

            # Check follow-through failure
            if self._check_follow_through_failure(price, "sell", price_history):
                state.active = True
                state.side = "SELL_EXHAUSTION"
                state.confidence = self._compute_confidence(flow, liq, book)
                state.trade_signal = False
                state.message = (
                    "Aggression failing (SELL). Watch for reversal. Do not auto-enter."
                )

        # Buy exhaustion
        elif (flow.strong_buy and
              liq.cluster_detected and
              self._limited_new_high(price, price_history) and
              flow.delta_z >= self._delta_z_extreme):

            if self._check_follow_through_failure(price, "buy", price_history):
                state.active = True
                state.side = "BUY_EXHAUSTION"
                state.confidence = self._compute_confidence(flow, liq, book)
                state.trade_signal = False
                state.message = (
                    "Aggression failing (BUY). Watch for reversal. Do not auto-enter."
                )

        return state

    def _limited_new_low(self, price: float, history: deque) -> bool:
        """Price makes a limited new low (not a crash)."""
        if len(history) < 30 or price <= 0:
            return False
        recent = list(history)[-180:]  # 3 min window
        if not recent:
            return False
        local_low = min(recent)
        # Limited = new low within 10 bps of recent low
        if local_low <= 0:
            return False
        return price <= local_low * 1.001  # within 10 bps

    def _limited_new_high(self, price: float, history: deque) -> bool:
        """Price makes a limited new high (not a breakout)."""
        if len(history) < 30 or price <= 0:
            return False
        recent = list(history)[-180:]
        if not recent:
            return False
        local_high = max(recent)
        if local_high <= 0:
            return False
        return price >= local_high * 0.999  # within 10 bps

    def _check_follow_through_failure(self, price: float, side: str,
                                       history: deque) -> bool:
        """Check if price failed to extend by follow_through_bps in follow_through_bars minutes."""
        # Store spike price for later checking
        now = time.time()
        self._spike_prices.append((now, price))

        if len(self._spike_prices) < 2:
            return False

        # Check if a spike from ~N minutes ago failed to extend
        window_sec = self._follow_through_bars * 60
        for ts, spike_price in list(self._spike_prices):
            if now - ts >= window_sec:
                price_change_bps = abs(price - spike_price) / spike_price * 10000 if spike_price > 0 else 0
                if price_change_bps < self._follow_through_bps:
                    return True  # Follow-through failure
                self._spike_prices.remove((ts, spike_price))

        return False

    def _compute_confidence(self, flow: TradeFlowFeatures,
                            liq: LiquidationFeatures,
                            book: OrderBookFeatures) -> float:
        """Compute exhaustion confidence 0-100."""
        delta_component = min(1.0, abs(flow.delta_z) / 4.0) * 35
        liq_component = 25 if liq.cluster_detected else 0
        book_component = (1 - abs(book.book_imbalance)) * 20  # balanced book = absorption
        flow_component = min(1.0, abs(flow.buy_pressure - 0.5) * 4) * 20
        return min(100, delta_component + liq_component + book_component + flow_component)
