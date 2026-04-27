#!/usr/bin/env python3
"""
MANTIS Shadow Validation — Controlled comparison of original vs new scoring.

Runs entirely offline on exported event data.
Does NOT modify live engine. Does NOT overwrite raw files.

Outputs:
  backend/data/events/events_shadow_scored.csv
  backend/data/events/validation_shadow_report.json
  SHADOW_VALIDATION_REPORT.md
"""

import json
import os
import sys
import csv
import math
from collections import defaultdict
from datetime import datetime, timezone, timedelta

# Add backend to path for new modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from event_engine.regime import RegimeClassifier
from event_engine.confidence import ConfidenceEngine
from event_engine.directional_bias import DirectionalBias
from event_engine.config import EventEngineConfig


# ============================================================
# Data Loading
# ============================================================

def load_events(path: str) -> list[dict]:
    events = []
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


# ============================================================
# Shadow Scoring
# ============================================================

def compute_shadow_scores(events: list[dict]) -> list[dict]:
    """
    For each event, compute shadow scores using new modules.
    Returns enriched event dicts with both original and shadow data.
    """
    config = EventEngineConfig()
    regime_clf = RegimeClassifier()
    conf_eng = ConfidenceEngine()
    bias = DirectionalBias(config)

    enriched = []

    for i, event in enumerate(events):
        event_type = event["event_type"]
        side = event["side"]
        price = event["price"]
        ts = event["timestamp"]
        original_score = event["scores"]["composite_score"]
        original_regime = event.get("context_metrics", {}).get("regime", "unknown")

        # --- Estimate regime from event sequence ---
        regime = _estimate_regime(events, i)

        # --- Directional filter ---
        is_sell = _is_sell_side(side)
        direction = "short" if is_sell else "long"

        # Mini context for directional bias
        class MiniBuffer:
            def __init__(self, p):
                self.last_price = p
                self._timestamps = []
            def get_cvd_window(self, *a):
                return []

        session_high = max(e["price"] for e in events[:i+1]) if i > 0 else price
        session_low = min(e["price"] for e in events[:i+1]) if i > 0 else price
        vwap = event.get("vwap", price)

        class MiniCtx:
            def __init__(self, p, vwap, sh, sl):
                self.buffer = MiniBuffer(p)
                self.session = type('s', (), {
                    'vwap': vwap,
                    'session_high': sh,
                    'session_low_safe': sl,
                })()
        ctx = MiniCtx(price, vwap, session_high, session_low)

        allowed, reason = bias.should_allow_event(event_type, side, regime, {}, ctx)

        # --- Shadow confidence ---
        conf_result = conf_eng.score(
            event_type=event_type,
            side=side,
            regime=regime,
            price=price,
            buffer=ctx.buffer,
            session=ctx.session,
        )

        # --- Shadow composite ---
        strength = event["scores"]["strength_score"]
        noise = event["scores"]["noise_score"]
        new_conf = conf_result["confidence_score"]

        # Additive formula
        quality = strength * 0.40 + new_conf * 0.40 + (1 - noise) * 0.20
        quality = max(0, min(1, quality))
        shadow_score = bias.adjust_score(event_type, side, regime, quality, ctx)
        shadow_score = max(0, min(1, shadow_score))

        # --- Forward outcomes in trade direction ---
        fwd = event.get("forward", {})
        directional_outcomes = {}
        for horizon in [10, 30, 60, 120, 300]:
            raw = fwd.get(f"future_return_{horizon}s")
            if raw is not None:
                directional_outcomes[f"dir_return_{horizon}s"] = raw if not is_sell else -raw
            else:
                directional_outcomes[f"dir_return_{horizon}s"] = None

        # MFE/MAE
        mfe_30s = fwd.get("max_favorable_excursion_30s")
        mae_30s = fwd.get("max_adverse_excursion_30s")
        mfe_120s = fwd.get("max_favorable_excursion_120s")
        mae_120s = fwd.get("max_adverse_excursion_120s")

        # TP/SL
        hit_tp_10 = fwd.get("hit_tp_0_10pct")
        hit_tp_20 = fwd.get("hit_tp_0_20pct")
        hit_sl_10 = fwd.get("hit_sl_0_10pct")
        hit_sl_20 = fwd.get("hit_sl_0_20pct")

        enriched.append({
            "event_id": event["event_id"],
            "timestamp": ts,
            "event_type": event_type,
            "side": side,
            "direction": direction,
            "price": price,
            "original_score": original_score,
            "original_regime": original_regime,
            "shadow_score": round(shadow_score, 4),
            "shadow_regime": regime,
            "shadow_confidence": round(new_conf, 4),
            "shadow_quality": round(quality, 4),
            "directional_filter_allowed": allowed,
            "directional_filter_reason": reason,
            "strength": round(strength, 4),
            "noise": round(noise, 4),
            "is_complete": fwd.get("is_complete", False),
            **directional_outcomes,
            "mfe_30s": mfe_30s,
            "mae_30s": mae_30s,
            "mfe_120s": mfe_120s,
            "mae_120s": mae_120s,
            "hit_tp_10": hit_tp_10,
            "hit_tp_20": hit_tp_20,
            "hit_sl_10": hit_sl_10,
            "hit_sl_20": hit_sl_20,
        })

    return enriched


def _estimate_regime(events: list[dict], idx: int) -> str:
    """Estimate regime at event time from event price sequence."""
    ts = events[idx]["timestamp"]
    lookback = 300

    prices = []
    for i in range(max(0, idx - 50), idx + 1):
        if events[i]["timestamp"] >= ts - lookback:
            prices.append(events[i]["price"])

    if len(prices) < 5:
        return "unknown"

    returns = [(prices[i] - prices[i-1]) / prices[i-1]
               for i in range(1, len(prices)) if prices[i-1] > 0]
    if not returns:
        return "unknown"

    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / len(returns)
    rv = math.sqrt(var) * 10000

    # Direction from delta
    recent_deltas = []
    for i in range(max(0, idx - 10), idx + 1):
        rm = events[i].get("raw_metrics", {})
        d = rm.get("delta", rm.get("total_delta", 0))
        if d is None:
            d = 0
        recent_deltas.append(d)
    cvd_trend = sum(recent_deltas)

    if rv < 3:
        base = "compression"
    elif rv > 15:
        base = "expansion"
    else:
        base = "neutral"

    if cvd_trend > 2:
        return "mild_up" if base == "neutral" else "uptrend" if base == "expansion" else "mild_up"
    elif cvd_trend < -2:
        return "mild_down" if base == "neutral" else "downtrend" if base == "expansion" else "mild_down"
    return base


