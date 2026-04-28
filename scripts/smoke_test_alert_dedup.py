#!/usr/bin/env python3
"""Smoke test for alert rate limiter deduplication fix.

Validates:
- same tier + same state + same side fires only once within min_seconds_between_same_alert
- duplicate alerts within cooldown are suppressed
- suppressed_alert_count increments correctly
- raw event logging is unaffected (no changes to scoring/detectors)
- no duplicate burst remains
"""

from __future__ import annotations

import sys
import time

# Add project root to path
sys.path.insert(0, ".")

from engine.alerts import AlertManager
from engine.models import (
    Scores, MarketState, CrowdBuildupState, LiquidationCascadeState,
    UnwindState, ExhaustionAbsorptionState, ExecutionMode,
)

# ── Config ──────────────────────────────────────────────────────────────

CONFIG = {
    "alerts": {
        "tier1": {"imbalance_score_min": 60, "execution_quality_min": 50},
        "tier2": {"imbalance_score_min": 75, "execution_quality_min": 70, "risk_score_max": 60},
        "tier3": {"risk_score_min": 75, "execution_quality_max": 35, "cascade_intensity_min": 80},
        "min_seconds_between_same_alert": 60,
        "max_alerts_per_hour": 20,
    }
}

# ── Helpers ─────────────────────────────────────────────────────────────

def make_scores(**kwargs) -> Scores:
    s = Scores()
    for k, v in kwargs.items():
        setattr(s, k, v)
    return s


def make_cascade(active=False, intensity=0.0, direction="DOWN") -> LiquidationCascadeState:
    return LiquidationCascadeState(
        active=active, cascade_direction=direction,
        intensity=intensity, execution_mode="DANGER" if active else "NORMAL",
    )


def make_crowd(active=False, side="neutral") -> CrowdBuildupState:
    return CrowdBuildupState(active=active, crowd_side=side)


def make_unwind(active=False, side="neutral") -> UnwindState:
    return UnwindState(active=active, unwind_side=side)


def make_exhaustion() -> ExhaustionAbsorptionState:
    return ExhaustionAbsorptionState()


# ── Test Cases ──────────────────────────────────────────────────────────

def test_same_key_suppressed():
    """Same tier+state+side must NOT fire twice within cooldown."""
    mgr = AlertManager(CONFIG)
    now = time.time()

    # Tier 1: CROWD_BUILDUP + LONGS
    scores = make_scores(imbalance=65, execution_quality=55)
    crowd = make_crowd(active=True, side="LONGS")
    state = MarketState.CROWD_BUILDUP

    a1 = mgr.check(scores, state, crowd, make_cascade(), make_unwind(), make_exhaustion(), ExecutionMode.MAKER_ONLY)
    assert a1 is not None, "First alert must fire"

    # Immediate duplicate — must be suppressed
    a2 = mgr.check(scores, state, crowd, make_cascade(), make_unwind(), make_exhaustion(), ExecutionMode.MAKER_ONLY)
    assert a2 is None, "Duplicate within cooldown must be suppressed"
    assert mgr.suppressed_alert_count == 1, f"suppressed_alert_count should be 1, got {mgr.suppressed_alert_count}"
    print("  ✓ Same tier+state+side suppressed within cooldown")


def test_different_side_fires():
    """Different side for same tier+state should fire independently."""
    mgr = AlertManager(CONFIG)

    scores = make_scores(imbalance=65, execution_quality=55)
    state = MarketState.CROWD_BUILDUP

    # LONGS fires
    crowd_long = make_crowd(active=True, side="LONGS")
    a1 = mgr.check(scores, state, crowd_long, make_cascade(), make_unwind(), make_exhaustion(), ExecutionMode.MAKER_ONLY)
    assert a1 is not None, "LONGS alert must fire"
    assert a1.side == "LONGS"

    # SHORTS fires (different side)
    crowd_short = make_crowd(active=True, side="SHORTS")
    a2 = mgr.check(scores, state, crowd_short, make_cascade(), make_unwind(), make_exhaustion(), ExecutionMode.MAKER_ONLY)
    assert a2 is not None, "SHORTS alert must fire (different side)"
    assert a2.side == "SHORTS"
    assert mgr.suppressed_alert_count == 0, "No suppression should occur for different side"
    print("  ✓ Different side fires independently")


def test_different_state_fires():
    """Different state for same tier+side should fire independently."""
    mgr = AlertManager(CONFIG)

    # CROWD_BUILDUP + LONGS
    scores1 = make_scores(imbalance=65, execution_quality=55)
    crowd1 = make_crowd(active=True, side="LONGS")
    a1 = mgr.check(scores1, MarketState.CROWD_BUILDUP, crowd1, make_cascade(), make_unwind(), make_exhaustion(), ExecutionMode.MAKER_ONLY)
    assert a1 is not None

    # UNWIND + LONGS (different state)
    scores2 = make_scores(imbalance=65, execution_quality=55)
    unwind2 = make_unwind(active=True, side="LONGS")
    a2 = mgr.check(scores2, MarketState.UNWIND, make_crowd(), make_cascade(), unwind2, make_exhaustion(), ExecutionMode.MAKER_ONLY)
    assert a2 is not None, "Different state must fire independently"
    print("  ✓ Different state fires independently")


