"""
MANTIS Event Engine Pro — Structural Market Event Detection

Detects measurable structural events from live order flow.
Every event answers: What happened? Where? Under what conditions?
What was the evidence? What happened afterward?

Event Types:
  1. Absorption — aggressive orders absorbed, price fails to continue
  2. Exhaustion — aggressive flow extreme, continuation weakens
  3. Liquidity Sweep — price sweeps high/low then fails/reverses
  4. Delta Divergence — price and CVD disagree
  5. Imbalance — aggressive directional order-flow imbalance
"""

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# Event Data Structures
# ============================================================

@dataclass
class ForwardOutcome:
    """Measured after event fires at 10s, 30s, 60s, 120s, 300s."""
    price_at_10s: float = 0.0
    price_at_30s: float = 0.0
    price_at_60s: float = 0.0
    price_at_120s: float = 0.0
    price_at_300s: float = 0.0
    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0
    pnl_at_10s_bps: float = 0.0
    pnl_at_30s_bps: float = 0.0
    pnl_at_60s_bps: float = 0.0
    pnl_at_120s_bps: float = 0.0
    pnl_at_300s_bps: float = 0.0
    fees_assumed_bps: float = 4.0  # 4 bps per side
    net_pnl_at_60s_bps: float = 0.0
    measured: bool = False


@dataclass
class AbsorptionEvent:
    event_type: str = "absorption"
    event_id: str = ""
    side: str = ""  # "buy_absorption" or "sell_absorption"
    timestamp: float = 0.0
    symbol: str = "BTC"
    price_level: float = 0.0
    window_seconds: int = 30
    aggressive_volume: float = 0.0
    signed_delta: float = 0.0
    price_change_after_aggression: float = 0.0
    max_adverse_excursion: float = 0.0
    max_favorable_excursion: float = 0.0
    absorption_strength_score: float = 0.0
    local_volume_percentile: float = 0.0
    delta_percentile: float = 0.0
    book_liquidity_context: float = 0.0
    vwap_distance: float = 0.0
    spread_context: float = 0.0
    regime_context: str = ""
    forward: ForwardOutcome = field(default_factory=ForwardOutcome)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "side": self.side,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "price_level": round(self.price_level, 2),
            "window_seconds": self.window_seconds,
            "aggressive_volume": round(self.aggressive_volume, 4),
            "signed_delta": round(self.signed_delta, 4),
            "price_change_after_aggression": round(self.price_change_after_aggression, 2),
            "max_adverse_excursion": round(self.max_adverse_excursion, 2),
            "max_favorable_excursion": round(self.max_favorable_excursion, 2),
            "absorption_strength_score": round(self.absorption_strength_score, 3),
            "local_volume_percentile": round(self.local_volume_percentile, 3),
            "delta_percentile": round(self.delta_percentile, 3),
            "book_liquidity_context": round(self.book_liquidity_context, 4),
            "vwap_distance": round(self.vwap_distance, 2),
            "spread_context": round(self.spread_context, 2),
            "regime_context": self.regime_context,
            "forward": _forward_to_dict(self.forward),
        }


@dataclass
class ExhaustionEvent:
    event_type: str = "exhaustion"
    event_id: str = ""
    side: str = ""  # "buy_exhaustion" or "sell_exhaustion"
    timestamp: float = 0.0
    price: float = 0.0
    aggressive_volume: float = 0.0
    delta: float = 0.0
    bubble_count: int = 0
    price_impact_per_volume: float = 0.0
    continuation_failure_score: float = 0.0
    local_extreme_context: str = ""
    cvd_divergence_context: float = 0.0
    exhaustion_strength_score: float = 0.0
    forward: ForwardOutcome = field(default_factory=ForwardOutcome)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "side": self.side,
            "timestamp": self.timestamp,
            "price": round(self.price, 2),
            "aggressive_volume": round(self.aggressive_volume, 4),
            "delta": round(self.delta, 4),
            "bubble_count": self.bubble_count,
            "price_impact_per_volume": round(self.price_impact_per_volume, 6),
            "continuation_failure_score": round(self.continuation_failure_score, 3),
            "local_extreme_context": self.local_extreme_context,
            "cvd_divergence_context": round(self.cvd_divergence_context, 3),
            "exhaustion_strength_score": round(self.exhaustion_strength_score, 3),
            "forward": _forward_to_dict(self.forward),
        }


@dataclass
class LiquiditySweepEvent:
    event_type: str = "liquidity_sweep"
    event_id: str = ""
    side: str = ""  # "high_sweep" or "low_sweep"
    timestamp: float = 0.0
    swept_level: float = 0.0
    sweep_distance: float = 0.0
    sweep_volume: float = 0.0
    sweep_delta: float = 0.0
    reclaim_status: bool = False
    reversal_confirmation: bool = False
    time_to_reclaim: float = 0.0
    sweep_strength_score: float = 0.0
    forward: ForwardOutcome = field(default_factory=ForwardOutcome)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "side": self.side,
            "timestamp": self.timestamp,
            "swept_level": round(self.swept_level, 2),
            "sweep_distance": round(self.sweep_distance, 2),
            "sweep_volume": round(self.sweep_volume, 4),
            "sweep_delta": round(self.sweep_delta, 4),
            "reclaim_status": self.reclaim_status,
            "reversal_confirmation": self.reversal_confirmation,
            "time_to_reclaim": round(self.time_to_reclaim, 1),
            "sweep_strength_score": round(self.sweep_strength_score, 3),
            "forward": _forward_to_dict(self.forward),
        }