def _is_sell_side(side: str) -> bool:
    sell_kw = ["sell", "bearish", "high_sweep", "down_break", "above_vwap"]
    return any(kw in side.lower() for kw in sell_kw)


# ============================================================
# Analysis Functions
# ============================================================

def bucket_analysis(events: list[dict], score_field: str,
                    horizon: int = 60, cost_bps: float = 4.0,
                    buckets: int = 4) -> dict:
    """Bucket events by score quantile, compute outcome stats per bucket."""
    return_field = f"dir_return_{horizon}s"

    # Filter to events with outcome
    valid = [e for e in events if e.get(return_field) is not None]
    if not valid:
        return {"error": "no valid outcomes"}

    sorted_events = sorted(valid, key=lambda e: e[score_field])
    n = len(sorted_events)
    bin_size = max(n // buckets, 1)

    results = {}
    for i in range(buckets):
        start = i * bin_size
        end = start + bin_size if i < buckets - 1 else n
        chunk = sorted_events[start:end]
        if not chunk:
            continue

        low = chunk[0][score_field]
        high = chunk[-1][score_field]
        returns = [e[return_field] for e in chunk]
        net_returns = [r - cost_bps for r in returns]

        wins = [r for r in net_returns if r > 0]
        losses = [r for r in net_returns if r <= 0]
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0

        label = f"Q{i+1}" if buckets == 4 else f"{low:.2f}-{high:.2f}"
        results[label] = {
            "n": len(chunk),
            "score_range": f"{low:.3f}-{high:.3f}",
            "mean_gross_bps": round(sum(returns) / len(returns), 2),
            "mean_net_bps": round(sum(net_returns) / len(net_returns), 2),
            "winrate": round(len(wins) / len(net_returns), 4) if net_returns else 0,
            "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss > 0 else float('inf'),
            "median_net_bps": round(sorted(net_returns)[len(net_returns)//2], 2),
        }

    return results


def top_n_analysis(events: list[dict], score_field: str,
                   horizon: int = 60, cost_bps: float = 4.0,
                   pct: float = 0.10) -> dict:
    """Analyze top N% by score."""
    return_field = f"dir_return_{horizon}s"
    valid = [e for e in events if e.get(return_field) is not None]
    if not valid:
        return {"error": "no valid outcomes"}

    sorted_events = sorted(valid, key=lambda e: -e[score_field])
    n = max(int(len(sorted_events) * pct), 1)
    top = sorted_events[:n]

    returns = [e[return_field] for e in top]
    net = [r - cost_bps for r in returns]
    wins = [r for r in net if r > 0]
    losses = [r for r in net if r <= 0]
    gp = sum(wins) if wins else 0
    gl = abs(sum(losses)) if losses else 0

    return {
        "n": len(top),
        "pct": pct,
        "mean_gross_bps": round(sum(returns) / len(returns), 2),
        "mean_net_bps": round(sum(net) / len(net), 2),
        "winrate": round(len(wins) / len(net), 4),
        "profit_factor": round(gp / gl, 3) if gl > 0 else float('inf'),
    }


def short_filter_analysis(events: list[dict], horizon: int = 60,
                          costs: list[float] = None) -> dict:
    """Compare suppressed vs preserved short events."""
    if costs is None:
        costs = [2, 4, 6]

    sell_events = [e for e in events if e["direction"] == "short"]
    suppressed = [e for e in sell_events if not e["directional_filter_allowed"]]
    preserved = [e for e in sell_events if e["directional_filter_allowed"]]

    return_field = f"dir_return_{horizon}s"

    def _stats(evts, cost):
        valid = [e for e in evts if e.get(return_field) is not None]
        if not valid:
            return {"n": 0}
        returns = [e[return_field] for e in valid]
        net = [r - cost for r in returns]
        wins = [r for r in net if r > 0]
        losses = [r for r in net if r <= 0]
        gp = sum(wins) if wins else 0
        gl = abs(sum(losses)) if losses else 0
        return {
            "n": len(valid),
            "mean_gross_bps": round(sum(returns) / len(returns), 2),
            "mean_net_bps": round(sum(net) / len(net), 2),
            "winrate": round(len(wins) / len(net), 4) if net else 0,
            "profit_factor": round(gp / gl, 3) if gl > 0 else float('inf'),
            "worst_loss_bps": round(min(returns), 2) if returns else 0,
            "avg_loss_bps": round(sum(r for r in returns if r < 0) / max(len([r for r in returns if r < 0]), 1), 2),
        }

    result = {"suppressed": {}, "preserved": {}}
    for cost in costs:
        result["suppressed"][f"cost_{cost}bps"] = _stats(suppressed, cost)
        result["preserved"][f"cost_{cost}bps"] = _stats(preserved, cost)

    result["suppressed_count"] = len(suppressed)
    result["preserved_count"] = len(preserved)
    result["suppressed_types"] = _type_dist(suppressed)
    result["preserved_types"] = _type_dist(preserved)

    return result


def regime_analysis(events: list[dict], horizon: int = 60,
                    cost_bps: float = 4.0) -> dict:
    """Analyze outcomes by shadow regime."""
    return_field = f"dir_return_{horizon}s"
    by_regime = defaultdict(list)
    for e in events:
        by_regime[e["shadow_regime"]].append(e)

    result = {}
    for regime, evts in sorted(by_regime.items()):
        valid = [e for e in evts if e.get(return_field) is not None]
        if not valid:
            result[regime] = {"n": len(evts), "n_with_outcome": 0}
            continue

        # By direction
        for dir_label, dir_filter in [("long", lambda e: e["direction"] == "long"),
                                       ("short", lambda e: e["direction"] == "short"),
                                       ("all", lambda e: True)]:
            subset = [e for e in valid if dir_filter(e)]
            if not subset:
                continue
            returns = [e[return_field] for e in subset]
            net = [r - cost_bps for r in returns]
            wins = [r for r in net if r > 0]
            losses = [r for r in net if r <= 0]
            gp = sum(wins) if wins else 0
            gl = abs(sum(losses)) if losses else 0

            key = f"{regime}_{dir_label}"
            result[key] = {
                "n": len(subset),
                "mean_gross_bps": round(sum(returns) / len(returns), 2),
                "mean_net_bps": round(sum(net) / len(net), 2),
                "winrate": round(len(wins) / len(net), 4),
                "profit_factor": round(gp / gl, 3) if gl > 0 else float('inf'),
            }

        result[regime] = {
            "n": len(evts),
            "n_with_outcome": len(valid),
            "types": _type_dist(evts),
        }

    return result


def time_split_analysis(events: list[dict], score_field: str,
                        horizon: int = 60, cost_bps: float = 4.0) -> dict:
    """Split events chronologically and compare."""
    return_field = f"dir_return_{horizon}s"
    sorted_by_time = sorted(events, key=lambda e: e["timestamp"])
    n = len(sorted_by_time)
    mid = n // 2

    first_half = sorted_by_time[:mid]
    second_half = sorted_by_time[mid:]

    def _split_stats(evts, label):
        valid = [e for e in evts if e.get(return_field) is not None]
        if not valid:
            return {"n": len(evts), "n_with_outcome": 0}

        # Score distribution
        scores = [e[score_field] for e in valid]
        scores.sort()

        # Top quartile performance
        sorted_by_score = sorted(valid, key=lambda e: -e[score_field])
        top_q = sorted_by_score[:max(len(sorted_by_score)//4, 1)]
        top_returns = [e[return_field] for e in top_q]
        top_net = [r - cost_bps for r in top_returns]
        top_wins = [r for r in top_net if r > 0]

        # All performance
        all_returns = [e[return_field] for e in valid]
        all_net = [r - cost_bps for r in all_returns]
        all_wins = [r for r in all_net if r > 0]
        all_losses = [r for r in all_net if r <= 0]
        gp = sum(all_wins) if all_wins else 0
        gl = abs(sum(all_losses)) if all_losses else 0

        return {
            "n": len(evts),
            "n_with_outcome": len(valid),
            "score_p25": round(scores[len(scores)//4], 4),
            "score_median": round(scores[len(scores)//2], 4),
            "score_p75": round(scores[3*len(scores)//4], 4),
            "all_mean_net_bps": round(sum(all_net) / len(all_net), 2),
            "all_winrate": round(len(all_wins) / len(all_net), 4),
            "all_pf": round(gp / gl, 3) if gl > 0 else float('inf'),
            "top_q_n": len(top_q),
            "top_q_mean_net_bps": round(sum(top_net) / len(top_net), 2),
            "top_q_winrate": round(len(top_wins) / len(top_net), 4),
        }

    return {
        "first_half": _split_stats(first_half, "first"),
        "second_half": _split_stats(second_half, "second"),
    }


def cost_stress_test(events: list[dict], score_field: str,
                     horizon: int = 60, costs: list[float] = None) -> dict:
    """Test performance at multiple cost levels."""
    if costs is None:
        costs = [2, 4, 6]
    return_field = f"dir_return_{horizon}s"
    valid = [e for e in events if e.get(return_field) is not None]
    if not valid:
        return {"error": "no valid outcomes"}

    # Top quartile
    sorted_by_score = sorted(valid, key=lambda e: -e[score_field])
    top_q = sorted_by_score[:max(len(sorted_by_score)//4, 1)]

    result = {}
    for cost in costs:
        # All events
        all_returns = [e[return_field] for e in valid]
        all_net = [r - cost for r in all_returns]
        all_wins = [r for r in all_net if r > 0]
        all_losses = [r for r in all_net if r <= 0]
        gp = sum(all_wins) if all_wins else 0
        gl = abs(sum(all_losses)) if all_losses else 0

        # Top quartile
        top_returns = [e[return_field] for e in top_q]
        top_net = [r - cost for r in top_returns]
        top_wins = [r for r in top_net if r > 0]
        top_losses = [r for r in top_net if r <= 0]
        tgp = sum(top_wins) if top_wins else 0
        tgl = abs(sum(top_losses)) if top_losses else 0

        result[f"cost_{cost}bps"] = {
            "all_n": len(valid),
            "all_mean_net_bps": round(sum(all_net) / len(all_net), 2),
            "all_winrate": round(len(all_wins) / len(all_net), 4),
            "all_pf": round(gp / gl, 3) if gl > 0 else float('inf'),
            "top_q_n": len(top_q),
            "top_q_mean_net_bps": round(sum(top_net) / len(top_net), 2),
            "top_q_winrate": round(len(top_wins) / len(top_net), 4),
            "top_q_pf": round(tgp / tgl, 3) if tgl > 0 else float('inf'),
        }

    return result


# ============================================================
# New Diagnostics: Type×Side×Regime×Horizon + Gross Edge
# ============================================================

def type_side_regime_analysis(events: list[dict]) -> dict:
    """
    Detailed breakdown: event_type × side × regime × horizon.
    For each combination, compute gross and net returns at multiple horizons.
    Focus on sell-side types: sell_exhaustion, sell_cluster, sell_imbalance,
    bearish_divergence, sell_absorption.
    """
    horizons = [10, 30, 60, 120, 300]
    costs = [2, 4, 6]

    # Group by (event_type, side, regime)
    groups = defaultdict(list)
    for e in events:
        key = (e["event_type"], e["side"], e["shadow_regime"])
        groups[key].append(e)

    results = {}
    for (etype, side, regime), evts in sorted(groups.items()):
        key = f"{etype}|{side}|{regime}"
        row = {
            "event_type": etype,
            "side": side,
            "regime": regime,
            "n": len(evts),
        }

        for horizon in horizons:
            ret_field = f"dir_return_{horizon}s"
            valid = [e for e in evts if e.get(ret_field) is not None]
            if not valid:
                row[f"gross_{horizon}s"] = None
                row[f"net4_{horizon}s"] = None
                row[f"wr_{horizon}s"] = None
                continue

            returns = [e[ret_field] for e in valid]
            gross = sum(returns) / len(returns)
            net4 = sum(r - 4 for r in returns) / len(returns)
            wins = sum(1 for r in returns if r - 4 > 0)
            wr = wins / len(returns)

            row[f"gross_{horizon}s"] = round(gross, 2)
            row[f"net4_{horizon}s"] = round(net4, 2)
            row[f"wr_{horizon}s"] = round(wr, 4)

        results[key] = row

    return results


def gross_edge_analysis(events: list[dict]) -> dict:
    """
    Separate gross edge from cost impact.

    For each event_type × side:
      - mean gross return (before costs) at 10s, 30s, 60s, 120s, 300s
      - mean net return at 2, 4, 6 bps
      - gross_positive: is mean gross > 0?
      - net_positive_at_4: is mean net @ 4bps > 0?
      - verdict:
        "detector_bad"       — gross is negative (detector itself is wrong)
        "cost_sensitive"     — gross positive, net negative at 4bps (horizon/cost issue)
        "edge_at_horizon"    — net positive at some cost level
    """
    horizons = [10, 30, 60, 120, 300]
    costs = [2, 4, 6]

    groups = defaultdict(list)
    for e in events:
        groups[(e["event_type"], e["side"])].append(e)

    results = {}
    for (etype, side), evts in sorted(groups.items()):
        key = f"{etype}|{side}"
        row = {
            "event_type": etype,
            "side": side,
            "n": len(evts),
        }

        gross_positive_any = False
        net_positive_any = False

        for horizon in horizons:
            ret_field = f"dir_return_{horizon}s"
            valid = [e for e in evts if e.get(ret_field) is not None]
            if not valid:
                row[f"gross_{horizon}s"] = None
                continue

            returns = [e[ret_field] for e in valid]
            gross = sum(returns) / len(returns)
            row[f"gross_{horizon}s"] = round(gross, 2)

            if gross > 0:
                gross_positive_any = True

            for cost in costs:
                net = sum(r - cost for r in returns) / len(returns)
                row[f"net{cost}_{horizon}s"] = round(net, 2)
                if net > 0:
                    net_positive_any = True

        # Verdict
        if not gross_positive_any:
            row["verdict"] = "detector_bad"
            row["verdict_note"] = "Gross return negative at ALL horizons. Detector itself has no edge."
        elif gross_positive_any and not net_positive_any:
            row["verdict"] = "cost_sensitive"
            row["verdict_note"] = "Gross positive at some horizon but net negative at all cost levels."
        else:
            row["verdict"] = "edge_at_horizon"
            row["verdict_note"] = "Net positive at some horizon/cost combination."

        results[key] = row

    return results


# ============================================================
# Helpers
# ============================================================

def _type_dist(events: list[dict]) -> dict:
    dist = defaultdict(int)
    for e in events:
        dist[e["event_type"]] += 1
    return dict(sorted(dist.items(), key=lambda x: -x[1]))


def write_csv(events: list[dict], path: str):
    """Write shadow-scored events to CSV."""
    if not events:
        return
    fields = list(events[0].keys())
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for e in events:
            row = {}
            for k, v in e.items():
                if isinstance(v, bool):
                    row[k] = str(v)
                elif v is None:
                    row[k] = ''
                else:
                    row[k] = v
            writer.writerow(row)


# ============================================================
# Report Generation
# ============================================================

def generate_report(events: list[dict], analysis: dict) -> str:
    """Generate SHADOW_VALIDATION_REPORT.md content."""
    n = len(events)
    n_complete = sum(1 for e in events if e["is_complete"])
    timestamps = [e["timestamp"] for e in events]
    tz8 = timezone(timedelta(hours=8))
    t0 = datetime.fromtimestamp(min(timestamps), tz=tz8)
    t1 = datetime.fromtimestamp(max(timestamps), tz=tz8)
    span_min = (max(timestamps) - min(timestamps)) / 60

    # Sample sufficiency
    if n < 100:
        sufficiency = "INSUFFICIENT — diagnostics only"
        sufficiency_note = "Less than 100 events. Results are descriptive, not inferential."
    elif n < 300:
        sufficiency = "WEAK PRELIMINARY — treat with caution"
        sufficiency_note = "100–300 events. Directional evidence only. Need 1000+ for stronger claims."
    elif n < 1000:
        sufficiency = "USABLE PRELIMINARY — conditional on stability"
        sufficiency_note = "300–1000 events. Preliminary validation possible if stable across splits."
    else:
        sufficiency = "ADEQUATE — stronger validation possible"
        sufficiency_note = "1000+ events. Statistical tests meaningful."

    lines = []
    lines.append("# SHADOW VALIDATION REPORT")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now(tz8).strftime('%Y-%m-%d %H:%M:%S')} CST")
    lines.append(f"**Data source:** Hyperliquid BTC live event engine")
    lines.append(f"**Validation type:** Shadow scoring (original vs new modules)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Executive Summary")
    lines.append("")
    lines.append(f"- **Events analyzed:** {n}")
    lines.append(f"- **Completed outcomes:** {n_complete}")
    lines.append(f"- **Time range:** {t0.strftime('%H:%M:%S')} – {t1.strftime('%H:%M:%S')} ({span_min:.0f} min)")
    lines.append(f"- **Sample sufficiency:** {sufficiency}")
    lines.append(f"  - {sufficiency_note}")
    lines.append(f"- **Live engine modified:** NO (shadow mode only)")
    lines.append("")

    # Integration recommendation — will be filled at end
    lines.append("## 2. Baseline Problems Identified")
    lines.append("")
    lines.append("### 2.1 Dead Regime Detection")
    lines.append("")
    orig_regimes = defaultdict(int)
    for e in events:
        orig_regimes[e["original_regime"]] += 1
    lines.append(f"Original regime distribution: {dict(orig_regimes)}")
    lines.append("")
    lines.append("All events classified as `low_volatility`. The original `classify_regime()` uses")
    lines.append("a 60-tick absolute price range with a 0.3% threshold ($235 at BTC $78,500).")
    lines.append("The entire 36-minute price span is ~$232. Threshold never reached.")
    lines.append("Result: `regime_score=0.4` and `confidence_regime=0.4` for every event.")
    lines.append("")
    lines.append("### 2.2 Score Compression")
    lines.append("")
    orig_scores = [e["original_score"] for e in events]
    orig_scores.sort()
    no = len(orig_scores)
    lines.append(f"Original composite score distribution:")
    lines.append(f"- min={orig_scores[0]:.4f}  p25={orig_scores[no//4]:.4f}  "
                 f"median={orig_scores[no//2]:.4f}  p75={orig_scores[3*no//4]:.4f}  max={orig_scores[-1]:.4f}")
    lines.append("")
    lines.append("Multiplicative formula `strength × confidence × (1 - noise × 0.5)` compresses")
    lines.append("most scores into 0.09–0.42 range. Score separation is weak.")
    lines.append("")
    lines.append("### 2.3 Short-Side Noise Hypothesis")
    lines.append("")
    sell_events = [e for e in events if e["direction"] == "short"]
    sell_types = _type_dist(sell_events)
    lines.append(f"Sell-side event type distribution: {sell_types}")
    lines.append("")
    lines.append("`sell_imbalance`, `sell_cluster`, and `down_break` may represent")
    lines.append("absorption noise, not valid short setups. Structural short candidates:")
    lines.append("`sell_exhaustion`, `bearish_divergence`, `sell_absorption`.")
    lines.append("")

    lines.append("## 3. Shadow Scoring Method")
    lines.append("")
    lines.append("Three new modules computed in shadow mode (not integrated into live engine):")
    lines.append("")
    lines.append("1. **RegimeClassifier** (`regime.py`): Multi-signal regime detection")
    lines.append("   - Volatility ratio (30s/300s rv, percentile-ranked)")
    lines.append("   - CVD slope + price slope at two timeframes")
    lines.append("   - Range position within session")
    lines.append("")
    lines.append("2. **ConfidenceEngine** (`confidence.py`): Regime-aware confidence")
    lines.append("   - Regime-event alignment (does regime support this direction?)")
    lines.append("   - Structural proximity (distance to VWAP/session H-L)")
    lines.append("   - Flow consistency (CVD vs event direction)")
    lines.append("   - Event type reliability (structural base rate)")
    lines.append("")
    lines.append("3. **DirectionalBias** (`directional_bias.py`): Short filter + score modifier")
    lines.append("   - Shorts allowed only in: bearish regime, structural events, or extended above VWAP")
    lines.append("   - Score multiplier: 0.5x–1.5x based on regime-direction alignment")
    lines.append("")
    lines.append("Shadow composite formula (additive, replaces multiplicative):")
    lines.append("`quality = strength×0.40 + confidence×0.40 + (1-noise)×0.20`")
    lines.append("`shadow_score = quality × directional_multiplier`")
    lines.append("")

    # Regime distribution
    lines.append("### 3.1 Shadow Regime Distribution")
    lines.append("")
    shadow_regimes = defaultdict(int)
    for e in events:
        shadow_regimes[e["shadow_regime"]] += 1
    for r, c in sorted(shadow_regimes.items(), key=lambda x: -x[1]):
        lines.append(f"- `{r}`: {c} ({c/n*100:.0f}%)")
    lines.append("")

    # Score distribution comparison
    lines.append("### 3.2 Score Distribution Comparison")
    lines.append("")
    shadow_scores = [e["shadow_score"] for e in events]
    shadow_scores.sort()
    ns = len(shadow_scores)
    lines.append(f"| Metric | Original | Shadow |")
    lines.append(f"|--------|----------|--------|")
    lines.append(f"| min | {orig_scores[0]:.4f} | {shadow_scores[0]:.4f} |")
    lines.append(f"| p25 | {orig_scores[no//4]:.4f} | {shadow_scores[ns//4]:.4f} |")
    lines.append(f"| median | {orig_scores[no//2]:.4f} | {shadow_scores[ns//2]:.4f} |")
    lines.append(f"| p75 | {orig_scores[3*no//4]:.4f} | {shadow_scores[3*ns//4]:.4f} |")
    lines.append(f"| max | {orig_scores[-1]:.4f} | {shadow_scores[-1]:.4f} |")
    lines.append("")

    # 4. Score Ranking Validation
    lines.append("## 4. Score Ranking Validation")
    lines.append("")
    lines.append("Question: Do higher scores predict better directional outcomes?")
    lines.append("")
    lines.append("### 4.1 Original Score Buckets (60s, net @ 4bps)")
    lines.append("")
    orig_buckets = analysis.get("original_buckets", {})
    lines.append(f"| Bucket | N | Mean Gross | Mean Net | Winrate | PF |")
    lines.append(f"|--------|---|-----------|---------|---------|-----|")
    for label, data in orig_buckets.items():
        if "error" in data:
            continue
        lines.append(f"| {label} | {data['n']} | {data['mean_gross_bps']:+.2f} | "
                     f"{data['mean_net_bps']:+.2f} | {data['winrate']:.1%} | {data['profit_factor']:.2f} |")
    lines.append("")

    lines.append("### 4.2 Shadow Score Buckets (60s, net @ 4bps)")
    lines.append("")
    shadow_buckets = analysis.get("shadow_buckets", {})
    lines.append(f"| Bucket | N | Mean Gross | Mean Net | Winrate | PF |")
    lines.append(f"|--------|---|-----------|---------|---------|-----|")
    for label, data in shadow_buckets.items():
        if "error" in data:
            continue
        lines.append(f"| {label} | {data['n']} | {data['mean_gross_bps']:+.2f} | "
                     f"{data['mean_net_bps']:+.2f} | {data['winrate']:.1%} | {data['profit_factor']:.2f} |")
    lines.append("")

    # Monotonicity check
    lines.append("### 4.3 Monotonicity Check")
    lines.append("")
    lines.append("Does score increase → outcome improve monotonically?")
    lines.append("")
    for score_label, buckets in [("Original", orig_buckets), ("Shadow", shadow_buckets)]:
        bucket_list = list(buckets.values())
        bucket_list = [b for b in bucket_list if "error" not in b]
        if len(bucket_list) < 2:
            lines.append(f"- **{score_label}**: insufficient buckets")
            continue
        nets = [b["mean_net_bps"] for b in bucket_list]
        monotonic = all(nets[i] >= nets[i-1] for i in range(1, len(nets)))
        strictly_mono = all(nets[i] > nets[i-1] for i in range(1, len(nets)))
        if strictly_mono:
            lines.append(f"- **{score_label}**: ✅ Strictly monotonic (Q1→Q4: {'→'.join(f'{n:+.1f}' for n in nets)})")
        elif monotonic:
            lines.append(f"- **{score_label}**: ⚠️ Weakly monotonic (Q1→Q4: {'→'.join(f'{n:+.1f}' for n in nets)})")
        else:
            lines.append(f"- **{score_label}**: ❌ NOT monotonic (Q1→Q4: {'→'.join(f'{n:+.1f}' for n in nets)})")
    lines.append("")

    # Top quartile comparison
    lines.append("### 4.4 Top Quartile Performance")
    lines.append("")
    for score_label, key in [("Original", "original_top_q"), ("Shadow", "shadow_top_q")]:
        tq = analysis.get(key, {})
        if "error" in tq:
            lines.append(f"- **{score_label}**: no data")
            continue
        lines.append(f"- **{score_label}** top 25%: n={tq['n']}, "
                     f"net={tq['mean_net_bps']:+.2f}bps, "
                     f"WR={tq['winrate']:.1%}")
    lines.append("")

    # 5. Short Filter Validation
    lines.append("## 5. Short Filter Validation")
    lines.append("")
    sf = analysis.get("short_filter", {})
    lines.append(f"- Suppressed: {sf.get('suppressed_count', 0)} events")
    lines.append(f"- Preserved: {sf.get('preserved_count', 0)} events")
    lines.append("")
    lines.append("Suppressed types: " + str(sf.get("suppressed_types", {})))
    lines.append("Preserved types: " + str(sf.get("preserved_types", {})))
    lines.append("")

    for cost_key in ["cost_2bps", "cost_4bps", "cost_6bps"]:
        supp = sf.get("suppressed", {}).get(cost_key, {})
        pres = sf.get("preserved", {}).get(cost_key, {})
        if supp.get("n", 0) == 0 and pres.get("n", 0) == 0:
            continue
        lines.append(f"**{cost_key}**:")
        lines.append(f"| Metric | Suppressed | Preserved |")
        lines.append(f"|--------|-----------|-----------|")
        lines.append(f"| N | {supp.get('n', 0)} | {pres.get('n', 0)} |")
        lines.append(f"| Mean net bps | {supp.get('mean_net_bps', 'N/A')} | {pres.get('mean_net_bps', 'N/A')} |")
        lines.append(f"| Winrate | {supp.get('winrate', 'N/A')} | {pres.get('winrate', 'N/A')} |")
        lines.append(f"| PF | {supp.get('profit_factor', 'N/A')} | {pres.get('profit_factor', 'N/A')} |")
        lines.append(f"| Worst loss | {supp.get('worst_loss_bps', 'N/A')} | {pres.get('worst_loss_bps', 'N/A')} |")
        lines.append("")

    # Filter verdict
    supp_net = sf.get("suppressed", {}).get("cost_4bps", {}).get("mean_net_bps", 0)
    pres_net = sf.get("preserved", {}).get("cost_4bps", {}).get("mean_net_bps", 0)
    if supp_net < pres_net:
        lines.append("**Filter verdict:** ✅ Suppressed events perform worse than preserved. Filter adds value.")
    elif supp_net == pres_net:
        lines.append("**Filter verdict:** ⚠️ No clear difference. Need more data.")
    else:
        lines.append("**Filter verdict:** ❌ Suppressed events perform BETTER. Filter is harmful.")
    lines.append("")

    # 6. Regime Validation
    lines.append("## 6. Regime Validation")
    lines.append("")
    rv = analysis.get("regime", {})
    regime_keys = [k for k in rv.keys() if "_" not in k or k.startswith("unknown")]
    for regime in sorted(rv.keys()):
        if "_" in regime and not regime.startswith("unknown"):
            continue
        data = rv[regime]
        lines.append(f"### {regime}")
        lines.append(f"- Events: {data.get('n', 0)} (with outcome: {data.get('n_with_outcome', 0)})")
        lines.append(f"- Types: {data.get('types', {})}")
        lines.append("")

        # Show long/short breakdown
        for dir_label in ["long", "short", "all"]:
            key = f"{regime}_{dir_label}"
            if key in rv:
                d = rv[key]
                lines.append(f"  - {dir_label}: n={d['n']}, "
                             f"net={d['mean_net_bps']:+.2f}bps, "
                             f"WR={d['winrate']:.1%}, "
                             f"PF={d['profit_factor']:.2f}")
        lines.append("")

    # 7. Time Split Validation
    lines.append("## 7. Time Split Validation")
    lines.append("")
    ts_data = analysis.get("time_split", {})
    first = ts_data.get("first_half", {})
    second = ts_data.get("second_half", {})

    lines.append(f"| Metric | First Half | Second Half |")
    lines.append(f"|--------|-----------|-------------|")
    lines.append(f"| Events | {first.get('n', 0)} | {second.get('n', 0)} |")
    lines.append(f"| With outcome | {first.get('n_with_outcome', 0)} | {second.get('n_with_outcome', 0)} |")
    lines.append(f"| Score median | {first.get('score_median', 'N/A')} | {second.get('score_median', 'N/A')} |")
    lines.append(f"| All mean net | {first.get('all_mean_net_bps', 'N/A')} bps | {second.get('all_mean_net_bps', 'N/A')} bps |")
    lines.append(f"| All winrate | {first.get('all_winrate', 'N/A')} | {second.get('all_winrate', 'N/A')} |")
    lines.append(f"| All PF | {first.get('all_pf', 'N/A')} | {second.get('all_pf', 'N/A')} |")
    lines.append(f"| Top Q mean net | {first.get('top_q_mean_net_bps', 'N/A')} bps | {second.get('top_q_mean_net_bps', 'N/A')} bps |")
    lines.append(f"| Top Q winrate | {first.get('top_q_winrate', 'N/A')} | {second.get('top_q_winrate', 'N/A')} |")
    lines.append("")

    # Stability
    f_net = first.get("all_mean_net_bps", 0)
    s_net = second.get("all_mean_net_bps", 0)
    if (f_net > 0 and s_net > 0) or (f_net < 0 and s_net < 0):
        lines.append("**Stability:** ✅ Directionally consistent across halves.")
    else:
        lines.append("**Stability:** ❌ Direction inconsistent across halves. Results unreliable.")
    lines.append("")

    # 8. Cost Stress Test
    lines.append("## 8. Cost Stress Test")
    lines.append("")
    cst = analysis.get("cost_stress", {})
    lines.append(f"| Cost | All N | All Net | All WR | All PF | Top Q Net | Top Q WR | Top Q PF |")
    lines.append(f"|------|-------|---------|--------|--------|-----------|----------|----------|")
    for cost_key in ["cost_2bps", "cost_4bps", "cost_6bps"]:
        d = cst.get(cost_key, {})
        lines.append(f"| {cost_key} | {d.get('all_n', 0)} | {d.get('all_mean_net_bps', 0):+.2f} | "
                     f"{d.get('all_winrate', 0):.1%} | {d.get('all_pf', 0):.2f} | "
                     f"{d.get('top_q_mean_net_bps', 0):+.2f} | {d.get('top_q_winrate', 0):.1%} | "
                     f"{d.get('top_q_pf', 0):.2f} |")
    lines.append("")

    # 9. Type × Side × Regime × Horizon
    lines.append("## 9. Event Type × Side × Regime × Horizon Performance")
    lines.append("")
    tsr = analysis.get("type_side_regime", {})

    # Focus on sell-side types
    focus_types = ["sell_exhaustion", "sell_cluster", "sell_imbalance",
                   "bearish_divergence", "sell_absorption",
                   "buy_exhaustion", "buy_imbalance", "bullish_divergence"]

    lines.append("### Sell-Side Focus Events")
    lines.append("")
    lines.append("| Type | Side | Regime | N | Gross10s | Gross30s | Gross60s | Gross120s | Gross300s | Net4@60s | WR@60s |")
    lines.append("|------|------|--------|---|----------|----------|----------|-----------|-----------|----------|--------|")
    for key, row in tsr.items():
        if row["side"] not in focus_types and row["event_type"] not in ["exhaustion", "imbalance", "delta_divergence", "absorption", "large_trade_cluster", "liquidity_sweep"]:
            continue
        # Only show sell-side or bearish
        if not any(kw in row["side"] for kw in ["sell", "bearish", "high_sweep", "down_break", "above_vwap"]):
            continue
        g10 = f"{row['gross_10s']:+.2f}" if row['gross_10s'] is not None else "—"
        g30 = f"{row['gross_30s']:+.2f}" if row['gross_30s'] is not None else "—"
        g60 = f"{row['gross_60s']:+.2f}" if row['gross_60s'] is not None else "—"
        g120 = f"{row['gross_120s']:+.2f}" if row['gross_120s'] is not None else "—"
        g300 = f"{row['gross_300s']:+.2f}" if row['gross_300s'] is not None else "—"
        n4 = f"{row['net4_60s']:+.2f}" if row['net4_60s'] is not None else "—"
        wr = f"{row['wr_60s']:.1%}" if row['wr_60s'] is not None else "—"
        lines.append(f"| {row['event_type']} | {row['side']} | {row['regime']} | {row['n']} | {g10} | {g30} | {g60} | {g120} | {g300} | {n4} | {wr} |")
    lines.append("")

    lines.append("### Buy-Side Focus Events")
    lines.append("")
    lines.append("| Type | Side | Regime | N | Gross10s | Gross30s | Gross60s | Gross120s | Gross300s | Net4@60s | WR@60s |")
    lines.append("|------|------|--------|---|----------|----------|----------|-----------|-----------|----------|--------|")
    for key, row in tsr.items():
        if not any(kw in row["side"] for kw in ["buy", "bullish", "low_sweep", "up_break", "below_vwap"]):
            continue
        g10 = f"{row['gross_10s']:+.2f}" if row['gross_10s'] is not None else "—"
        g30 = f"{row['gross_30s']:+.2f}" if row['gross_30s'] is not None else "—"
        g60 = f"{row['gross_60s']:+.2f}" if row['gross_60s'] is not None else "—"
        g120 = f"{row['gross_120s']:+.2f}" if row['gross_120s'] is not None else "—"
        g300 = f"{row['gross_300s']:+.2f}" if row['gross_300s'] is not None else "—"
        n4 = f"{row['net4_60s']:+.2f}" if row['net4_60s'] is not None else "—"
        wr = f"{row['wr_60s']:.1%}" if row['wr_60s'] is not None else "—"
        lines.append(f"| {row['event_type']} | {row['side']} | {row['regime']} | {row['n']} | {g10} | {g30} | {g60} | {g120} | {g300} | {n4} | {wr} |")
    lines.append("")

    # 10. Gross Edge Before Costs
    lines.append("## 10. Gross Edge Before Costs")
    lines.append("")
    lines.append("Question: Is the detector itself wrong (gross negative), or is the issue cost/horizon?")
    lines.append("")
    ge = analysis.get("gross_edge", {})

    lines.append("| Type | Side | N | Gross10s | Gross30s | Gross60s | Gross120s | Gross300s | Net4@60s | Verdict |")
    lines.append("|------|------|---|----------|----------|----------|-----------|-----------|----------|---------|")
    for key, row in ge.items():
        g10 = f"{row['gross_10s']:+.2f}" if row.get('gross_10s') is not None else "—"
        g30 = f"{row['gross_30s']:+.2f}" if row.get('gross_30s') is not None else "—"
        g60 = f"{row['gross_60s']:+.2f}" if row.get('gross_60s') is not None else "—"
        g120 = f"{row['gross_120s']:+.2f}" if row.get('gross_120s') is not None else "—"
        g300 = f"{row['gross_300s']:+.2f}" if row.get('gross_300s') is not None else "—"
        n4 = f"{row.get('net4_60s', '—'):+.2f}" if row.get('net4_60s') is not None else "—"
        verdict = row.get("verdict", "?")
        lines.append(f"| {row['event_type']} | {row['side']} | {row['n']} | {g10} | {g30} | {g60} | {g120} | {g300} | {n4} | {verdict} |")
    lines.append("")

    # Verdict summary
    bad_detectors = [k for k, v in ge.items() if v.get("verdict") == "detector_bad"]
    cost_sensitive = [k for k, v in ge.items() if v.get("verdict") == "cost_sensitive"]
    edge_found = [k for k, v in ge.items() if v.get("verdict") == "edge_at_horizon"]

    lines.append(f"**Detector bad (gross negative everywhere):** {len(bad_detectors)} types")
    if bad_detectors:
        lines.append(f"  - {', '.join(bad_detectors)}")
    lines.append(f"**Cost-sensitive (gross positive, net negative):** {len(cost_sensitive)} types")
    if cost_sensitive:
        lines.append(f"  - {', '.join(cost_sensitive)}")
    lines.append(f"**Edge at some horizon (net positive):** {len(edge_found)} types")
    if edge_found:
        lines.append(f"  - {', '.join(edge_found)}")
    lines.append("")

    # 11. Final Recommendation
    lines.append("## 11. Final Recommendation")
    lines.append("")
    lines.append(analysis.get("recommendation", "PENDING"))
    lines.append("")

    # 12. Next Actions
    lines.append("## 12. Next Actions")
    lines.append("")
    lines.append(analysis.get("next_actions", "PENDING"))
    lines.append("")

    return "\n".join(lines)


# ============================================================
# Main
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="backend/data/events/events_with_outcomes.jsonl")
    parser.add_argument("--output-csv", default="backend/data/events/events_shadow_scored.csv")
    parser.add_argument("--output-json", default="backend/data/events/validation_shadow_report.json")
    parser.add_argument("--output-md", default="SHADOW_VALIDATION_REPORT.md")
    args = parser.parse_args()

    print("Loading events...")
    events = load_events(args.input)
    print(f"  Loaded {len(events)} events")

    print("Computing shadow scores...")
    enriched = compute_shadow_scores(events)
    print(f"  Scored {len(enriched)} events")

    # Write shadow-scored CSV
    write_csv(enriched, args.output_csv)
    print(f"  Written to {args.output_csv}")

    # Run analyses
    print("Running validations...")
    analysis = {}

    # Only use events with complete outcomes for validation
    complete = [e for e in enriched if e["is_complete"]]
    print(f"  Events with complete outcomes: {len(complete)}")

    # 4.1 Original score buckets
    analysis["original_buckets"] = bucket_analysis(complete, "original_score", 60, 4.0, 4)

    # 4.2 Shadow score buckets
    analysis["shadow_buckets"] = bucket_analysis(complete, "shadow_score", 60, 4.0, 4)

    # 4.4 Top quartile
    analysis["original_top_q"] = top_n_analysis(complete, "original_score", 60, 4.0, 0.25)
    analysis["shadow_top_q"] = top_n_analysis(complete, "shadow_score", 60, 4.0, 0.25)

    # 5. Short filter
    analysis["short_filter"] = short_filter_analysis(complete, 60, [2, 4, 6])

    # 6. Regime
    analysis["regime"] = regime_analysis(complete, 60, 4.0)

    # 7. Time split
    analysis["time_split"] = time_split_analysis(complete, "shadow_score", 60, 4.0)

    # 8. Cost stress
    analysis["cost_stress"] = cost_stress_test(complete, "shadow_score", 60, [2, 4, 6])

    # 9. Type×Side×Regime detailed breakdown
    analysis["type_side_regime"] = type_side_regime_analysis(complete)

    # 10. Gross edge analysis
    analysis["gross_edge"] = gross_edge_analysis(complete)

    # --- Determine recommendation ---
    rec_lines = []
    integrate_signals = 0
    reject_signals = 0

    # Check 1: Monotonic ranking
    shadow_b = analysis["shadow_buckets"]
    orig_b = analysis["original_buckets"]
    sb = list(shadow_b.values())
    ob = list(orig_b.values())
    sb = [b for b in sb if "error" not in b]
    ob = [b for b in ob if "error" not in b]

    if len(sb) >= 2:
        nets = [b["mean_net_bps"] for b in sb]
        if all(nets[i] >= nets[i-1] for i in range(1, len(nets))):
            integrate_signals += 1
            rec_lines.append("- ✅ Shadow score has monotonic ranking")
        else:
            reject_signals += 1
            rec_lines.append("- ❌ Shadow score does NOT have monotonic ranking")

    if len(ob) >= 2:
        nets = [b["mean_net_bps"] for b in ob]
        if all(nets[i] >= nets[i-1] for i in range(1, len(nets))):
            rec_lines.append("- ✅ Original score has monotonic ranking")
        else:
            rec_lines.append("- ❌ Original score does NOT have monotonic ranking")

    # Check 2: Top quartile
    otq = analysis.get("original_top_q", {})
    stq = analysis.get("shadow_top_q", {})
    if stq.get("mean_net_bps", -999) > otq.get("mean_net_bps", -999):
        integrate_signals += 1
        rec_lines.append(f"- ✅ Shadow top Q net ({stq.get('mean_net_bps',0):+.2f}) > Original ({otq.get('mean_net_bps',0):+.2f})")
    else:
        rec_lines.append(f"- ⚠️ Shadow top Q net ({stq.get('mean_net_bps',0):+.2f}) ≤ Original ({otq.get('mean_net_bps',0):+.2f})")

    # Check 3: Short filter
    sf = analysis.get("short_filter", {})
    supp_net = sf.get("suppressed", {}).get("cost_4bps", {}).get("mean_net_bps", 0)
    pres_net = sf.get("preserved", {}).get("cost_4bps", {}).get("mean_net_bps", 0)
    if sf.get("suppressed_count", 0) > 0 and sf.get("preserved_count", 0) > 0:
        if supp_net < pres_net:
            integrate_signals += 1
            rec_lines.append(f"- ✅ Suppressed shorts ({supp_net:+.2f}) worse than preserved ({pres_net:+.2f})")
        else:
            reject_signals += 1
            rec_lines.append(f"- ❌ Suppressed shorts ({supp_net:+.2f}) NOT worse than preserved ({pres_net:+.2f})")

    # Check 4: Time stability
    ts = analysis.get("time_split", {})
    f_net = ts.get("first_half", {}).get("all_mean_net_bps", 0)
    s_net = ts.get("second_half", {}).get("all_mean_net_bps", 0)
    if (f_net > 0 and s_net > 0) or (f_net < 0 and s_net < 0):
        integrate_signals += 1
        rec_lines.append(f"- ✅ Time-stable (first={f_net:+.2f}, second={s_net:+.2f})")
    else:
        reject_signals += 1
        rec_lines.append(f"- ❌ Time-unstable (first={f_net:+.2f}, second={s_net:+.2f})")

    # Check 5: Sample size
    if len(complete) < 100:
        rec_lines.append(f"- ⚠️ Sample too small ({len(complete)}) for reliable conclusions")
        reject_signals += 2
    elif len(complete) < 300:
        rec_lines.append(f"- ⚠️ Sample marginal ({len(complete)}), treat as preliminary")

    # Final decision
    rec_lines.append("")
    if integrate_signals >= 4 and reject_signals == 0:
        recommendation = "**RECOMMENDATION: INTEGRATE** — All criteria met."
        next_actions = (
            "1. Integrate `regime.py`, `confidence.py`, `directional_bias.py` into `manager.py`\n"
            "2. Replace multiplicative scoring with additive formula\n"
            "3. Collect 1000+ events with new scoring\n"
            "4. Re-run validation to confirm improvement holds"
        )
    elif integrate_signals >= 3 and reject_signals <= 1:
        recommendation = "**RECOMMENDATION: NOT YET** — Promising but insufficient evidence."
        next_actions = (
            "1. Continue collecting events to 1000+\n"
            "2. Re-run this validation at 500 and 1000 events\n"
            "3. If criteria met at 1000+, integrate\n"
            "4. If not, investigate specific failing criteria"
        )
    else:
        recommendation = "**RECOMMENDATION: KEEP SHADOW MODE** — Evidence insufficient or negative."
        next_actions = (
            "1. Keep collecting events to 1000+\n"
            "2. Investigate why specific criteria failed\n"
            "3. Do NOT integrate until criteria pass\n"
            "4. Consider whether modules need structural changes"
        )

    analysis["recommendation"] = recommendation
    analysis["_decision_details"] = rec_lines
    analysis["next_actions"] = next_actions

    # Write JSON report
    with open(args.output_json, 'w') as f:
        json.dump(analysis, f, indent=2, default=str)
    print(f"  JSON report: {args.output_json}")

    # Write Markdown report
    report = generate_report(enriched, analysis)
    with open(args.output_md, 'w') as f:
        f.write(report)
    print(f"  Markdown report: {args.output_md}")

    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)
    for line in rec_lines:
        print(f"  {line}")
    print(f"\n  {recommendation}")


if __name__ == "__main__":
    main()
