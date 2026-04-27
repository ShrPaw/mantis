"""
MANTIS Event Engine — Re-scoring Script

Re-scores all collected events using the improved regime classifier,
confidence engine, and directional bias. Does NOT modify original data.
Outputs a new JSONL with updated scores for comparison.

Usage:
    python3 scripts/rescore_events.py \
        --input backend/data/events/events_raw.jsonl \
        --output backend/data/events/events_rescored.jsonl

This allows comparing:
  Original composite_score vs new composite_score
  Original regime vs new regime
  Events suppressed by directional filter
"""

import json
import sys
import os
import argparse
from collections import defaultdict

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from event_engine.regime import RegimeClassifier
from event_engine.confidence import ConfidenceEngine
from event_engine.directional_bias import DirectionalBias
from event_engine.config import EventEngineConfig
from event_engine.context import RollingBuffer, SessionState


def rebuild_context(events: list[dict]):
    """
    Rebuild a minimal EngineContext from event sequence.
    We don't have raw trades, but we can reconstruct approximate
    regime from the event sequence itself.
    """
    config = EventEngineConfig()
    regime_clf = RegimeClassifier()
    conf_eng = ConfidenceEngine()
    bias = DirectionalBias(config)
    
    return config, regime_clf, conf_eng, bias


def estimate_regime_from_events(events: list[dict], idx: int, regime_clf: RegimeClassifier) -> str:
    """
    Estimate regime at time of event using price sequence.
    
    We use the events themselves as a sparse price series.
    Not perfect, but sufficient for re-scoring comparison.
    """
    # Look at prices from events in a window around this event
    ts = events[idx]["timestamp"]
    lookback = 300  # 5 minutes
    
    prices = []
    for i in range(max(0, idx - 50), idx + 1):
        if events[i]["timestamp"] >= ts - lookback:
            prices.append(events[i]["price"])
    
    if len(prices) < 5:
        return "unknown"
    
    # Simple volatility-based regime from price series
    returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices)) if prices[i-1] > 0]
    if not returns:
        return "unknown"
    
    import math
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / len(returns)
    rv = math.sqrt(var) * 10000  # bps
    
    # Direction from CVD-like metric (use delta from events)
    recent_deltas = []
    for i in range(max(0, idx - 10), idx + 1):
        rm = events[i].get("raw_metrics", {})
        d = rm.get("delta", rm.get("total_delta", 0))
        recent_deltas.append(d)
    
    cvd_trend = sum(recent_deltas) if recent_deltas else 0
    
    # Classify
    if rv < 3:
        base = "compression"
    elif rv > 15:
        base = "expansion"
    else:
        base = "neutral"
    
    # Overlay direction
    if cvd_trend > 2:
        return "uptrend" if base != "compression" else "mild_up"
    elif cvd_trend < -2:
        return "downtrend" if base != "compression" else "mild_down"
    
    return base