@dataclass
class DeltaDivergenceEvent:
    event_type: str = "delta_divergence"
    event_id: str = ""
    side: str = ""  # "bearish_divergence" or "bullish_divergence"
    timestamp: float = 0.0
    price_structure: str = ""
    cvd_structure: str = ""
    divergence_window: int = 60
    divergence_strength_score: float = 0.0
    local_trend_context: str = ""
    price_at_detection: float = 0.0
    cvd_at_detection: float = 0.0
    forward: ForwardOutcome = field(default_factory=ForwardOutcome)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "side": self.side,
            "timestamp": self.timestamp,
            "price_structure": self.price_structure,
            "cvd_structure": self.cvd_structure,
            "divergence_window": self.divergence_window,
            "divergence_strength_score": round(self.divergence_strength_score, 3),
            "local_trend_context": self.local_trend_context,
            "price_at_detection": round(self.price_at_detection, 2),
            "cvd_at_detection": round(self.cvd_at_detection, 4),
            "forward": _forward_to_dict(self.forward),
        }


@dataclass
class ImbalanceEvent:
    event_type: str = "imbalance"
    event_id: str = ""
    side: str = ""  # "buy_imbalance" or "sell_imbalance"
    timestamp: float = 0.0
    volume_buy: float = 0.0
    volume_sell: float = 0.0
    delta: float = 0.0
    imbalance_ratio: float = 0.0
    price_response: float = 0.0
    continuation_score: float = 0.0
    failure_score: float = 0.0
    classification: str = ""  # "continuation", "absorption", "exhaustion"
    forward: ForwardOutcome = field(default_factory=ForwardOutcome)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "side": self.side,
            "timestamp": self.timestamp,
            "volume_buy": round(self.volume_buy, 4),
            "volume_sell": round(self.volume_sell, 4),
            "delta": round(self.delta, 4),
            "imbalance_ratio": round(self.imbalance_ratio, 3),
            "price_response": round(self.price_response, 2),
            "continuation_score": round(self.continuation_score, 3),
            "failure_score": round(self.failure_score, 3),
            "classification": self.classification,
            "forward": _forward_to_dict(self.forward),
        }


def _forward_to_dict(f: ForwardOutcome) -> dict:
        return {
            "price_at_10s": round(f.price_at_10s, 2),
            "price_at_30s": round(f.price_at_30s, 2),
            "price_at_60s": round(f.price_at_60s, 2),
            "price_at_120s": round(f.price_at_120s, 2),
            "price_at_300s": round(f.price_at_300s, 2),
            "max_favorable_excursion": round(f.max_favorable_excursion, 2),
            "max_adverse_excursion": round(f.max_adverse_excursion, 2),
            "pnl_at_10s_bps": round(f.pnl_at_10s_bps, 1),
            "pnl_at_30s_bps": round(f.pnl_at_30s_bps, 1),
            "pnl_at_60s_bps": round(f.pnl_at_60s_bps, 1),
            "pnl_at_120s_bps": round(f.pnl_at_120s_bps, 1),
            "pnl_at_300s_bps": round(f.pnl_at_300s_bps, 1),
            "fees_assumed_bps": f.fees_assumed_bps,
            "net_pnl_at_60s_bps": round(f.net_pnl_at_60s_bps, 1),
            "measured": f.measured,
        }


# ============================================================
# Rolling Window Buffers
# ============================================================

