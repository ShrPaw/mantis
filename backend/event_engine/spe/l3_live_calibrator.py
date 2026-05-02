"""
MANTIS SPE — L3 1m Displacement Live Calibrator (Shadow Diagnostic)

Independent shadow system that evaluates 1m candle-based displacement metrics
alongside production L3. Does NOT modify production L3. Observation-only.

Computes:
  - Single candle: body_bps, range_bps, close_to_close_bps
  - Multi-candle legs: 2c/3c/5c leg_bps, directional_efficiency, pullback_ratio
  - Rolling percentile stats at 60/240/720 candle windows
  - 5 shadow variants with independent pass/fail logic

Persists:
  - data/metrics/l3_live_shadow.json  (latest snapshot)
  - data/events/l3_shadow_events.jsonl (append on any shadow pass)
"""

import json
import logging
import math
import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
# Data structures
# ────────────────────────────────────────────────────────────

@dataclass
class Candle1m:
    """Aggregated 1m candle from ticks."""
    time: float          # candle open time (unix seconds, aligned to 1m)
    open: float = 0.0
    high: float = 0.0
    low: float = float("inf")
    close: float = 0.0
    volume: float = 0.0
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    trade_count: int = 0
    vwap: float = 0.0
    _vol_price_sum: float = 0.0

    def add_trade(self, price: float, qty: float, delta: float):
        if self.open == 0.0:
            self.open = price
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += qty
        if delta > 0:
            self.buy_volume += qty
        else:
            self.sell_volume += qty
        self.trade_count += 1
        self._vol_price_sum += price * qty

    def finalize(self):
        if self.volume > 0:
            self.vwap = self._vol_price_sum / self.volume
        if self.low == float("inf"):
            self.low = self.close

    @property
    def body_bps(self) -> float:
        avg = (self.open + self.close) / 2
        if avg <= 0:
            return 0.0
        return abs(self.close - self.open) / avg * 10000

    @property
    def range_bps(self) -> float:
        avg = (self.open + self.close) / 2
        if avg <= 0 or self.low == float("inf"):
            return 0.0
        return (self.high - self.low) / avg * 10000

    @property
    def direction(self) -> int:
        """1 = up, -1 = down, 0 = flat."""
        if self.close > self.open:
            return 1
        elif self.close < self.open:
            return -1
        return 0

    def to_dict(self) -> dict:
        return {
            "time": self.time,
            "open": round(self.open, 2),
            "high": round(self.high, 2),
            "low": round(self.low, 2),
            "close": round(self.close, 2),
            "volume": round(self.volume, 6),
            "buy_volume": round(self.buy_volume, 6),
            "sell_volume": round(self.sell_volume, 6),
            "trade_count": self.trade_count,
            "body_bps": round(self.body_bps, 2),
            "range_bps": round(self.range_bps, 2),
        }


@dataclass
class PercentileStats:
    """Rolling percentile stats for a metric."""
    window_size: int
    values: list = field(default_factory=list)

    def add(self, val: float):
        self.values.append(val)
        if len(self.values) > self.window_size:
            self.values = self.values[-self.window_size:]

    def percentile(self, p: float) -> float:
        if not self.values:
            return 0.0
        s = sorted(self.values)
        idx = min(int(len(s) * p), len(s) - 1)
        return s[idx]

    def rank(self, val: float) -> float:
        """What percentile rank is val in current distribution? 0-1."""
        if not self.values:
            return 0.5
        count_below = sum(1 for v in self.values if v < val)
        return count_below / len(self.values)

    @property
    def count(self) -> int:
        return len(self.values)

    def to_dict(self) -> dict:
        return {
            "window": self.window_size,
            "count": self.count,
            "p75": round(self.percentile(0.75), 2),
            "p80": round(self.percentile(0.80), 2),
            "p85": round(self.percentile(0.85), 2),
            "p90": round(self.percentile(0.90), 2),
            "p95": round(self.percentile(0.95), 2),
            "p99": round(self.percentile(0.99), 2),
        }


# ────────────────────────────────────────────────────────────
# Production L3 replay (exact logic)
# ────────────────────────────────────────────────────────────