def rescore_events(input_path: str, output_path: str):
    """Re-score all events with improved engines."""
    
    # Load events
    events = []
    with open(input_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    
    print(f"Loaded {len(events)} events from {input_path}")
    
    config, regime_clf, conf_eng, bias = rebuild_context(events)
    
    # Stats
    stats = {
        "total": len(events),
        "regime_changes": 0,
        "suppressed": 0,
        "score_increased": 0,
        "score_decreased": 0,
        "score_unchanged": 0,
    }
    
    by_type = defaultdict(lambda: {"original_avg": 0, "new_avg": 0, "count": 0, "suppressed": 0})
    by_side = defaultdict(lambda: {"original_avg": 0, "new_avg": 0, "count": 0, "suppressed": 0})
    regime_distribution = defaultdict(int)
    
    rescored = []
    
    for i, event in enumerate(events):
        event_type = event["event_type"]
        side = event["side"]
        original_score = event["scores"]["composite_score"]
        original_regime = event.get("context_metrics", {}).get("regime", "unknown")
        
        # Estimate regime
        regime = estimate_regime_from_events(events, i, regime_clf)
        regime_distribution[regime] += 1
        
        if regime != original_regime:
            stats["regime_changes"] += 1
        
        # Check directional filter
        # Build a minimal context-like object
        class MiniBuffer:
            def __init__(self, price):
                self.last_price = price
                self._timestamps = []
            def get_cvd_window(self, *a):
                return []
        class MiniContext:
            def __init__(self, price, vwap, session_high, session_low):
                self.buffer = MiniBuffer(price)
                self.session = type('sess', (), {
                    'vwap': vwap,
                    'session_high': session_high,
                    'session_low_safe': session_low,
                })()
        
        price = event["price"]
        # Approximate session values from event data
        vwap = event.get("vwap", price)
        session_high = max(e["price"] for e in events[:i+1]) if i > 0 else price
        session_low = min(e["price"] for e in events[:i+1]) if i > 0 else price
        
        ctx = MiniContext(price, vwap, session_high, session_low)
        
        allowed, reason = bias.should_allow_event(event_type, side, regime, {}, ctx)
        
        if not allowed:
            stats["suppressed"] += 1
            by_type[event_type]["suppressed"] += 1
            by_side[side]["suppressed"] += 1
            # Mark but keep in output
            event["rescored"] = {
                "suppressed": True,
                "suppression_reason": reason,
                "regime": regime,
            }
            rescored.append(event)
            continue
        
        # Re-score confidence with new engine
        conf_result = conf_eng.score(
            event_type=event_type,
            side=side,
            regime=regime,
            price=price,
            buffer=ctx.buffer,
            session=ctx.session,
        )
        
        # Use ORIGINAL strength and noise, REPLACE confidence
        strength_score = event["scores"]["strength_score"]
        noise_score = event["scores"]["noise_score"]
        original_confidence = event["scores"]["confidence_score"]
        
        new_confidence = conf_result["confidence_score"]
        
        # NEW additive formula (replaces multiplicative compression)
        # Quality = weighted average of components, penalized by noise
        # Range: roughly 0.1 to 0.9, better spread than multiplicative
        quality = (strength_score * 0.40 + new_confidence * 0.40 + (1 - noise_score) * 0.20)
        quality = max(0, min(1, quality))
        
        # Apply directional bias multiplier on top
        new_composite = bias.adjust_score(event_type, side, regime, quality, ctx)
        new_composite = max(0, min(1, new_composite))
        
        # Also compute original formula for comparison
        original_formula = strength_score * original_confidence * (1.0 - noise_score * 0.5)
        
        # Track stats
        diff = new_composite - original_score
        if diff > 0.01:
            stats["score_increased"] += 1
        elif diff < -0.01:
            stats["score_decreased"] += 1
        else:
            stats["score_unchanged"] += 1
        
        by_type[event_type]["original_avg"] += original_score
        by_type[event_type]["new_avg"] += new_composite
        by_type[event_type]["count"] += 1
        
        by_side[side]["original_avg"] += original_score
        by_side[side]["new_avg"] += new_composite
        by_side[side]["count"] += 1
        
        # Store rescored data
        event["rescored"] = {
            "suppressed": False,
            "regime": regime,
            "original_regime": original_regime,
            "original_composite": original_score,
            "original_formula_check": round(original_formula, 4),
            "new_composite": round(new_composite, 4),
            "new_confidence": round(new_confidence, 4),
            "original_confidence": round(original_confidence, 4),
            "confidence_change": round(new_confidence - original_confidence, 4),
            "strength_preserved": round(strength_score, 4),
            "noise_preserved": round(noise_score, 4),
            "quality_score": round(quality, 4),
            "confidence_components": {k: round(v, 4) for k, v in conf_result["confidence_components"].items()},
            "confidence_explanation": conf_result["explanation"],
            "directional_multiplier": round(new_composite / max(quality, 0.0001), 4),
            "score_change": round(diff, 4),
        }
        rescored.append(event)
    
    # Write output
    with open(output_path, 'w') as f:
        for event in rescored:
            f.write(json.dumps(event) + '\n')
    
    # Print report
    print(f"\n{'='*60}")
    print("RE-SCORING REPORT")
    print(f"{'='*60}")
    print(f"\nTotal events: {stats['total']}")
    print(f"Regime changes: {stats['regime_changes']} ({stats['regime_changes']/stats['total']*100:.0f}%)")
    print(f"Suppressed by directional filter: {stats['suppressed']}")
    print(f"Score increased: {stats['score_increased']}")
    print(f"Score decreased: {stats['score_decreased']}")
    print(f"Score unchanged: {stats['score_unchanged']}")
    
    print(f"\n--- REGIME DISTRIBUTION ---")
    for r, c in sorted(regime_distribution.items(), key=lambda x: -x[1]):
        print(f"  {r:20s} {c:>4d} ({c/stats['total']*100:.0f}%)")
    
    print(f"\n--- BY EVENT TYPE ---")
    for t, d in sorted(by_type.items(), key=lambda x: -x[1]["count"]):
        n = d["count"]
        if n > 0:
            orig_avg = d["original_avg"] / n
            new_avg = d["new_avg"] / n
            print(f"  {t:25s}  n={n:>3d}  orig={orig_avg:.4f}  new={new_avg:.4f}  "
                  f"Δ={new_avg-orig_avg:+.4f}  suppressed={d['suppressed']}")
    
    print(f"\n--- BY SIDE ---")
    for s, d in sorted(by_side.items(), key=lambda x: -x[1]["count"]):
        n = d["count"]
        if n > 0:
            orig_avg = d["original_avg"] / n
            new_avg = d["new_avg"] / n
            print(f"  {s:30s}  n={n:>3d}  orig={orig_avg:.4f}  new={new_avg:.4f}  "
                  f"Δ={new_avg-orig_avg:+.4f}  suppressed={d['suppressed']}")
    
    print(f"\nOutput written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="MANTIS Re-scoring")
    parser.add_argument("--input", default="backend/data/events/events_raw.jsonl")
    parser.add_argument("--output", default="backend/data/events/events_rescored.jsonl")
    args = parser.parse_args()
    
    rescore_events(args.input, args.output)


if __name__ == "__main__":
    main()
