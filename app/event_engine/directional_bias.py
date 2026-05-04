"""
MANTIS Event Engine — Directional Bias & Short Filter

Problem: MID SHORT trades underperform. Crypto has structural upward drift.
Current system fires sell-side events without checking if the broader
context supports a short. Result: shorting pullbacks in uptrends.

Solution: DirectionalBias layer that sits between detection and scoring.
Does NOT change detector logic — adds a post-detection filter and
score modifier.

Components:
  1. Short filter — gates whether a sell-side event should fire
  2. Directional multiplier — adjusts composite score based on
     regime + event direction alignment
  3. Long bias correction — reduces oversensitivity to buy signals
     during strong trends (catching falling knives vs riding trend)

Rules are structural, not tuned. Based on market mechanics:
  - Shorts work in: downtrend, exhaustion at high, failed breakout
  - Shorts fail in: uptrend pullbacks, compression at low
  - Longs work in: uptrend pullbacks, absorption at low, sweep of low
  - Longs fail in: downtrend rallies, exhaustion at high

SHADOW MODE: Blacklist/watchlist metadata is handled by the manager.
This module does NOT enforce blacklist. All events pass on directional merit.
"""

from app.event_engine.config import EventEngineConfig


class DirectionalBias:
    """
    Post-detection filter + score modifier for directional events.

    SHADOW MODE — Blacklist/Watchlist:
      - Blacklist/watchlist metadata is handled by the manager.
      - This filter does NOT block events based on blacklist status.
      - All events pass the directional filter on their own merits.
      - No score capping based on blacklist.
    """

    def __init__(self, config: EventEngineConfig):
        self.config = config

    def should_allow_event(self, event_type: str, side: str,
                           regime: str, regime_details: dict,
                           context) -> tuple[bool, str]:
        """
        Gate: should this event be allowed to fire?
        Directional filter only. No blacklist enforcement.
        """
        is_sell_side = self._is_sell_side(side)

        if not is_sell_side:
            return self._check_long_event(event_type, side, regime, regime_details, context)
        else:
            return self._check_short_event(event_type, side, regime, regime_details, context)
    
    def adjust_score(self, event_type: str, side: str,
                     regime: str, composite_score: float,
                     context) -> float:
        """
        Score modifier: adjust composite score based on directional alignment.
        No blacklist enforcement. All events scored on directional merit.
        """
        is_sell_side = self._is_sell_side(side)
        multiplier = 1.0
        
        # Regime alignment bonus/penalty
        if is_sell_side:
            if regime == "downtrend":
                multiplier *= 1.3  # shorts in downtrend = higher quality
            elif regime == "mild_down":
                multiplier *= 1.1
            elif regime == "uptrend":
                multiplier *= 0.6  # shorts in uptrend = lower quality
            elif regime == "mild_up":
                multiplier *= 0.8
        else:
            if regime == "uptrend":
                multiplier *= 1.2  # longs in uptrend = slightly better
            elif regime == "downtrend":
                multiplier *= 0.7  # longs in downtrend = lower quality
            elif regime == "mild_down":
                multiplier *= 0.85
        
        # Event-type specific adjustments
        multiplier *= self._event_type_multiplier(event_type, side, regime)
        
        # Clamp
        return max(0.5, min(1.5, composite_score * multiplier))
    
    def _check_short_event(self, event_type: str, side: str,
                           regime: str, regime_details: dict,
                           context) -> tuple[bool, str]:
        """
        Short filter: only allow sell-side events in supportive context.
        
        Must pass AT LEAST ONE of:
          1. Regime is bearish (downtrend or mild_down)
          2. Event is structural (exhaustion, absorption, failed breakout)
          3. Price is above VWAP and near session high (mean-reversion context)
        """
        # Rule 1: Bearish regime
        if regime in ("downtrend", "mild_down"):
            return True, f"short_allowed:bearish_regime={regime}"
        
        # Rule 2: Structural short events (always allowed in any regime)
        # NOTE: "exhaustion" excluded — forensic audit found sell_exhaustion
        # fires on selling climax (inverted logic). Not structurally sound.
        structural_short_events = {
            "absorption",      # sell_absorption = buy aggression absorbed
            "liquidity_sweep", # high_sweep = stop hunt, reversal
            "delta_divergence", # bearish_divergence = price up, CVD flat
        }
        if event_type in structural_short_events:
            return True, f"short_allowed:structural_event={event_type}"
        
        # Rule 3: Mean-reversion context (price extended above VWAP)
        if hasattr(context, 'session') and context.session.vwap > 0:
            price = context.buffer.last_price
            vwap = context.session.vwap
            vwap_dist_bps = ((price - vwap) / vwap * 10000) if vwap > 0 else 0
            
            # Only allow non-structural shorts if price is significantly above VWAP
            # This catches exhaustion at highs, not pullbacks
            if vwap_dist_bps > 15:  # 15 bps above VWAP
                session_high = context.session.session_high
                if session_high > 0:
                    dist_to_high_bps = ((session_high - price) / session_high * 10000)
                    if dist_to_high_bps < 10:  # within 10 bps of session high
                        return True, f"short_allowed:extended_above_vwap={vwap_dist_bps:.0f}bps"
        
        # Default: suppress short event
        return False, f"short_suppressed:regime={regime},type={event_type}"
    
    def _check_long_event(self, event_type: str, side: str,
                          regime: str, regime_details: dict,
                          context) -> tuple[bool, str]:
        """
        Long filter: less restrictive than short filter.
        
        Suppress longs only when:
          - Strong downtrend AND event is weak (imbalance only)
          - Price extended to session high (buying the top)
        """
        # In strong downtrend, suppress weak long events
        if regime == "downtrend" and event_type == "imbalance":
            return False, f"long_suppressed:downtrend_imbalance"
        
        # Check if buying at session high (potential exhaustion)
        if hasattr(context, 'session') and context.session.session_high > 0:
            price = context.buffer.last_price
            session_high = context.session.session_high
            dist_to_high_bps = ((session_high - price) / session_high * 10000)
            
            # If within 3 bps of session high and event is imbalance (weak signal)
            if dist_to_high_bps < 3 and event_type == "imbalance":
                return False, f"long_suppressed:near_session_high"
        
        return True, "long_allowed"
    
    def _event_type_multiplier(self, event_type: str, side: str, regime: str) -> float:
        """
        Event-type specific score multiplier.
        
        Based on structural reliability:
          - Absorption, exhaustion, sweep = higher reliability (structural)
          - Imbalance = lower reliability (can be noise)
          - Divergence = medium reliability (needs confirmation)
        """
        reliability = {
            "absorption": 1.15,
            "exhaustion": 1.10,
            "liquidity_sweep": 1.15,
            "range_break": 1.05,
            "vwap_reaction": 1.00,
            "delta_divergence": 0.95,
            "imbalance": 0.85,
            "large_trade_cluster": 0.90,
        }
        return reliability.get(event_type, 1.0)
    
    def _is_sell_side(self, side: str) -> bool:
        """Check if event side is sell-side / bearish."""
        sell_keywords = ["sell", "bearish", "high_sweep", "down_break", "above_vwap"]
        return any(kw in side.lower() for kw in sell_keywords)