class RollingBuffer:
    """Time-indexed rolling buffer for trade data."""

    def __init__(self, max_age_seconds: float = 600):
        self.max_age = max_age_seconds
        self.trades: deque = deque(maxlen=100000)
        self.prices: deque = deque(maxlen=100000)
        self.volumes: deque = deque(maxlen=100000)
        self.deltas: deque = deque(maxlen=100000)
        self.timestamps: deque = deque(maxlen=100000)
        self.cvd_values: deque = deque(maxlen=100000)
        self._cvd_running: float = 0.0

    def add(self, timestamp: float, price: float, qty: float, delta: float):
        self.trades.append({"ts": timestamp, "price": price, "qty": qty, "delta": delta})
        self.prices.append(price)
        self.volumes.append(qty)
        self.deltas.append(delta)
        self.timestamps.append(timestamp)
        self._cvd_running += delta
        self.cvd_values.append(self._cvd_running)
        self._prune(timestamp)

    def _prune(self, now: float):
        cutoff = now - self.max_age
        while self.timestamps and self.timestamps[0] < cutoff:
            self.timestamps.popleft()
            self.prices.popleft()
            self.volumes.popleft()
            self.deltas.popleft()
            self.cvd_values.popleft()
            self.trades.popleft()

    def get_window(self, window_seconds: float, now: float):
        """Get data within window_seconds of now."""
        cutoff = now - window_seconds
        indices = []
        for i, ts in enumerate(self.timestamps):
            if ts >= cutoff:
                indices.append(i)
                break
        if not indices:
            return [], [], [], []
        start = indices[0]
        return (
            list(self.prices)[start:],
            list(self.volumes)[start:],
            list(self.deltas)[start:],
            list(self.timestamps)[start:],
        )

    def get_cvd_window(self, window_seconds: float, now: float):
        """Get CVD values within window."""
        cutoff = now - window_seconds
        cvd_list = []
        ts_list = []
        for i, ts in enumerate(self.timestamps):
            if ts >= cutoff:
                cvd_list.append(self.cvd_values[i])
                ts_list.append(ts)
        return cvd_list, ts_list

    @property
    def current_cvd(self) -> float:
        return self._cvd_running

    def volume_in_window(self, window_seconds: float, now: float) -> float:
        cutoff = now - window_seconds
        total = 0.0
        for ts, vol in zip(self.timestamps, self.volumes):
            if ts >= cutoff:
                total += vol
        return total

    def delta_in_window(self, window_seconds: float, now: float) -> float:
        cutoff = now - window_seconds
        total = 0.0
        for ts, d in zip(self.timestamps, self.deltas):
            if ts >= cutoff:
                total += d
        return total

    def price_range_in_window(self, window_seconds: float, now: float):
        prices, _, _, _ = self.get_window(window_seconds, now)
        if not prices:
            return 0, 0
        return min(prices), max(prices)


# ============================================================
# Event Engine
# ============================================================