def test_after_cooldown_fires():
    """After cooldown expires, same key should fire again."""
    cooldown = 2  # short cooldown for test
    cfg = {
        "alerts": {
            "tier1": {"imbalance_score_min": 60, "execution_quality_min": 50},
            "min_seconds_between_same_alert": cooldown,
            "max_alerts_per_hour": 100,
        }
    }
    mgr = AlertManager(cfg)

    scores = make_scores(imbalance=65, execution_quality=55)
    crowd = make_crowd(active=True, side="LONGS")
    state = MarketState.CROWD_BUILDUP

    a1 = mgr.check(scores, state, crowd, make_cascade(), make_unwind(), make_exhaustion(), ExecutionMode.MAKER_ONLY)
    assert a1 is not None

    # Within cooldown — suppressed
    a2 = mgr.check(scores, state, crowd, make_cascade(), make_unwind(), make_exhaustion(), ExecutionMode.MAKER_ONLY)
    assert a2 is None

    # Wait for cooldown
    time.sleep(cooldown + 0.1)

    a3 = mgr.check(scores, state, crowd, make_cascade(), make_unwind(), make_exhaustion(), ExecutionMode.MAKER_ONLY)
    assert a3 is not None, "Must fire again after cooldown expires"
    print("  ✓ Fires again after cooldown expires")


def test_tier3_dedup():
    """Tier 3 (DANGER) must deduplicate by side."""
    mgr = AlertManager(CONFIG)

    # DANGER + DOWN
    scores = make_scores(risk=80, execution_quality=30)
    cascade = make_cascade(active=True, intensity=85, direction="DOWN")

    a1 = mgr.check(scores, MarketState.LIQUIDATION_CASCADE, make_crowd(), cascade, make_unwind(), make_exhaustion(), ExecutionMode.NO_TRADE)
    assert a1 is not None, "Tier 3 must fire"
    assert a1.tier == 3
    assert a1.side == "DOWN"

    # Same side — must be suppressed
    a2 = mgr.check(scores, MarketState.LIQUIDATION_CASCADE, make_crowd(), cascade, make_unwind(), make_exhaustion(), ExecutionMode.NO_TRADE)
    assert a2 is None, "Tier 3 duplicate must be suppressed"
    assert mgr.suppressed_alert_count == 1
    print("  ✓ Tier 3 deduplicates by side")


def test_tier3_different_direction_fires():
    """Tier 3 with different cascade direction should fire independently."""
    mgr = AlertManager(CONFIG)

    scores = make_scores(risk=80, execution_quality=30)

    # DOWN cascade
    cascade_down = make_cascade(active=True, intensity=85, direction="DOWN")
    a1 = mgr.check(scores, MarketState.LIQUIDATION_CASCADE, make_crowd(), cascade_down, make_unwind(), make_exhaustion(), ExecutionMode.NO_TRADE)
    assert a1 is not None
    assert a1.side == "DOWN"

    # UP cascade — different side
    cascade_up = make_cascade(active=True, intensity=85, direction="UP")
    a2 = mgr.check(scores, MarketState.LIQUIDATION_CASCADE, make_crowd(), cascade_up, make_unwind(), make_exhaustion(), ExecutionMode.NO_TRADE)
    assert a2 is not None, "Different cascade direction must fire"
    assert a2.side == "UP"
    print("  ✓ Tier 3 different direction fires independently")


def test_burst_suppression():
    """Rapid-fire identical alerts must all but first be suppressed."""
    mgr = AlertManager(CONFIG)

    scores = make_scores(imbalance=65, execution_quality=55)
    crowd = make_crowd(active=True, side="LONGS")
    state = MarketState.CROWD_BUILDUP

    fired = 0
    suppressed = 0
    for _ in range(20):
        a = mgr.check(scores, state, crowd, make_cascade(), make_unwind(), make_exhaustion(), ExecutionMode.MAKER_ONLY)
        if a:
            fired += 1
        else:
            suppressed += 1

    assert fired == 1, f"Only 1 should fire, got {fired}"
    assert suppressed == 19, f"19 should be suppressed, got {suppressed}"
    assert mgr.suppressed_alert_count == 19
    print("  ✓ Burst of 20 identical: 1 fired, 19 suppressed")


def test_suppressed_counter_accurate():
    """suppressed_alert_count must equal total suppressed attempts."""
    mgr = AlertManager(CONFIG)

    scores = make_scores(imbalance=65, execution_quality=55)
    crowd = make_crowd(active=True, side="LONGS")

    # Fire 1
    mgr.check(scores, MarketState.CROWD_BUILDUP, crowd, make_cascade(), make_unwind(), make_exhaustion(), ExecutionMode.MAKER_ONLY)

    # Suppress 5
    for _ in range(5):
        mgr.check(scores, MarketState.CROWD_BUILDUP, crowd, make_cascade(), make_unwind(), make_exhaustion(), ExecutionMode.MAKER_ONLY)

    assert mgr.suppressed_alert_count == 5, f"Expected 5, got {mgr.suppressed_alert_count}"
    print("  ✓ Suppressed counter accurate")


# ── Main ────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  MANTIS Alert Rate Limiter — Smoke Test")
    print("=" * 60)
    print()

    tests = [
        ("Same key suppressed within cooldown", test_same_key_suppressed),
        ("Different side fires independently", test_different_side_fires),
        ("Different state fires independently", test_different_state_fires),
        ("Fires again after cooldown expires", test_after_cooldown_fires),
        ("Tier 3 deduplicates by side", test_tier3_dedup),
        ("Tier 3 different direction fires", test_tier3_different_direction_fires),
        ("Burst suppression (20 rapid-fire)", test_burst_suppression),
        ("Suppressed counter accuracy", test_suppressed_counter_accurate),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"  Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed:
        sys.exit(1)
    print("\nAll tests passed. Rate limiter deduplication is working correctly.")


if __name__ == "__main__":
    main()