class ProductionL3Replay:
    """
    Replays production L3 logic from candle data.
    Uses the same algorithm as DisplacementDetector but from 1m candle ticks.
    """

    def __init__(self):
        self._body_history: deque = deque(maxlen=200)
        self._active = False
        self._start_price = 0.0
        self._start_time = 0.0
        self._direction = ""

    def evaluate(self, candles: list[Candle1m]) -> dict:
        """Evaluate production L3 logic from recent candles."""
        if len(candles) < 3:
            return {"pass": False, "reason": "insufficient_data", "status": "NOT_EVALUATED"}

        # Simulate 180s window = last 3 candles
        recent = candles[-3:]
        prices = []
        for c in recent:
            prices.extend([c.open, c.high, c.low, c.close])

        if not prices:
            return {"pass": False, "reason": "no_prices", "status": "NOT_EVALUATED"}

        window_high = max(prices)
        window_low = min(prices)
        avg_price = sum(prices) / len(prices)

        if avg_price <= 0:
            return {"pass": False, "reason": "invalid_price", "status": "NOT_EVALUATED"}

        body_bps = ((window_high - window_low) / avg_price) * 10000
        self._body_history.append(body_bps)

        if len(self._body_history) < 10:
            return {"pass": False, "reason": "warming_up", "status": "NOT_EVALUATED"}

        sorted_bodies = sorted(self._body_history)
        p85_idx = int(len(sorted_bodies) * 0.85)
        p85 = sorted_bodies[min(p85_idx, len(sorted_bodies) - 1)]

        body_ok = body_bps >= p85
        move_ok = body_bps >= 15.0

        direction = "UP" if recent[-1].close > recent[0].open else "DOWN"

        # Continuation: check segments
        continuation_ok = False
        segment_size = max(len(prices) // 3, 1)
        segments = []
        for i in range(0, len(prices), segment_size):
            seg = prices[i:i + segment_size]
            if seg:
                segments.append(seg)

        if len(segments) >= 2:
            for i in range(1, len(segments)):
                prev_avg = sum(segments[i-1]) / len(segments[i-1])
                curr_avg = sum(segments[i]) / len(segments[i])
                if prev_avg > 0:
                    change_bps = abs(curr_avg - prev_avg) / prev_avg * 10000
                    if direction == "UP" and curr_avg > prev_avg and change_bps >= 5.0:
                        continuation_ok = True
                    elif direction == "DOWN" and curr_avg < prev_avg and change_bps >= 5.0:
                        continuation_ok = True

        confirmed = body_ok and move_ok
        block_reason = ""
        if not body_ok:
            block_reason = f"body_bps={body_bps:.1f} < p85={p85:.1f}"
        elif not move_ok:
            block_reason = f"body_bps={body_bps:.1f} < 15 bps floor"

        return {
            "pass": confirmed,
            "status": "PASS" if confirmed else "FAIL",
            "reason": block_reason or ("confirmed" if confirmed else ""),
            "body_bps": round(body_bps, 2),
            "p85_threshold": round(p85, 2),
            "continuation_ok": continuation_ok,
            "direction": direction,
        }


# ────────────────────────────────────────────────────────────
# Shadow Variants
# ────────────────────────────────────────────────────────────

def _leg_bps(candles: list[Candle1m], count: int) -> float:
    """Compute leg move in bps over `count` candles from the tail."""
    if len(candles) < count or count < 2:
        return 0.0
    leg = candles[-count:]
    start_price = leg[0].open
    end_price = leg[-1].close
    avg = (start_price + end_price) / 2
    if avg <= 0:
        return 0.0
    return abs(end_price - start_price) / avg * 10000


def _directional_efficiency(candles: list[Candle1m], count: int) -> float:
    """
    Net move / total path. 1.0 = straight line, 0.0 = round trip.
    """
    if len(candles) < count or count < 2:
        return 0.0
    leg = candles[-count:]
    net_move = abs(leg[-1].close - leg[0].open)
    total_path = sum(abs(c.close - c.open) for c in leg)
    if total_path <= 0:
        return 0.0
    return net_move / total_path


def _pullback_ratio(candles: list[Candle1m], count: int) -> float:
    """
    Max retracement within leg as fraction of total leg move.
    0.0 = no pullback, 1.0 = full reversal.
    """
    if len(candles) < count or count < 2:
        return 1.0
    leg = candles[-count:]
    leg_high = max(c.high for c in leg)
    leg_low = min(c.low for c in leg)
    leg_range = leg_high - leg_low
    if leg_range <= 0:
        return 0.0

    # Direction: up leg or down leg
    is_up = leg[-1].close >= leg[0].open

    if is_up:
        # Max pullback = how far price dipped from running high
        max_pullback = 0.0
        running_high = leg[0].high
        for c in leg:
            running_high = max(running_high, c.high)
            pullback = running_high - c.low
            max_pullback = max(max_pullback, pullback)
        return max_pullback / leg_range
    else:
        # Max pullback = how far price bounced from running low
        max_pullback = 0.0
        running_low = leg[0].low
        for c in leg:
            running_low = min(running_low, c.low)
            pullback = c.high - running_low
            max_pullback = max(max_pullback, pullback)
        return max_pullback / leg_range


def _close_to_close_bps(candles: list[Candle1m]) -> float:
    """Close-to-close between last two candles."""
    if len(candles) < 2:
        return 0.0
    prev_close = candles[-2].close
    curr_close = candles[-1].close
    avg = (prev_close + curr_close) / 2
    if avg <= 0:
        return 0.0
    return abs(curr_close - prev_close) / avg * 10000


def _max_extension_bps(candles: list[Candle1m], count: int) -> float:
    """Max extension from leg open in bps."""
    if len(candles) < count or count < 2:
        return 0.0
    leg = candles[-count:]
    open_price = leg[0].open
    if open_price <= 0:
        return 0.0
    max_ext = max(
        abs(c.high - open_price),
        abs(c.low - open_price),
    )
    for c in leg:
        max_ext = max(max_ext, abs(c.close - open_price))
    return max_ext / open_price * 10000


@dataclass
class ShadowVariant:
    """Result of a shadow variant evaluation."""
    name: str
    passed: bool
    reason: str
    metrics: dict = field(default_factory=dict)


def _eval_shadow_3c(candles: list[Candle1m], stats: dict[str, PercentileStats],
                    volume_pct: float) -> ShadowVariant:
    """
    Shadow B: 1m 3-candle displacement
      3c_leg_bps >= rolling p85
      AND directional_efficiency_3c >= 0.55
      AND volume_percentile >= 60
    """
    leg = _leg_bps(candles, 3)
    eff = _directional_efficiency(candles, 3)
    p85 = stats["3c_leg_bps"].percentile(0.85)

    pass_leg = leg >= p85 and p85 > 0
    pass_eff = eff >= 0.55
    pass_vol = volume_pct >= 0.60

    reasons = []
    if not pass_leg:
        reasons.append(f"3c_leg={leg:.1f} < p85={p85:.1f}")
    if not pass_eff:
        reasons.append(f"eff={eff:.2f} < 0.55")
    if not pass_vol:
        reasons.append(f"vol_pct={volume_pct:.2f} < 0.60")

    return ShadowVariant(
        name="shadow_3c",
        passed=pass_leg and pass_eff and pass_vol,
        reason="; ".join(reasons) if reasons else "confirmed",
        metrics={
            "3c_leg_bps": round(leg, 2),
            "directional_efficiency_3c": round(eff, 3),
            "volume_percentile": round(volume_pct, 3),
            "p85_threshold": round(p85, 2),
        },
    )


def _eval_shadow_stress(candles: list[Candle1m], stats: dict[str, PercentileStats],
                        volume_pct: float) -> ShadowVariant:
    """
    Shadow C: 1m stress displacement
      3c_leg_bps >= rolling p90
      AND directional_efficiency_3c >= 0.65
      AND volume_percentile >= 75
    """
    leg = _leg_bps(candles, 3)
    eff = _directional_efficiency(candles, 3)
    p90 = stats["3c_leg_bps"].percentile(0.90)

    pass_leg = leg >= p90 and p90 > 0
    pass_eff = eff >= 0.65
    pass_vol = volume_pct >= 0.75

    reasons = []
    if not pass_leg:
        reasons.append(f"3c_leg={leg:.1f} < p90={p90:.1f}")
    if not pass_eff:
        reasons.append(f"eff={eff:.2f} < 0.65")
    if not pass_vol:
        reasons.append(f"vol_pct={volume_pct:.2f} < 0.75")

    return ShadowVariant(
        name="shadow_stress",
        passed=pass_leg and pass_eff and pass_vol,
        reason="; ".join(reasons) if reasons else "confirmed",
        metrics={
            "3c_leg_bps": round(leg, 2),
            "directional_efficiency_3c": round(eff, 3),
            "volume_percentile": round(volume_pct, 3),
            "p90_threshold": round(p90, 2),
        },
    )


def _eval_shadow_single_candle(candles: list[Candle1m],
                               stats_body: dict,
                               stats_range: dict = None) -> ShadowVariant:
    """
    Shadow D: Single candle impulse
      body_bps >= rolling p90
      AND range_bps >= rolling p85
    """
    if not candles:
        return ShadowVariant("shadow_single_candle", False, "no candles")

    last = candles[-1]
    body = last.body_bps
    rng = last.range_bps

    # stats_body is {window_key: PercentileStats} for body_bps
    p90_body = stats_body["60"].percentile(0.90) if "60" in stats_body else 0.0
    # stats_range is {window_key: PercentileStats} for range_bps (or fallback to body)
    if stats_range and "60" in stats_range:
        p85_range = stats_range["60"].percentile(0.85)
    else:
        p85_range = p90_body  # fallback

    pass_body = body >= p90_body and p90_body > 0
    pass_range = rng >= p85_range and p85_range > 0

    reasons = []
    if not pass_body:
        reasons.append(f"body={body:.1f} < p90={p90_body:.1f}")
    if not pass_range:
        reasons.append(f"range={rng:.1f} < p85={p85_range:.1f}")

    return ShadowVariant(
        name="shadow_single_candle",
        passed=pass_body and pass_range,
        reason="; ".join(reasons) if reasons else "confirmed",
        metrics={
            "body_bps": round(body, 2),
            "range_bps": round(rng, 2),
            "p90_body_threshold": round(p90_body, 2),
            "p85_range_threshold": round(p85_range, 2),
        },
    )


def _eval_shadow_5c(candles: list[Candle1m],
                    stats: dict[str, PercentileStats]) -> ShadowVariant:
    """
    Shadow E: 5-candle displacement leg
      5c_leg_bps >= rolling p85
      AND directional_efficiency_5c >= 0.60
      AND pullback_ratio <= 0.40
    """
    leg = _leg_bps(candles, 5)
    eff = _directional_efficiency(candles, 5)
    pbr = _pullback_ratio(candles, 5)
    p85 = stats["5c_leg_bps"].percentile(0.85)

    pass_leg = leg >= p85 and p85 > 0
    pass_eff = eff >= 0.60
    pass_pbr = pbr <= 0.40

    reasons = []
    if not pass_leg:
        reasons.append(f"5c_leg={leg:.1f} < p85={p85:.1f}")
    if not pass_eff:
        reasons.append(f"eff={eff:.2f} < 0.60")
    if not pass_pbr:
        reasons.append(f"pullback={pbr:.2f} > 0.40")

    return ShadowVariant(
        name="shadow_5c",
        passed=pass_leg and pass_eff and pass_pbr,
        reason="; ".join(reasons) if reasons else "confirmed",
        metrics={
            "5c_leg_bps": round(leg, 2),
            "directional_efficiency_5c": round(eff, 3),
            "pullback_ratio": round(pbr, 3),
            "p85_threshold": round(p85, 2),
        },
    )


# ────────────────────────────────────────────────────────────
# Main Calibrator
# ────────────────────────────────────────────────────────────

class L3LiveCalibrator:
    """
    Shadow diagnostic system for L3 displacement.
    Aggregates ticks into 1m candles, computes metrics,
    evaluates 5 shadow variants, persists results.
    """

    def __init__(self, max_candles: int = 1200):
        self._max_candles = max_candles
        self._candles: deque[Candle1m] = deque(maxlen=max_candles)
        self._current_candle: Optional[Candle1m] = None
        self._candle_duration = 60.0  # 1 minute

        # Production L3 replay
        self._prod_l3 = ProductionL3Replay()

        # Rolling percentile stats at 3 windows
        self._stats: dict[str, dict[str, PercentileStats]] = {}
        for metric in ["body_bps", "range_bps", "3c_leg_bps", "5c_leg_bps"]:
            self._stats[metric] = {
                "60": PercentileStats(60),
                "240": PercentileStats(240),
                "720": PercentileStats(720),
            }

        # Volume tracking for percentile
        self._candle_volumes: deque = deque(maxlen=720)

        # Shadow event log
        self._shadow_event_count = 0

        # Persistence paths
        self._shadow_json_path = "data/metrics/l3_live_shadow.json"
        self._shadow_events_path = "data/events/l3_shadow_events.jsonl"

        os.makedirs("data/metrics", exist_ok=True)
        os.makedirs("data/events", exist_ok=True)

        logger.info("L3 Live Calibrator initialized (shadow diagnostic)")

    def on_trade(self, price: float, qty: float, delta: float, timestamp: float):
        """
        Called on every trade tick.
        Aggregates into 1m candles and updates metrics when candle closes.
        """
        candle_time = math.floor(timestamp / self._candle_duration) * self._candle_duration

        if self._current_candle is None:
            self._current_candle = Candle1m(time=candle_time)

        # If we've moved to a new candle, finalize the old one
        if candle_time > self._current_candle.time:
            self._current_candle.finalize()
            self._candles.append(self._current_candle)
            self._on_candle_close(self._current_candle)
            self._current_candle = Candle1m(time=candle_time)

        self._current_candle.add_trade(price, qty, delta)

    def _on_candle_close(self, candle: Candle1m):
        """Process a closed candle: update stats, evaluate shadows."""
        # Update volume tracking
        self._candle_volumes.append(candle.volume)

        # Update percentile stats
        for metric_name, getter in [
            ("body_bps", lambda c: c.body_bps),
            ("range_bps", lambda c: c.range_bps),
        ]:
            val = getter(candle)
            for win_key in self._stats[metric_name]:
                self._stats[metric_name][win_key].add(val)

        # Multi-candle metrics need at least N candles
        candle_list = list(self._candles)
        if len(candle_list) >= 3:
            leg3 = _leg_bps(candle_list, 3)
            for win_key in self._stats["3c_leg_bps"]:
                self._stats["3c_leg_bps"][win_key].add(leg3)

        if len(candle_list) >= 5:
            leg5 = _leg_bps(candle_list, 5)
            for win_key in self._stats["5c_leg_bps"]:
                self._stats["5c_leg_bps"][win_key].add(leg5)

    def evaluate(self) -> dict:
        """
        Run all shadow variants and return full diagnostic snapshot.
        Called on-demand (e.g., by API endpoint).
        """
        candle_list = list(self._candles)
        if len(candle_list) < 5:
            return self._build_result(
                candle_list, prod_status="NOT_EVALUATED",
                prod_reason="insufficient_candles",
                shadows=[], interpretation="Warming up — need at least 5 candles",
            )

        # Volume percentile of latest candle
        vol_pct = self._volume_percentile(candle_list[-1].volume)

        # Volatility percentile (range_bps rank in 60-candle window)
        latest_range = candle_list[-1].range_bps
        vol_rank = self._stats["range_bps"]["60"].rank(latest_range)

        # Production L3 replay
        prod = self._prod_l3.evaluate(candle_list)

        # Shadow variants
        shadow_3c = _eval_shadow_3c(candle_list, self._flat_stats("3c_leg_bps"), vol_pct)
        shadow_stress = _eval_shadow_stress(candle_list, self._flat_stats("3c_leg_bps"), vol_pct)
        shadow_single = _eval_shadow_single_candle(
            candle_list, self._flat_stats("body_bps"), self._flat_stats("range_bps")
        )
        shadow_5c = _eval_shadow_5c(candle_list, self._flat_stats("5c_leg_bps"))

        shadows = [shadow_3c, shadow_stress, shadow_single, shadow_5c]

        # Check if any shadow passed
        any_shadow_pass = any(s.passed for s in shadows)

        # Persist shadow events if any variant passed
        if any_shadow_pass:
            self._log_shadow_event(candle_list, prod, shadows)

        # Build interpretation
        interpretation = self._build_interpretation(
            candle_list, prod, shadows, vol_pct, vol_rank
        )

        # Persist latest snapshot
        result = self._build_result(
            candle_list, prod_status=prod["status"],
            prod_reason=prod.get("reason", ""),
            shadows=shadows, interpretation=interpretation,
            vol_pct=vol_pct, vol_rank=vol_rank,
        )
        self._persist_snapshot(result)

        return result

    def _flat_stats(self, metric: str) -> dict[str, PercentileStats]:
        """Get stats dict keyed by window size string."""
        return self._stats.get(metric, {
            "60": PercentileStats(60),
            "240": PercentileStats(240),
            "720": PercentileStats(720),
        })

    def _volume_percentile(self, vol: float) -> float:
        """Volume percentile vs recent candles."""
        if not self._candle_volumes:
            return 0.5
        vols = list(self._candle_volumes)
        count_below = sum(1 for v in vols if v < vol)
        return count_below / len(vols)

    def _build_result(self, candles: list[Candle1m],
                      prod_status: str, prod_reason: str,
                      shadows: list[ShadowVariant],
                      interpretation: str,
                      vol_pct: float = 0.0,
                      vol_rank: float = 0.0) -> dict:
        """Build the full diagnostic result."""
        candle_list = list(self._candles)
        last = candle_list[-1] if candle_list else None

        # Current metrics
        body_bps = last.body_bps if last else 0.0
        range_bps = last.range_bps if last else 0.0
        c2c_bps = _close_to_close_bps(candle_list)
        leg3 = _leg_bps(candle_list, 3)
        leg5 = _leg_bps(candle_list, 5)
        eff3 = _directional_efficiency(candle_list, 3)
        eff5 = _directional_efficiency(candle_list, 5)
        pbr = _pullback_ratio(candle_list, 5)
        max_ext = _max_extension_bps(candle_list, 5)

        # Current percentile ranks
        rank_body = self._stats["body_bps"]["60"].rank(body_bps)
        rank_range = self._stats["range_bps"]["60"].rank(range_bps)
        rank_leg3 = self._stats["3c_leg_bps"]["60"].rank(leg3)
        rank_leg5 = self._stats["5c_leg_bps"]["60"].rank(leg5)

        # Shadow results
        shadow_map = {}
        for s in shadows:
            shadow_map[s.name] = {
                "pass": s.passed,
                "reason": s.reason,
                **s.metrics,
            }

        return {
            "timestamp": time.time(),
            "candles_evaluated": len(candle_list),
            "current_candle_time": last.time if last else None,

            # Production L3 status
            "production_l3_status": prod_status,
            "production_l3_block_reason": prod_reason,

            # Shadow variant results
            "shadow_3c_pass": shadow_map.get("shadow_3c", {}).get("pass", False),
            "shadow_stress_pass": shadow_map.get("shadow_stress", {}).get("pass", False),
            "shadow_single_candle_pass": shadow_map.get("shadow_single_candle", {}).get("pass", False),
            "shadow_5c_pass": shadow_map.get("shadow_5c", {}).get("pass", False),

            # Shadow detail
            "shadow_detail": shadow_map,

            # Current metrics
            "current": {
                "body_bps": round(body_bps, 2),
                "range_bps": round(range_bps, 2),
                "close_to_close_bps": round(c2c_bps, 2),
                "3c_leg_bps": round(leg3, 2),
                "5c_leg_bps": round(leg5, 2),
                "directional_efficiency_3c": round(eff3, 3),
                "directional_efficiency_5c": round(eff5, 3),
                "pullback_ratio": round(pbr, 3),
                "max_extension_bps": round(max_ext, 2),
                "volume_percentile": round(vol_pct, 3),
                "volatility_percentile": round(vol_rank, 3),
            },

            # Percentile ranks (0-1)
            "percentile_ranks": {
                "body_bps_rank_60": round(rank_body, 3),
                "range_bps_rank_60": round(rank_range, 3),
                "3c_leg_bps_rank_60": round(rank_leg3, 3),
                "5c_leg_bps_rank_60": round(rank_leg5, 3),
            },

            # Rolling percentile thresholds
            "percentile_thresholds": {
                metric: {
                    win: self._stats[metric][win].to_dict()
                    for win in self._stats[metric]
                }
                for metric in self._stats
            },

            # Interpretation
            "interpretation": interpretation,
        }

    def _build_interpretation(self, candles: list[Candle1m],
                              prod: dict, shadows: list[ShadowVariant],
                              vol_pct: float, vol_rank: float) -> str:
        """Build human-readable interpretation of current state."""
        if not candles:
            return "No candle data available."

        last = candles[-1]
        parts = []

        prod_pass = prod.get("pass", False)
        any_shadow = any(s.passed for s in shadows)
        shadow_pass_names = [s.name for s in shadows if s.passed]

        # Case 1: Production passes
        if prod_pass:
            parts.append("Production L3 PASSED.")
            if any_shadow:
                parts.append(f"Shadow variants also passing: {', '.join(shadow_pass_names)}.")
            return " ".join(parts)

        # Case 2: Production fails but shadow passes
        if any_shadow and not prod_pass:
            parts.append(
                f"Visible 1m displacement detected but production L3 failed. "
                f"Production reason: {prod.get('reason', 'unknown')}. "
                f"Shadow variants passing: {', '.join(shadow_pass_names)}."
            )
            # Diagnose why production failed
            body = last.body_bps
            if prod.get("reason", "").startswith("body_bps"):
                parts.append("Production L3 too strict vs 1m percentile displacement.")
            elif "15 bps" in prod.get("reason", ""):
                parts.append("Move below 15 bps hard floor but significant relative to recent history.")
            return " ".join(parts)

        # Case 3: Nothing passes — diagnose
        leg3 = _leg_bps(candles, 3)
        eff3 = _directional_efficiency(candles, 3)

        if leg3 < 5:
            parts.append("No meaningful 1m displacement.")
        elif eff3 < 0.4:
            parts.append("Move is choppy; efficiency too low for any variant.")
        elif vol_pct < 0.5:
            parts.append("Volume below median; move lacks participation.")
        else:
            # Check specific shadow failures
            for s in shadows:
                if not s.passed:
                    parts.append(f"{s.name}: {s.reason}.")
                    break  # just show first failure

        return " ".join(parts) if parts else "No displacement conditions met."

    def _log_shadow_event(self, candles: list[Candle1m],
                          prod: dict, shadows: list[ShadowVariant]):
        """Append to l3_shadow_events.jsonl when any shadow variant passes."""
        self._shadow_event_count += 1
        event = {
            "timestamp": time.time(),
            "candle_count": len(candles),
            "production_l3_status": prod["status"],
            "production_l3_reason": prod.get("reason", ""),
            "passing_variants": [s.name for s in shadows if s.passed],
            "current_metrics": candles[-1].to_dict() if candles else {},
            "shadow_details": {s.name: {"pass": s.passed, "reason": s.reason, **s.metrics} for s in shadows},
        }
        try:
            with open(self._shadow_events_path, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            logger.debug(f"L3 shadow event write error: {e}")

    def _persist_snapshot(self, result: dict):
        """Write latest snapshot to l3_live_shadow.json."""
        try:
            with open(self._shadow_json_path, "w") as f:
                json.dump(result, f, indent=2)
        except Exception as e:
            logger.debug(f"L3 shadow snapshot write error: {e}")

    def get_latest_candles(self, count: int = 5) -> list[dict]:
        """Get recent candles as dicts for API response."""
        candle_list = list(self._candles)
        return [c.to_dict() for c in candle_list[-count:]]

    @property
    def candle_count(self) -> int:
        return len(self._candles)