class EventEngine:
    """
    Detects structural market events from live order flow.
    Runs on every trade tick, evaluates all detectors.
    """

    # --- Tunable Parameters ---
    ABSORPTION_WINDOW = 30          # seconds
    ABSORPTION_VOL_THRESHOLD = 2.0  # min BTC volume to consider
    ABSORPTION_DELTA_RATIO = 0.15   # max |delta|/volume for absorption
    ABSORPTION_PRICE_MAX_MOVE = 50  # max price move in $ for absorption

    EXHAUSTION_WINDOW = 60
    EXHAUSTION_VOL_THRESHOLD = 3.0
    EXHAUSTION_BUBBLE_WINDOW = 120

    SWEEP_LOOKBACK = 300            # seconds to find prior high/low
    SWEEP_THRESHOLD = 20            # $ beyond level to count as sweep
    SWEEP_RECLAIM_WINDOW = 60       # seconds to reclaim

    DIVERGENCE_WINDOW = 60
    DIVERGENCE_MIN_PRICE_MOVE = 30  # min $ move for divergence

    IMBALANCE_WINDOW = 15
    IMBALANCE_RATIO_THRESHOLD = 3.0
    IMBALANCE_MIN_VOLUME = 1.0

    EVENT_COOLDOWN = 10             # seconds between same-type events
    MAX_EVENTS = 500                # max events in history
    FORWARD_MEASURE_INTERVALS = [10, 30, 60, 120, 300]

    def __init__(self):
        self.buffer = RollingBuffer(max_age_seconds=600)
        self._event_log: deque = deque(maxlen=self.MAX_EVENTS)
        self._pending_forward: list = []
        self._last_event_time: dict[str, float] = {}

        # Book state (updated from main)
        self._best_bid: float = 0.0
        self._best_ask: float = 0.0
        self._bid_depth: float = 0.0
        self._ask_depth: float = 0.0

        # Session context
        self._vwap: float = 0.0
        self._session_high: float = 0.0
        self._session_low: float = float("inf")

        # Large trade tracking for exhaustion
        self._recent_bubbles: deque = deque(maxlen=100)

    # --- External state setters ---

    def update_book(self, best_bid: float, best_ask: float, bid_depth: float, ask_depth: float):
        self._best_bid = best_bid
        self._best_ask = best_ask
        self._bid_depth = bid_depth
        self._ask_depth = ask_depth

    def update_session(self, vwap: float, session_high: float, session_low: float):
        self._vwap = vwap
        self._session_high = session_high
        self._session_low = session_low

    def record_bubble(self, price: float, qty: float, side: str, timestamp: float):
        self._recent_bubbles.append({"price": price, "qty": qty, "side": side, "ts": timestamp})

    # --- Main tick entry ---

    def on_trade(self, price: float, qty: float, delta: float, timestamp: float) -> list[dict]:
        """
        Called on every trade. Returns list of detected events (as dicts).
        """
        self.buffer.add(timestamp, price, qty, delta)
        self._measure_pending(timestamp, price)

        events = []

        # Run all detectors
        abs_evt = self._detect_absorption(price, qty, delta, timestamp)
        if abs_evt:
            events.append(abs_evt)

        exh_evt = self._detect_exhaustion(price, qty, delta, timestamp)
        if exh_evt:
            events.append(exh_evt)

        sweep_evt = self._detect_sweep(price, qty, delta, timestamp)
        if sweep_evt:
            events.append(sweep_evt)

        div_evt = self._detect_divergence(price, qty, delta, timestamp)
        if div_evt:
            events.append(div_evt)

        imb_evt = self._detect_imbalance(price, qty, delta, timestamp)
        if imb_evt:
            events.append(imb_evt)

        return events

    def _can_fire(self, event_type: str, now: float) -> bool:
        last = self._last_event_time.get(event_type, 0)
        if now - last < self.EVENT_COOLDOWN:
            return False
        self._last_event_time[event_type] = now
        return True

    # ============================================================
    # 1. ABSORPTION DETECTOR
    # ============================================================

    def _detect_absorption(self, price: float, qty: float, delta: float, now: float) -> Optional[dict]:
        window = self.ABSORPTION_WINDOW
        prices, volumes, deltas, timestamps = self.buffer.get_window(window, now)
        if len(prices) < 5:
            return None

        total_vol = sum(volumes)
        total_delta = sum(deltas)
        if total_vol < self.ABSORPTION_VOL_THRESHOLD:
            return None

        price_move = prices[-1] - prices[0]
        abs_delta_ratio = abs(total_delta) / total_vol

        # Buy absorption: heavy selling but price doesn't break lower
        if total_delta < -self.ABSORPTION_VOL_THRESHOLD * 0.5:
            if price_move > -self.ABSORPTION_PRICE_MAX_MOVE and abs_delta_ratio < self.ABSORPTION_DELTA_RATIO:
                if not self._can_fire("buy_absorption", now):
                    return None
                strength = self._calc_absorption_strength(total_vol, total_delta, price_move, "buy")
                evt = AbsorptionEvent(
                    event_id=str(uuid.uuid4())[:8],
                    side="buy_absorption",
                    timestamp=now,
                    price_level=price,
                    window_seconds=window,
                    aggressive_volume=total_vol,
                    signed_delta=total_delta,
                    price_change_after_aggression=price_move,
                    absorption_strength_score=strength,
                    vwap_distance=price - self._vwap if self._vwap > 0 else 0,
                    spread_context=self._best_ask - self._best_bid if self._best_ask > 0 else 0,
                    regime_context=self._classify_regime(),
                    book_liquidity_context=self._bid_depth,
                    local_volume_percentile=self._volume_percentile(total_vol, window, now),
                    delta_percentile=self._delta_percentile(total_delta, window, now),
                )
                self._log_event(evt)
                return evt.to_dict()

        # Sell absorption: heavy buying but price doesn't break higher
        if total_delta > self.ABSORPTION_VOL_THRESHOLD * 0.5:
            if price_move < self.ABSORPTION_PRICE_MAX_MOVE and abs_delta_ratio < self.ABSORPTION_DELTA_RATIO:
                if not self._can_fire("sell_absorption", now):
                    return None
                strength = self._calc_absorption_strength(total_vol, total_delta, price_move, "sell")
                evt = AbsorptionEvent(
                    event_id=str(uuid.uuid4())[:8],
                    side="sell_absorption",
                    timestamp=now,
                    price_level=price,
                    window_seconds=window,
                    aggressive_volume=total_vol,
                    signed_delta=total_delta,
                    price_change_after_aggression=price_move,
                    absorption_strength_score=strength,
                    vwap_distance=price - self._vwap if self._vwap > 0 else 0,
                    spread_context=self._best_ask - self._best_bid if self._best_ask > 0 else 0,
                    regime_context=self._classify_regime(),
                    book_liquidity_context=self._ask_depth,
                    local_volume_percentile=self._volume_percentile(total_vol, window, now),
                    delta_percentile=self._delta_percentile(total_delta, window, now),
                )
                self._log_event(evt)
                return evt.to_dict()

        return None

    def _calc_absorption_strength(self, vol: float, delta: float, price_move: float, side: str) -> float:
        """Score 0-1: higher = stronger absorption."""
        vol_score = min(vol / 10.0, 1.0) * 0.3
        delta_score = min(abs(delta) / 5.0, 1.0) * 0.3
        if side == "buy":
            # price should NOT move down much despite selling
            move_score = max(0, 1.0 - abs(price_move) / self.ABSORPTION_PRICE_MAX_MOVE) * 0.4
        else:
            move_score = max(0, 1.0 - abs(price_move) / self.ABSORPTION_PRICE_MAX_MOVE) * 0.4
        return min(vol_score + delta_score + move_score, 1.0)

    # ============================================================
    # 2. EXHAUSTION DETECTOR
    # ============================================================

    def _detect_exhaustion(self, price: float, qty: float, delta: float, now: float) -> Optional[dict]:
        window = self.EXHAUSTION_WINDOW
        prices, volumes, deltas, timestamps = self.buffer.get_window(window, now)
        if len(prices) < 10:
            return None

        total_vol = sum(volumes)
        total_delta = sum(deltas)
        if total_vol < self.EXHAUSTION_VOL_THRESHOLD:
            return None

        # Count recent bubbles
        bubble_cutoff = now - self.EXHAUSTION_BUBBLE_WINDOW
        recent_bubbles = [b for b in self._recent_bubbles if b["ts"] >= bubble_cutoff]

        # Price impact per volume: how much price moved per unit of aggression
        price_range = max(prices) - min(prices)
        if total_vol == 0:
            return None
        impact_per_vol = price_range / total_vol

        # Check for declining impact in sub-windows
        half = len(prices) // 2
        first_half_prices = prices[:half]
        second_half_prices = prices[half:]
        first_range = max(first_half_prices) - min(first_half_prices) if len(first_half_prices) > 1 else 0
        second_range = max(second_half_prices) - min(second_half_prices) if len(second_half_prices) > 1 else 0
        first_vol = sum(volumes[:half])
        second_vol = sum(volumes[half:])

        first_impact = first_range / max(first_vol, 0.001)
        second_impact = second_range / max(second_vol, 0.001)

        # Buy exhaustion: aggressive buying near local high, declining impact
        if total_delta > self.EXHAUSTION_VOL_THRESHOLD * 0.5:
            local_high = max(prices)
            near_high = price >= local_high - self.ABSORPTION_PRICE_MAX_MOVE
            declining = second_impact < first_impact * 0.6

            if near_high and declining:
                if not self._can_fire("buy_exhaustion", now):
                    return None
                continuation_fail = 1.0 - (second_impact / max(first_impact, 0.001))
                bubble_count = len([b for b in recent_bubbles if b["side"] == "buy"])
                strength = self._calc_exhaustion_strength(total_vol, impact_per_vol, continuation_fail, bubble_count)

                # CVD divergence context
                cvd_list, _ = self.buffer.get_cvd_window(window, now)
                cvd_div = 0.0
                if len(cvd_list) > 2:
                    cvd_change = cvd_list[-1] - cvd_list[0]
                    price_change = prices[-1] - prices[0]
                    if price_change > 0 and cvd_change > 0:
                        cvd_div = 1.0 - (cvd_change / max(abs(price_change) * 10, 0.001))

                evt = ExhaustionEvent(
                    event_id=str(uuid.uuid4())[:8],
                    side="buy_exhaustion",
                    timestamp=now,
                    price=price,
                    aggressive_volume=total_vol,
                    delta=total_delta,
                    bubble_count=bubble_count,
                    price_impact_per_volume=impact_per_vol,
                    continuation_failure_score=max(continuation_fail, 0),
                    local_extreme_context="near_local_high",
                    cvd_divergence_context=cvd_div,
                    exhaustion_strength_score=strength,
                )
                self._log_event(evt)
                return evt.to_dict()

        # Sell exhaustion: aggressive selling near local low, declining impact
        if total_delta < -self.EXHAUSTION_VOL_THRESHOLD * 0.5:
            local_low = min(prices)
            near_low = price <= local_low + self.ABSORPTION_PRICE_MAX_MOVE
            declining = second_impact < first_impact * 0.6

            if near_low and declining:
                if not self._can_fire("sell_exhaustion", now):
                    return None
                continuation_fail = 1.0 - (second_impact / max(first_impact, 0.001))
                bubble_count = len([b for b in recent_bubbles if b["side"] == "sell"])
                strength = self._calc_exhaustion_strength(total_vol, impact_per_vol, continuation_fail, bubble_count)

                cvd_list, _ = self.buffer.get_cvd_window(window, now)
                cvd_div = 0.0
                if len(cvd_list) > 2:
                    cvd_change = cvd_list[-1] - cvd_list[0]
                    price_change = prices[-1] - prices[0]
                    if price_change < 0 and cvd_change < 0:
                        cvd_div = 1.0 - (abs(cvd_change) / max(abs(price_change) * 10, 0.001))

                evt = ExhaustionEvent(
                    event_id=str(uuid.uuid4())[:8],
                    side="sell_exhaustion",
                    timestamp=now,
                    price=price,
                    aggressive_volume=total_vol,
                    delta=total_delta,
                    bubble_count=bubble_count,
                    price_impact_per_volume=impact_per_vol,
                    continuation_failure_score=max(continuation_fail, 0),
                    local_extreme_context="near_local_low",
                    cvd_divergence_context=cvd_div,
                    exhaustion_strength_score=strength,
                )
                self._log_event(evt)
                return evt.to_dict()

        return None

    def _calc_exhaustion_strength(self, vol: float, impact: float, cont_fail: float, bubbles: int) -> float:
        vol_score = min(vol / 8.0, 1.0) * 0.25
        impact_score = max(0, 1.0 - impact * 100) * 0.25  # lower impact = stronger
        fail_score = min(cont_fail, 1.0) * 0.3
        bubble_score = min(bubbles / 5.0, 1.0) * 0.2
        return min(vol_score + impact_score + fail_score + bubble_score, 1.0)

    # ============================================================
    # 3. LIQUIDITY SWEEP DETECTOR
    # ============================================================

    def _detect_sweep(self, price: float, qty: float, delta: float, now: float) -> Optional[dict]:
        lookback = self.SWEEP_LOOKBACK
        prices, volumes, deltas, timestamps = self.buffer.get_window(lookback, now)
        if len(prices) < 20:
            return None

        # Find local high/low (excluding last 5 ticks = the "sweep" zone)
        if len(prices) < 10:
            return None
        prior_prices = prices[:-5]
        prior_high = max(prior_prices)
        prior_low = min(prior_prices)

        # High sweep: price breaks above prior high then comes back
        if price > prior_high and price < prior_high + self.SWEEP_THRESHOLD * 3:
            # Check if price came back inside within recent ticks
            recent = prices[-10:]
            came_back = any(p <= prior_high + 5 for p in recent[5:]) if len(recent) > 5 else False

            if came_back:
                if not self._can_fire("high_sweep", now):
                    return None
                sweep_dist = max(recent) - prior_high
                sweep_vol = sum(volumes[-10:])
                sweep_delta = sum(deltas[-10:])
                strength = self._calc_sweep_strength(sweep_dist, sweep_vol, abs(sweep_delta))

                evt = LiquiditySweepEvent(
                    event_id=str(uuid.uuid4())[:8],
                    side="high_sweep",
                    timestamp=now,
                    swept_level=prior_high,
                    sweep_distance=sweep_dist,
                    sweep_volume=sweep_vol,
                    sweep_delta=sweep_delta,
                    reclaim_status=True,
                    reversal_confirmation=delta < 0,  # selling after sweep
                    sweep_strength_score=strength,
                )
                self._log_event(evt)
                return evt.to_dict()

        # Low sweep: price breaks below prior low then comes back
        if price < prior_low and price > prior_low - self.SWEEP_THRESHOLD * 3:
            recent = prices[-10:]
            came_back = any(p >= prior_low - 5 for p in recent[5:]) if len(recent) > 5 else False

            if came_back:
                if not self._can_fire("low_sweep", now):
                    return None
                sweep_dist = prior_low - min(recent)
                sweep_vol = sum(volumes[-10:])
                sweep_delta = sum(deltas[-10:])
                strength = self._calc_sweep_strength(sweep_dist, sweep_vol, abs(sweep_delta))

                evt = LiquiditySweepEvent(
                    event_id=str(uuid.uuid4())[:8],
                    side="low_sweep",
                    timestamp=now,
                    swept_level=prior_low,
                    sweep_distance=sweep_dist,
                    sweep_volume=sweep_vol,
                    sweep_delta=sweep_delta,
                    reclaim_status=True,
                    reversal_confirmation=delta > 0,  # buying after sweep
                    sweep_strength_score=strength,
                )
                self._log_event(evt)
                return evt.to_dict()

        return None

    def _calc_sweep_strength(self, distance: float, vol: float, abs_delta: float) -> float:
        dist_score = min(distance / 50.0, 1.0) * 0.35
        vol_score = min(vol / 5.0, 1.0) * 0.35
        delta_score = min(abs_delta / 3.0, 1.0) * 0.3
        return min(dist_score + vol_score + delta_score, 1.0)

    # ============================================================
    # 4. DELTA DIVERGENCE DETECTOR
    # ============================================================

    def _detect_divergence(self, price: float, qty: float, delta: float, now: float) -> Optional[dict]:
        window = self.DIVERGENCE_WINDOW
        prices, _, _, timestamps = self.buffer.get_window(window, now)
        cvd_list, cvd_ts = self.buffer.get_cvd_window(window, now)

        if len(prices) < 10 or len(cvd_list) < 10:
            return None

        price_change = prices[-1] - prices[0]
        cvd_change = cvd_list[-1] - cvd_list[0]

        if abs(price_change) < self.DIVERGENCE_MIN_PRICE_MOVE:
            return None

        # Bearish divergence: price higher high, CVD doesn't confirm
        if price_change > 0 and cvd_change <= 0:
            if not self._can_fire("bearish_divergence", now):
                return None
            strength = self._calc_divergence_strength(price_change, cvd_change)
            evt = DeltaDivergenceEvent(
                event_id=str(uuid.uuid4())[:8],
                side="bearish_divergence",
                timestamp=now,
                price_structure="higher_high",
                cvd_structure="lower_or_flat",
                divergence_window=window,
                divergence_strength_score=strength,
                local_trend_context=self._classify_regime(),
                price_at_detection=price,
                cvd_at_detection=self.buffer.current_cvd,
            )
            self._log_event(evt)
            return evt.to_dict()

        # Bullish divergence: price lower low, CVD doesn't confirm
        if price_change < 0 and cvd_change >= 0:
            if not self._can_fire("bullish_divergence", now):
                return None
            strength = self._calc_divergence_strength(price_change, cvd_change)
            evt = DeltaDivergenceEvent(
                event_id=str(uuid.uuid4())[:8],
                side="bullish_divergence",
                timestamp=now,
                price_structure="lower_low",
                cvd_structure="higher_or_flat",
                divergence_window=window,
                divergence_strength_score=strength,
                local_trend_context=self._classify_regime(),
                price_at_detection=price,
                cvd_at_detection=self.buffer.current_cvd,
            )
            self._log_event(evt)
            return evt.to_dict()

        return None

    def _calc_divergence_strength(self, price_chg: float, cvd_chg: float) -> float:
        price_score = min(abs(price_chg) / 100.0, 1.0) * 0.5
        # Stronger divergence = CVD moves opposite more
        if price_chg > 0:
            cvd_score = min(max(-cvd_chg, 0) / 5.0, 1.0) * 0.5
        else:
            cvd_score = min(max(cvd_chg, 0) / 5.0, 1.0) * 0.5
        return min(price_score + cvd_score, 1.0)

    # ============================================================
    # 5. IMBALANCE DETECTOR
    # ============================================================

    def _detect_imbalance(self, price: float, qty: float, delta: float, now: float) -> Optional[dict]:
        window = self.IMBALANCE_WINDOW
        _, volumes, deltas, _ = self.buffer.get_window(window, now)
        if len(volumes) < 5:
            return None

        buy_vol = sum(v for v, d in zip(volumes, deltas) if d > 0)
        sell_vol = sum(v for v, d in zip(volumes, deltas) if d < 0)
        total = buy_vol + sell_vol

        if total < self.IMBALANCE_MIN_VOLUME:
            return None

        if buy_vol == 0 or sell_vol == 0:
            return None

        ratio = buy_vol / sell_vol if sell_vol > 0 else 999
        inv_ratio = sell_vol / buy_vol if buy_vol > 0 else 999

        net_delta = buy_vol - sell_vol

        # Buy imbalance
        if ratio >= self.IMBALANCE_RATIO_THRESHOLD:
            if not self._can_fire("buy_imbalance", now):
                return None
            classification = self._classify_imbalance(price, net_delta, "buy", now)
            prices, _, _, _ = self.buffer.get_window(window, now)
            price_resp = (prices[-1] - prices[0]) if len(prices) > 1 else 0
            strength = min((ratio - 1) / 5.0, 1.0)

            evt = ImbalanceEvent(
                event_id=str(uuid.uuid4())[:8],
                side="buy_imbalance",
                timestamp=now,
                volume_buy=buy_vol,
                volume_sell=sell_vol,
                delta=net_delta,
                imbalance_ratio=ratio,
                price_response=price_resp,
                continuation_score=strength if classification == "continuation" else 0.0,
                failure_score=strength if classification in ("absorption", "exhaustion") else 0.0,
                classification=classification,
            )
            self._log_event(evt)
            return evt.to_dict()

        # Sell imbalance
        if inv_ratio >= self.IMBALANCE_RATIO_THRESHOLD:
            if not self._can_fire("sell_imbalance", now):
                return None
            classification = self._classify_imbalance(price, net_delta, "sell", now)
            prices, _, _, _ = self.buffer.get_window(window, now)
            price_resp = (prices[-1] - prices[0]) if len(prices) > 1 else 0
            strength = min((inv_ratio - 1) / 5.0, 1.0)

            evt = ImbalanceEvent(
                event_id=str(uuid.uuid4())[:8],
                side="sell_imbalance",
                timestamp=now,
                volume_buy=buy_vol,
                volume_sell=sell_vol,
                delta=net_delta,
                imbalance_ratio=inv_ratio,
                price_response=price_resp,
                continuation_score=strength if classification == "continuation" else 0.0,
                failure_score=strength if classification in ("absorption", "exhaustion") else 0.0,
                classification=classification,
            )
            self._log_event(evt)
            return evt.to_dict()

        return None

    def _classify_imbalance(self, price: float, delta: float, side: str, now: float) -> str:
        """Classify imbalance as continuation, absorption, or exhaustion."""
        # Check recent price action after imbalance window
        recent_prices, recent_vols, recent_deltas, _ = self.buffer.get_window(5, now)
        if len(recent_prices) < 2:
            return "continuation"

        recent_move = recent_prices[-1] - recent_prices[0]

        if side == "buy":
            if recent_move > 10:
                return "continuation"
            elif recent_move < -5:
                return "absorption"
            else:
                return "exhaustion"
        else:
            if recent_move < -10:
                return "continuation"
            elif recent_move > 5:
                return "absorption"
            else:
                return "exhaustion"

    # ============================================================
    # Forward Outcome Measurement
    # ============================================================

    def _log_event(self, event):
        """Log event and schedule forward measurement."""
        self._event_log.append(event)
        self._pending_forward.append({
            "event": event,
            "created": event.timestamp,
            "measure_at": {t: event.timestamp + t for t in self.FORWARD_MEASURE_INTERVALS},
            "measured": set(),
            "initial_price": event.price if hasattr(event, "price") else (event.price_level if hasattr(event, "price_level") else 0),
        })

    def _measure_pending(self, now: float, current_price: float):
        """Measure forward outcomes for pending events."""
        still_pending = []
        for pending in self._pending_forward:
            event = pending["event"]
            initial = pending["initial_price"]
            if initial == 0:
                continue

            all_done = True
            for interval, target_time in pending["measure_at"].items():
                if interval in pending["measured"]:
                    continue
                if now >= target_time:
                    # Measure this interval
                    price_diff = current_price - initial
                    price_diff_bps = (price_diff / initial) * 10000

                    fwd = event.forward
                    if interval == 10:
                        fwd.price_at_10s = current_price
                        fwd.pnl_at_10s_bps = price_diff_bps
                    elif interval == 30:
                        fwd.price_at_30s = current_price
                        fwd.pnl_at_30s_bps = price_diff_bps
                    elif interval == 60:
                        fwd.price_at_60s = current_price
                        fwd.pnl_at_60s_bps = price_diff_bps
                        fwd.net_pnl_at_60s_bps = price_diff_bps - fwd.fees_assumed_bps * 2
                    elif interval == 120:
                        fwd.price_at_120s = current_price
                        fwd.pnl_at_120s_bps = price_diff_bps
                    elif interval == 300:
                        fwd.price_at_300s = current_price
                        fwd.pnl_at_300s_bps = price_diff_bps
                        fwd.measured = True

                    # Update MFE/MAE
                    fwd.max_favorable_excursion = max(fwd.max_favorable_excursion, abs(price_diff))
                    fwd.max_adverse_excursion = max(fwd.max_adverse_excursion, abs(min(0, price_diff) if price_diff > 0 else max(0, price_diff)))

                    pending["measured"].add(interval)
                else:
                    all_done = False

            # Update MFE/MAE continuously
            price_diff = current_price - initial
            event.forward.max_favorable_excursion = max(event.forward.max_favorable_excursion, abs(price_diff))

            if not all_done:
                still_pending.append(pending)

        self._pending_forward = still_pending

    # ============================================================
    # Helpers
    # ============================================================

    def _classify_regime(self) -> str:
        """Simple regime classification based on volatility and trend."""
        if len(self.buffer.prices) < 20:
            return "unknown"
        prices = list(self.buffer.prices)[-60:]
        price_range = max(prices) - min(prices)
        avg_price = sum(prices) / len(prices)
        volatility_pct = (price_range / avg_price) * 100 if avg_price > 0 else 0

        if volatility_pct > 1.0:
            return "high_volatility"
        elif volatility_pct > 0.3:
            return "normal"
        else:
            return "low_volatility"

    def _volume_percentile(self, vol: float, window: float, now: float) -> float:
        """Rough percentile of volume vs recent windows."""
        # Compare to last 10 windows of same size
        scores = []
        for i in range(10):
            offset = (i + 1) * window
            w_prices, w_vols, _, _ = self.buffer.get_window(window, now - offset)
            if w_vols:
                scores.append(sum(w_vols))
        if not scores:
            return 0.5
        better = sum(1 for s in scores if vol > s)
        return better / len(scores)

    def _delta_percentile(self, delta: float, window: float, now: float) -> float:
        scores = []
        for i in range(10):
            offset = (i + 1) * window
            _, _, w_deltas, _ = self.buffer.get_window(window, now - offset)
            if w_deltas:
                scores.append(abs(sum(w_deltas)))
        if not scores:
            return 0.5
        better = sum(1 for s in scores if abs(delta) > s)
        return better / len(scores)

    # ============================================================
    # Public API
    # ============================================================

    def get_events(self, limit: int = 50) -> list[dict]:
        """Get recent events as dicts."""
        events = list(self._event_log)
        return [e.to_dict() for e in events[-limit:]]

    def get_event_stats(self) -> dict:
        """Get event statistics for dashboard."""
        events = list(self._event_log)
        if not events:
            return {
                "total": 0,
                "by_type": {},
                "by_side": {},
                "avg_strength": 0,
                "measured_count": 0,
                "unmeasured_count": 0,
            }

        by_type = {}
        by_side = {}
        strengths = []
        measured = 0
        for e in events:
            t = e.event_type
            s = e.side
            by_type[t] = by_type.get(t, 0) + 1
            by_side[s] = by_side.get(s, 0) + 1
            if hasattr(e, "absorption_strength_score"):
                strengths.append(e.absorption_strength_score)
            elif hasattr(e, "exhaustion_strength_score"):
                strengths.append(e.exhaustion_strength_score)
            elif hasattr(e, "sweep_strength_score"):
                strengths.append(e.sweep_strength_score)
            elif hasattr(e, "divergence_strength_score"):
                strengths.append(e.divergence_strength_score)
            elif hasattr(e, "imbalance_ratio"):
                strengths.append(min(e.imbalance_ratio / 5.0, 1.0))
            if e.forward.measured:
                measured += 1

        return {
            "total": len(events),
            "by_type": by_type,
            "by_side": by_side,
            "avg_strength": round(sum(strengths) / len(strengths), 3) if strengths else 0,
            "measured_count": measured,
            "unmeasured_count": len(events) - measured,
        }
