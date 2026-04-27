"""
MANTIS Event Engine — Improved Confidence Engine

Problem: Current confidence score has a dead component (regime=0.4 for all events).
The confidence_weights sum to 1.0, so regime contributes 30% of confidence,
but it's a constant 0.4 → effectively just a scaling artifact.

Solution: Replace the flat regime component with actual regime-event alignment.
Add new components:
  1. regime_alignment — does the regime support this event direction?
  2. structural_proximity — is price near a structural level (VWAP, session H/L)?
  3. flow_consistency — does recent CVD agree with event direction?
  4. event_reliability — historical reliability of this event type

All components are 0-1 and explainable. No ML, no overfitting.
"""


class ConfidenceEngine:
    """
    Computes regime-aware confidence scores.
    
    Components (each 0-1):
      regime_alignment:     Does regime support this direction?
      structural_proximity: Is price near a structural level?
      flow_consistency:     Does CVD agree with event direction?
      event_reliability:    Base reliability of event type
    
    Weights: 0.30, 0.25, 0.25, 0.20 (sum=1.0)
    """
    
    # Event type base reliability (structural, not tuned)
    # Based on market mechanics:
    #   absorption/exhaustion = direct observation of order flow failure
    #   sweep = observable liquidity grab
    #   imbalance = weaker signal, more noise-prone
    EVENT_RELIABILITY = {
        "absorption": 0.75,
        "exhaustion": 0.70,
        "liquidity_sweep": 0.75,
        "range_break": 0.65,
        "vwap_reaction": 0.60,
        "delta_divergence": 0.55,
        "imbalance": 0.45,
        "large_trade_cluster": 0.50,
    }
    
    # Regime-event alignment matrix
    # (regime, event_direction) → alignment score
    # Based on: when does this event type work?
    REGIME_ALIGNMENT = {
        # Uptrend: longs supported, shorts need structural justification
        ("uptrend", "long"): 0.80,
        ("uptrend", "short"): 0.30,
        ("mild_up", "long"): 0.70,
        ("mild_up", "short"): 0.40,
        # Downtrend: shorts supported, longs risky
        ("downtrend", "long"): 0.30,
        ("downtrend", "short"): 0.80,
        ("mild_down", "long"): 0.40,
        ("mild_down", "short"): 0.70,
        # Neutral/compression: both directions possible but lower conviction
        ("compression", "long"): 0.55,
        ("compression", "short"): 0.55,
        ("expansion", "long"): 0.60,
        ("expansion", "short"): 0.60,
        ("neutral", "long"): 0.50,
        ("neutral", "short"): 0.50,
        ("unknown", "long"): 0.40,
        ("unknown", "short"): 0.40,
    }
    
    WEIGHTS = {
        "regime_alignment": 0.30,
        "structural_proximity": 0.25,
        "flow_consistency": 0.25,
        "event_reliability": 0.20,
    }

    # Blacklisted event types: reliability capped at this value
    # These events are structurally unsound per forensic audit
    BLACKLISTED_TYPES = {"exhaustion"}  # sell_exhaustion specifically
    BLACKLISTED_RELIABILITY_CAP = 0.10

    def score(self, event_type: str, side: str, regime: str,
              price: float, buffer, session) -> dict:
        """
        Compute confidence score and components.
        
        Returns dict with:
          confidence_score: float (0-1)
          confidence_components: dict of component scores
          explanation: str
        """
        direction = "short" if self._is_sell_side(side) else "long"
        
        # Component 1: Regime alignment
        regime_align = self.REGIME_ALIGNMENT.get((regime, direction), 0.40)
        
        # Component 2: Structural proximity
        struct_prox = self._structural_proximity(price, buffer, session, direction)
        
        # Component 3: Flow consistency
        flow_consist = self._flow_consistency(buffer, direction)
        
        # Component 4: Event reliability
        # BLACKLIST enforcement: sell_exhaustion gets capped reliability
        is_sell = self._is_sell_side(side)
        if is_sell and event_type in self.BLACKLISTED_TYPES:
            event_rel = self.BLACKLISTED_RELIABILITY_CAP
        else:
            event_rel = self.EVENT_RELIABILITY.get(event_type, 0.50)
        
        components = {
            "regime_alignment": regime_align,
            "structural_proximity": struct_prox,
            "flow_consistency": flow_consist,
            "event_reliability": event_rel,
        }
        
        # Weighted sum
        score = sum(
            components[k] * self.WEIGHTS[k]
            for k in self.WEIGHTS
        )
        score = max(0.0, min(1.0, score))
        
        explanation = (
            f"regime={regime_align:.2f} "
            f"(regime={regime},dir={direction}) | "
            f"struct={struct_prox:.2f} | "
            f"flow={flow_consist:.2f} | "
            f"reliability={event_rel:.2f} ({event_type})"
        )
        
        return {
            "confidence_score": score,
            "confidence_components": components,
            "explanation": explanation,
        }
    
    def _structural_proximity(self, price: float, buffer, session,
                               direction: str) -> float:
        """
        Is price near a structural level?
        
        Structural levels:
          - Session high / low
          - VWAP
          - Recent range boundaries
        
        Being near a structural level increases confidence because:
          - Stops can be placed on the other side of the level
          - Level acts as support/resistance
          - Clear invalidation point
        """
        if price <= 0:
            return 0.3
        
        distances = []
        
        # VWAP distance
        if session.vwap > 0:
            vwap_dist = abs(price - session.vwap) / session.vwap * 10000
            distances.append(min(vwap_dist / 20.0, 1.0))  # 20 bps = max distance
        
        # Session high distance
        if session.session_high > 0:
            high_dist = abs(price - session.session_high) / session.session_high * 10000
            distances.append(min(high_dist / 20.0, 1.0))
        
        # Session low distance
        if session.session_low_safe > 0:
            low_dist = abs(price - session.session_low_safe) / session.session_low_safe * 10000
            distances.append(min(low_dist / 20.0, 1.0))
        
        if not distances:
            return 0.3
        
        # Closer to any structural level = higher score
        min_distance = min(distances)
        # Invert: closer = better
        proximity = max(0, 1.0 - min_distance)
        
        return proximity
    
    def _flow_consistency(self, buffer, direction: str) -> float:
        """
        Does recent CVD agree with the event direction?
        
        CVD (Cumulative Volume Delta) shows net aggressive pressure.
        If CVD is rising and event is long → consistent.
        If CVD is rising and event is short → inconsistent.
        """
        cvd_30s = buffer.get_cvd_window(30, buffer._timestamps[-1] if buffer._timestamps else 0)
        
        if len(cvd_30s) < 3:
            return 0.5  # neutral if insufficient data
        
        # CVD slope
        cvd_change = cvd_30s[-1] - cvd_30s[0]
        
        if direction == "long":
            if cvd_change > 0:
                return 0.7 + min(cvd_change / 5.0, 0.3)  # buying pressure confirms long
            else:
                return 0.5 - min(abs(cvd_change) / 10.0, 0.3)  # selling pressure contradicts
        else:  # short
            if cvd_change < 0:
                return 0.7 + min(abs(cvd_change) / 5.0, 0.3)  # selling pressure confirms short
            else:
                return 0.5 - min(cvd_change / 10.0, 0.3)  # buying pressure contradicts
    
    def _is_sell_side(self, side: str) -> bool:
        sell_keywords = ["sell", "bearish", "high_sweep", "down_break", "above_vwap"]
        return any(kw in side.lower() for kw in sell_keywords)
