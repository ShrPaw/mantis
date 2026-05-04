"""
MANTIS Event Engine — Improved Regime Classification

Problem: Current classify_regime() uses 60-tick absolute range.
With BTC at $78k, the 0.3% threshold = $235, which covers the
entire intraday range. Result: 100% "low_volatility" classification.
Every event gets regime_score=0.4. The regime pathway is dead.

Solution: Multi-timeframe relative volatility + trend detection.
Uses percentile-based thresholds that adapt to current conditions.

Regime types:
  compression  — volatility below recent median, tight range
  expansion    — volatility above recent median, wide range
  uptrend      — directional bias up (CVD + price structure)
  downtrend    — directional bias down (CVD + price structure)

NO ML. NO curve fitting. Pure percentile + slope logic.
"""

import time
from collections import deque
from typing import Optional


class RegimeClassifier:
    """
    Replaces EngineContext.classify_regime() with multi-signal regime detection.
    
    Inputs (from existing EngineContext):
      - buffer._prices  (tick-level)
      - buffer._deltas  (tick-level)
      - buffer._cvd_values  (tick-level)
      - buffer._timestamps  (tick-level)
      - session.vwap, session_high, session_low
    
    Output:
      - regime: str  ("compression", "expansion", "uptrend", "downtrend", "unknown")
      - regime_details: dict  (all intermediate values for logging)
    """
    
    def __init__(self):
        # Rolling history of realized volatility for percentile ranking
        # Stores (timestamp, rv_value) pairs
        self._rv_history: deque = deque(maxlen=500)
        self._last_regime: str = "unknown"
        self._regime_duration: int = 0  # ticks in current regime
    
    def classify(self, buffer, session, now: float) -> tuple[str, dict]:
        """
        Main entry point. Returns (regime_string, details_dict).
        
        Uses three orthogonal signals:
          1. Volatility regime (compression vs expansion)
          2. Directional bias (trend detection)
          3. Price position relative to session structure
        """
        details = {}
        
        # Need minimum data
        if buffer.count < 50:
            return "unknown", {"reason": "insufficient_data", "count": buffer.count}
        
        # --- Signal 1: Volatility regime ---
        vol_signal, vol_details = self._volatility_signal(buffer, now)
        details["volatility"] = vol_details
        
        # --- Signal 2: Directional bias ---
        dir_signal, dir_details = self._directional_signal(buffer, session, now)
        details["direction"] = dir_details
        
        # --- Signal 3: Range position ---
        range_signal, range_details = self._range_position_signal(buffer, session, now)
        details["range"] = range_details
        
        # --- Combine signals ---
        regime = self._combine_signals(vol_signal, dir_signal, range_signal)
        details["regime"] = regime
        
        # Track regime duration
        if regime == self._last_regime:
            self._regime_duration += 1
        else:
            self._regime_duration = 1
            self._last_regime = regime
        
        details["regime_duration"] = self._regime_duration
        
        return regime, details
    
    def _volatility_signal(self, buffer, now: float) -> tuple[str, dict]:
        """
        Compute realized volatility at multiple horizons and rank
        against recent history. Uses RATIO of short:long rv to detect
        compression/expansion independent of absolute price level.
        
        Key insight: absolute rv is meaningless for BTC ($78k).
        The RATIO between timeframes is regime-dependent:
          - compression: short rv < long rv (mean-reverting)
          - expansion:   short rv > long rv (trending/breakout)
        """
        # Compute rv at 30s, 60s, 300s windows
        rv_30s = self._realized_vol(buffer, 30, now)
        rv_60s = self._realized_vol(buffer, 60, now)
        rv_300s = self._realized_vol(buffer, 300, now)
        
        details = {
            "rv_30s": rv_30s,
            "rv_60s": rv_60s,
            "rv_300s": rv_300s,
        }
        
        if rv_300s <= 0:
            return "unknown", {**details, "reason": "rv_300s_zero"}
        
        # Ratio: short-term vs long-term volatility
        ratio_short_long = rv_30s / rv_300s
        ratio_mid_long = rv_60s / rv_300s
        details["ratio_30s_300s"] = ratio_short_long
        details["ratio_60s_300s"] = ratio_mid_long
        
        # Store for percentile ranking
        self._rv_history.append((now, ratio_short_long))
        
        # Percentile rank of current ratio vs recent history
        percentile = self._percentile_rank(ratio_short_long)
        details["rv_percentile"] = percentile
        
        # Classify
        if percentile < 0.30:
            return "compression", details
        elif percentile > 0.70:
            return "expansion", details
        else:
            return "normal", details
    
    def _directional_signal(self, buffer, session, now: float) -> tuple[str, dict]:
        """
        Detect directional bias using CVD slope + price structure.
        
        Uses two timeframes:
          - Fast: 60s CVD slope (current aggression direction)
          - Slow: 300s CVD slope (structural direction)
        
        Agreement between timeframes = strong signal.
        Disagreement = choppy/transitional.
        """
        # CVD slope over 60s (fast)
        cvd_fast = buffer.get_cvd_window(60, now)
        cvd_slope_fast = self._slope(cvd_fast) if len(cvd_fast) >= 5 else 0
        
        # CVD slope over 300s (slow)
        cvd_slow = buffer.get_cvd_window(300, now)
        cvd_slope_slow = self._slope(cvd_slow) if len(cvd_slow) >= 10 else 0
        
        # Price slope over same windows
        prices_60, _, _, _ = buffer.get_window(60, now)
        prices_300, _, _, _ = buffer.get_window(300, now)
        price_slope_fast = self._slope(prices_60) if len(prices_60) >= 5 else 0
        price_slope_slow = self._slope(prices_300) if len(prices_300) >= 10 else 0
        
        # Normalize slopes to bps per minute for interpretability
        avg_price = buffer.last_price if buffer.last_price > 0 else 78000
        cvd_fast_bps = (cvd_slope_fast * 60 / avg_price) * 10000 if avg_price > 0 else 0
        cvd_slow_bps = (cvd_slope_slow * 60 / avg_price) * 10000 if avg_price > 0 else 0
        price_fast_bps = (price_slope_fast * 60 / avg_price) * 10000 if avg_price > 0 else 0
        price_slow_bps = (price_slope_slow * 60 / avg_price) * 10000 if avg_price > 0 else 0
        
        details = {
            "cvd_slope_fast_bps_min": cvd_fast_bps,
            "cvd_slope_slow_bps_min": cvd_slow_bps,
            "price_slope_fast_bps_min": price_fast_bps,
            "price_slope_slow_bps_min": price_slow_bps,
        }
        
        # Direction thresholds (bps/min)
        # These are structural, not tuned — just need to distinguish
        # "clearly going up" from "clearly going down" from "flat"
        STRONG = 5.0   # 5 bps/min = clear direction
        WEAK = 1.5     # below this = no clear direction
        
        # Check CVD alignment
        cvd_direction = "flat"
        if cvd_fast_bps > STRONG and cvd_slow_bps > WEAK:
            cvd_direction = "buying"
        elif cvd_fast_bps < -STRONG and cvd_slow_bps < -WEAK:
            cvd_direction = "selling"
        
        # Check price alignment
        price_direction = "flat"
        if price_fast_bps > STRONG and price_slow_bps > WEAK:
            price_direction = "up"
        elif price_fast_bps < -STRONG and price_slow_bps < -WEAK:
            price_direction = "down"
        
        details["cvd_direction"] = cvd_direction
        details["price_direction"] = price_direction
        
        # Combined directional signal
        if cvd_direction == "buying" and price_direction == "up":
            return "uptrend", details
        elif cvd_direction == "selling" and price_direction == "down":
            return "downtrend", details
        elif cvd_direction == "buying" and price_direction != "down":
            return "mild_up", details
        elif cvd_direction == "selling" and price_direction != "up":
            return "mild_down", details
        else:
            return "neutral", details
    
    def _range_position_signal(self, buffer, session, now: float) -> tuple[str, dict]:
        """
        Where is price relative to session range?
        
        This is structural context that affects event quality:
          - Buying at session high = potentially exhaustion
          - Selling at session low = potentially exhaustion
          - Buying at session low = potentially continuation
          - Selling at session high = potentially continuation
        """
        price = buffer.last_price
        if price <= 0:
            return "unknown", {"reason": "no_price"}
        
        session_high = session.session_high
        session_low = session.session_low_safe
        vwap = session.vwap
        
        if session_high <= session_low:
            return "unknown", {"reason": "no_range"}
        
        range_height = session_high - session_low
        position_in_range = (price - session_low) / range_height if range_height > 0 else 0.5
        
        # Distance to VWAP in bps
        vwap_dist_bps = ((price - vwap) / vwap * 10000) if vwap > 0 else 0
        
        details = {
            "session_high": session_high,
            "session_low": session_low,
            "vwap": vwap,
            "position_in_range": position_in_range,
            "vwap_dist_bps": vwap_dist_bps,
        }
        
        # Classify position
        if position_in_range > 0.85:
            position = "near_high"
        elif position_in_range < 0.15:
            position = "near_low"
        elif abs(vwap_dist_bps) < 5:
            position = "at_vwap"
        else:
            position = "mid_range"
        
        details["position"] = position
        return position, details
    
    def _combine_signals(self, vol: str, dir: str, range_pos: str) -> str:
        """
        Combine the three orthogonal signals into a single regime.
        
        Priority: direction > volatility > range position.
        Direction is the strongest signal for trade filtering.
        Volatility sets the context (compression = wait, expansion = act).
        Range position modifies event interpretation.
        """
        # Primary: directional bias
        if dir in ("uptrend", "downtrend"):
            return dir
        
        # Secondary: volatility regime
        if vol == "compression":
            return "compression"
        if vol == "expansion":
            return "expansion"
        
        # Tertiary: mild direction
        if dir in ("mild_up", "mild_down"):
            return dir
        
        return "neutral"
    
    def _realized_vol(self, buffer, window_seconds: float, now: float) -> float:
        """
        Compute realized volatility from tick-level returns.
        Annualized not needed — we use raw for relative comparison.
        """
        prices, _, _, timestamps = buffer.get_window(window_seconds, now)
        if len(prices) < 5:
            return 0.0
        
        # Compute log returns
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                returns.append((prices[i] - prices[i-1]) / prices[i-1])
        
        if not returns:
            return 0.0
        
        # Standard deviation of returns (scaled for visibility)
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / len(returns)
        return var ** 0.5 * 10000  # in bps
    
    def _slope(self, values: list) -> float:
        """
        Simple linear regression slope.
        Returns units per second.
        """
        n = len(values)
        if n < 2:
            return 0.0
        
        # Use indices as x (assuming uniform spacing)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        
        num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        den = sum((i - x_mean) ** 2 for i in range(n))
        
        if den == 0:
            return 0.0
        return num / den
    
    def _percentile_rank(self, value: float) -> float:
        """Rank value against recent history."""
        if not self._rv_history:
            return 0.5
        
        values = [v for _, v in self._rv_history]
        below = sum(1 for v in values if v < value)
        return below / len(values) if values else 0.5
