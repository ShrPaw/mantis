"""
MANTIS SPE — Orchestrator

Central pipeline coordinator for the 8-layer Structural Pressure Execution module.
Receives trade ticks, runs all layers sequentially, emits SPEEvent only when ALL pass.

Pipeline:
  L1  MantisState     → state gate (CASCADE/UNWIND)
  L2  Pressure        → crowd imbalance
  L3  Displacement    → forced move
  L4  Sweep           → structural sweep
  L5  Trap            → confirmation
  L6  ExecutionFilter → quality gate
  L7  Entry           → passive limit placement
  L8  Exit            → TP/SL levels
  →  SPEEvent         → emit if all layers pass + confidence ≥ threshold
"""

import logging
import time
from typing import Optional

from .config import SPEConfig
from .models import SPEEvent, SPESignal
from .mantis_state import MantisStateMachine
from .pressure import PressureDetector
from .displacement import DisplacementDetector
from .sweep import SweepDetector
from .trap import TrapDetector
from .execution_filter import ExecutionFilter
from .entry import EntryCalculator
from .exit import ExitCalculator
from ..context import EngineContext

logger = logging.getLogger(__name__)


class SPEOrchestrator:
    """
    Orchestrates the 8-layer SPE pipeline.
    Single entry point: on_trade(), on_book().

    Only emits STRUCTURAL_PRESSURE_EXECUTION events when all layers pass.
    """

    def __init__(self, ctx: EngineContext, config: SPEConfig | None = None):
        self.cfg = config or SPEConfig()
        self.ctx = ctx

        # Initialize all 8 layers
        self.state_machine = MantisStateMachine(self.cfg.state, ctx)
        self.pressure = PressureDetector(self.cfg.pressure, ctx)
        self.displacement = DisplacementDetector(self.cfg.displacement, ctx)
        self.sweep = SweepDetector(self.cfg.sweep, ctx)
        self.trap = TrapDetector(self.cfg.trap, ctx)
        self.exec_filter = ExecutionFilter(self.cfg.execution, ctx)
        self.entry = EntryCalculator(self.cfg.entry, ctx)
        self.exit_calc = ExitCalculator(self.cfg.exit, ctx)

        # Alert state
        self._last_alert_time: float = 0.0
        self._alerts_this_hour: int = 0
        self._hour_start: float = 0.0

        # Stats
        self._signals_evaluated: int = 0
        self._events_emitted: int = 0

        # Three-state layer accounting: pass / fail / not_evaluated
        # If layer N fails, layers N+1..end are not_evaluated (never reached).
        self._layer_stats: dict[str, dict[str, int]] = {
            "L1_context_gate":    {"pass": 0, "fail": 0, "not_evaluated": 0},
            "L2_pressure":        {"pass": 0, "fail": 0, "not_evaluated": 0},
            "L3_displacement":    {"pass": 0, "fail": 0, "not_evaluated": 0},
            "L4_sweep":           {"pass": 0, "fail": 0, "not_evaluated": 0},
            "L5_trap":            {"pass": 0, "fail": 0, "not_evaluated": 0},
            "L6_execution_filter": {"pass": 0, "fail": 0, "not_evaluated": 0},
            "L7_entry_zone":      {"pass": 0, "fail": 0, "not_evaluated": 0},
            "L8_exit_model":      {"pass": 0, "fail": 0, "not_evaluated": 0},
            "confidence_gate":    {"pass": 0, "fail": 0, "not_evaluated": 0},
        }
        self._layer_order: list[str] = [
            "L1_context_gate", "L2_pressure", "L3_displacement",
            "L4_sweep", "L5_trap", "L6_execution_filter",
            "L7_entry_zone", "L8_exit_model", "confidence_gate",
        ]

        logger.info("SPE Orchestrator initialized")

    def _mark_not_evaluated(self, from_index: int):
        """Mark layers from from_index onward as not_evaluated."""
        for key in self._layer_order[from_index:]:
            self._layer_stats[key]["not_evaluated"] += 1

    def on_trade(self, price: float, qty: float, delta: float,
                 timestamp: float) -> list[dict]:
        """
        Main entry point: called on every trade tick.
        Runs 8-layer pipeline with cascading accounting.
        Returns list of SPE events (usually empty).

        Layer accounting:
          - pass          → layer evaluated and passed
          - fail          → layer evaluated and failed
          - not_evaluated → layer was never reached (upstream failed)
        """
        if not self.cfg.enabled:
            return []

        self._signals_evaluated += 1

        # ── Layer 1: Context / State Gate ──
        mantis_state = self.state_machine.update(price, qty, delta, timestamp)

        # Compute scores needed for L1 composite gate
        # (L2-L6 must run to produce scores, but gate pass/fail is sequential)
        pressure_result = self.pressure.update(price, qty, delta, timestamp)
        crowd_direction = pressure_result["crowd_direction"]
        pressure_strength = pressure_result["pressure_strength"]

        disp_result = self.displacement.update(price, qty, delta, timestamp)
        displacement_detected = disp_result["displacement_detected"]
        displacement_direction = disp_result["displacement_direction"]

        sweep_result = self.sweep.update(price, qty, delta, timestamp)

        trap_result = self.trap.update(
            price, qty, delta, timestamp,
            crowd_direction=crowd_direction,
            displacement_direction=displacement_direction,
            displacement_origin=disp_result["displacement_origin"],
            displacement_end=disp_result["displacement_end"],
        )

        is_cascade = mantis_state == "CASCADE"
        exec_result = self.exec_filter.evaluate(timestamp, is_cascade=is_cascade)

        imbalance_score = self._compute_imbalance_score(
            pressure_strength, disp_result["displacement_strength"],
            sweep_result["sweep_detected"], trap_result["trap_detected"]
        )
        execution_quality = exec_result["execution_quality"]
        risk_score = self._compute_risk_score(
            mantis_state, pressure_result["funding_z"],
            disp_result["displacement_body_bps"], exec_result
        )

        # ── L1 Gate ──
        context_valid = False
        if mantis_state in ("CASCADE", "UNWIND"):
            context_valid = True
        elif (imbalance_score >= self.cfg.min_imbalance_score and
              execution_quality >= self.cfg.min_execution_quality and
              risk_score <= self.cfg.max_risk_score):
            context_valid = True

        if not context_valid:
            self._layer_stats["L1_context_gate"]["fail"] += 1
            self._mark_not_evaluated(1)  # L2-L8 + confidence = not_evaluated
            return []

        self._layer_stats["L1_context_gate"]["pass"] += 1

        # ── L2 Gate: Pressure ──
        if crowd_direction == "NONE":
            self._layer_stats["L2_pressure"]["fail"] += 1
            self._mark_not_evaluated(2)  # L3-L8 + confidence = not_evaluated
            return []

        self._layer_stats["L2_pressure"]["pass"] += 1

        # ── L3 Gate: Displacement ──
        if not displacement_detected:
            self._layer_stats["L3_displacement"]["fail"] += 1
            self._mark_not_evaluated(3)  # L4-L8 + confidence = not_evaluated
            return []

        self._layer_stats["L3_displacement"]["pass"] += 1

        # ── L4 Gate: Sweep ──
        if not sweep_result["sweep_detected"]:
            self._layer_stats["L4_sweep"]["fail"] += 1
            self._mark_not_evaluated(4)  # L5-L8 + confidence = not_evaluated
            return []

        self._layer_stats["L4_sweep"]["pass"] += 1

        # ── L5 Gate: Trap ──
        if not trap_result["trap_detected"]:
            self._layer_stats["L5_trap"]["fail"] += 1
            self._mark_not_evaluated(5)  # L6-L8 + confidence = not_evaluated
            return []

        self._layer_stats["L5_trap"]["pass"] += 1

        # ── L6 Gate: Execution Filter ──
        if execution_quality < self.cfg.min_execution_quality:
            if not (is_cascade and execution_quality >= 50):
                self._layer_stats["L6_execution_filter"]["fail"] += 1
                self._mark_not_evaluated(6)  # L7-L8 + confidence = not_evaluated
                return []

        self._layer_stats["L6_execution_filter"]["pass"] += 1

        # ── Determine direction ──
        direction = self._determine_direction(
            crowd_direction, displacement_direction, trap_result["trap_type"]
        )
        if not direction:
            # Direction derivation failed — counts as L7 not applicable
            self._layer_stats["L7_entry_zone"]["fail"] += 1
            self._mark_not_evaluated(7)  # L8 + confidence = not_evaluated
            return []

        # ── L7 Gate: Entry ──
        entry_result = self.entry.calculate(
            direction, disp_result["displacement_origin"],
            disp_result["displacement_end"], timestamp
        )
        if not entry_result["valid"]:
            self._layer_stats["L7_entry_zone"]["fail"] += 1
            self._mark_not_evaluated(7)  # L8 + confidence = not_evaluated
            return []

        self._layer_stats["L7_entry_zone"]["pass"] += 1

        # ── L8 Gate: Exit ──
        exit_result = self.exit_calc.calculate(
            direction, entry_result["entry_price"],
            disp_result["displacement_origin"],
            disp_result["displacement_end"], timestamp
        )
        if not exit_result["valid"]:
            self._layer_stats["L8_exit_model"]["fail"] += 1
            self._mark_not_evaluated(8)  # confidence = not_evaluated
            return []

        self._layer_stats["L8_exit_model"]["pass"] += 1

        # ── Confidence Gate ──
        confidence_score = self._compute_confidence(
            imbalance_score, execution_quality, risk_score,
            pressure_strength, disp_result["displacement_strength"],
            trap_result, sweep_result, exec_result, mantis_state
        )

        if confidence_score < self.cfg.alert.min_confidence_score:
            self._layer_stats["confidence_gate"]["fail"] += 1
            return []

        self._layer_stats["confidence_gate"]["pass"] += 1

        # ── Alert Cooldown ──
        if not self._check_alert_cooldown(timestamp):
            return []

        # ── ALL LAYERS PASSED — Emit SPE Event ──
        event = SPEEvent(
            direction=direction,
            mantis_state=mantis_state,
            imbalance_score=imbalance_score,
            execution_quality=execution_quality,
            risk_score=risk_score,
            crowd_direction=crowd_direction,
            displacement_strength=disp_result["displacement_strength"],
            trap_detected=True,
            entry_price=entry_result["entry_price"],
            stop_loss=exit_result["stop_loss"],
            tp_levels=exit_result["tp_levels"],
            confidence_score=confidence_score,
            pressure_strength=pressure_strength,
            funding_z=pressure_result["funding_z"],
            sweep_detected=sweep_result["sweep_detected"],
            sweep_direction=sweep_result.get("sweep_direction", ""),
            spread_bps=exec_result["spread_bps"],
            displacement_origin=disp_result["displacement_origin"],
            displacement_end=disp_result["displacement_end"],
            displacement_body_bps=disp_result["displacement_body_bps"],
            explanation=self._build_explanation(
                direction, mantis_state, crowd_direction,
                disp_result, trap_result, sweep_result, confidence_score
            ),
        )

        self._events_emitted += 1
        self._last_alert_time = timestamp

        logger.info(
            f"SPE EVENT EMITTED: {direction} | state={mantis_state} | "
            f"confidence={confidence_score:.1f} | entry={entry_result['entry_price']}"
        )

        return [event.to_dict()]

    def on_book(self, bids: list[tuple[float, float]],
                asks: list[tuple[float, float]]):
        """Called on every order book update."""
        # Execution filter uses book state from ctx directly
        pass

    def _determine_direction(self, crowd_direction: str,
                             displacement_direction: str,
                             trap_type: str) -> str:
        """
        Determine trade direction from crowd + displacement + trap.

        LONG_CROWD + UP displacement + trap → SHORT (fade the crowd)
        SHORT_CROWD + DOWN displacement + trap → LONG (fade the crowd)

        The trap means the crowd got trapped — we fade them.
        """
        if crowd_direction == "LONG_CROWD" and displacement_direction == "UP":
            return "SHORT"  # Crowd long, got trapped after up move
        elif crowd_direction == "SHORT_CROWD" and displacement_direction == "DOWN":
            return "LONG"  # Crowd short, got trapped after down move

        # If displacement and crowd disagree, use displacement direction
        if displacement_direction == "UP" and crowd_direction == "SHORT_CROWD":
            return "LONG"
        elif displacement_direction == "DOWN" and crowd_direction == "LONG_CROWD":
            return "SHORT"

        return ""

    def _compute_imbalance_score(self, pressure_strength: float,
                                 displacement_strength: float,
                                 sweep_detected: bool,
                                 trap_detected: bool) -> float:
        """
        Compute composite imbalance score (0-100).
        """
        score = 0.0

        # Pressure contribution (40%)
        score += pressure_strength * 0.4

        # Displacement contribution (35%)
        score += displacement_strength * 0.35

        # Sweep bonus (15%)
        if sweep_detected:
            score += 15.0

        # Trap bonus (10%)
        if trap_detected:
            score += 10.0

        return min(score, 100.0)

    def _compute_risk_score(self, mantis_state: str, funding_z: float,
                            body_bps: float, exec_result: dict) -> float:
        """
        Compute risk score (0-100). Lower is better.
        """
        risk = 50.0  # baseline

        # Extreme funding = higher risk
        risk += abs(funding_z) * 5

        # Large body = higher risk (more extended)
        risk += min(body_bps / 10, 20)

        # Poor execution = higher risk
        if not exec_result.get("spread_ok", True):
            risk += 10
        if not exec_result.get("depth_ok", True):
            risk += 10
        if exec_result.get("book_thinning", False):
            risk += 15

        # CASCADE context reduces risk perception
        if mantis_state == "CASCADE":
            risk -= 15

        return max(0, min(risk, 100))

    def _compute_confidence(self, imbalance_score: float,
                            execution_quality: float, risk_score: float,
                            pressure_strength: float,
                            displacement_strength: float,
                            trap_result: dict, sweep_result: dict,
                            exec_result: dict, mantis_state: str) -> float:
        """
        Compute confidence score (0-100).
        """
        confidence = 0.0

        # Imbalance quality (30%)
        confidence += imbalance_score * 0.3

        # Execution quality (25%)
        confidence += execution_quality * 0.25

        # Risk adjustment (15%) — lower risk = higher confidence
        confidence += (100 - risk_score) * 0.15

        # Trap strength (15%)
        trap_bonus = 0
        if trap_result["trap_detected"]:
            trap_bonus = 80
            if trap_result.get("rapid_reversal"):
                trap_bonus = 100
            elif trap_result.get("liquidity_taken"):
                trap_bonus = 90
        confidence += trap_bonus * 0.15

        # Sweep confirmation (10%)
        if sweep_result.get("sweep_detected"):
            confidence += 8.0

        # State bonus (5%)
        if mantis_state in ("CASCADE", "UNWIND"):
            confidence += 5.0

        return min(confidence, 100.0)

    def _check_alert_cooldown(self, timestamp: float) -> bool:
        """Check if alert can fire (cooldown + rate limit)."""
        # Cooldown check
        if timestamp - self._last_alert_time < self.cfg.alert.cooldown_seconds:
            return False

        # Hourly rate limit
        if self._hour_start == 0 or timestamp - self._hour_start > 3600:
            self._hour_start = timestamp
            self._alerts_this_hour = 0

        if self._alerts_this_hour >= self.cfg.alert.max_alerts_per_hour:
            return False

        self._alerts_this_hour += 1
        return True

    def _build_explanation(self, direction: str, mantis_state: str,
                           crowd_direction: str, disp_result: dict,
                           trap_result: dict, sweep_result: dict,
                           confidence: float) -> str:
        """Build human-readable explanation of the SPE signal."""
        parts = [
            f"SPE {direction} | State: {mantis_state}",
            f"Crowd: {crowd_direction} ({disp_result['displacement_strength']:.0f}/100 displacement)",
        ]

        if sweep_result.get("sweep_detected"):
            parts.append(f"Sweep: {sweep_result['sweep_direction']} @ {sweep_result['sweep_level']:.2f}")

        parts.append(f"Trap: {trap_result['trap_type']}")
        parts.append(f"Confidence: {confidence:.1f}/100")

        return " | ".join(parts)

    def get_stats(self) -> dict:
        """Get SPE orchestrator statistics with three-state layer accounting."""
        # layer_stats is a flat dict: layer_name -> {pass, fail, not_evaluated}
        layer_stats = {}
        for key in self._layer_order:
            layer_stats[key] = self._layer_stats[key].copy()

        return {
            "enabled": self.cfg.enabled,
            "signals_evaluated": self._signals_evaluated,
            "events_emitted": self._events_emitted,
            "layer_stats": layer_stats,
            "state": self.state_machine.state,
        }

    def get_layer_metrics(self) -> dict:
        """
        Get structured layer metrics for persistence to spe_metrics.json.
        Includes per-layer pass/fail/not_evaluated counts and summary stats.
        """
        layer_counts = {}
        for key in self._layer_order:
            layer_counts[key] = self._layer_stats[key].copy()

        # Count full pipeline passes (all 8 + confidence = pass)
        full_passes = self._layer_stats["confidence_gate"]["pass"]

        return {
            "raw_evaluations": self._signals_evaluated,
            "layer_counts": layer_counts,
            "full_8_layer_passes": full_passes,
            "emitted_events": self._events_emitted,
            "current_state": self.state_machine.state,
        }

    def validate_layer_accounting(self) -> dict:
        """
        Validate the accounting invariant:
          For each layer: pass + fail + not_evaluated == raw_evaluations

        Returns:
            {
                "accounting_valid": bool,
                "accounting_errors": [str, ...],
                "raw_evaluations": int,
            }
        """
        errors = []
        raw = self._signals_evaluated

        for key in self._layer_order:
            stats = self._layer_stats[key]
            total = stats["pass"] + stats["fail"] + stats["not_evaluated"]
            if total != raw:
                errors.append(
                    f"{key}: pass({stats['pass']}) + fail({stats['fail']}) + "
                    f"not_evaluated({stats['not_evaluated']}) = {total} != raw_evaluations({raw})"
                )

        return {
            "accounting_valid": len(errors) == 0,
            "accounting_errors": errors,
            "raw_evaluations": raw,
        }
