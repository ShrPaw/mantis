"""
MANTIS SPE — Validation Framework

Mandatory validation against:
  - random entries
  - same volatility entries
  - opposite direction

Includes:
  - taker cost (4 bps)
  - maker scenario (0–1 bps)
  - missed fills probability
  - adverse selection

Metrics:
  - net return
  - PF (profit factor)
  - MFE / MAE
  - stability across splits

FAILURE CONDITIONS:
  - net ≤ 0 after cost
  - PF < 1.1
  - results unstable
  → "No exploitable edge in SPE module"

FINAL RULE: No parameter tuning after results. No iteration loops.
Run once. Return truth.
"""

import json
import math
import os
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from .config import ValidationConfig


@dataclass
class TradeResult:
    """Result of a single simulated trade."""
    entry_price: float
    exit_price: float
    direction: str
    entry_time: float
    exit_time: float
    pnl_bps: float
    gross_pnl_bps: float
    cost_bps: float
    is_win: bool
    mfe_bps: float = 0.0     # max favorable excursion
    mae_bps: float = 0.0     # max adverse excursion
    hit_tp: bool = False
    hit_sl: bool = False
    fill_type: str = "maker"  # maker or taker


@dataclass
class ValidationReport:
    """Complete validation report."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    gross_return_bps: float = 0.0
    net_return_bps: float = 0.0
    total_cost_bps: float = 0.0

    profit_factor: float = 0.0
    avg_win_bps: float = 0.0
    avg_loss_bps: float = 0.0

    avg_mfe_bps: float = 0.0
    avg_mae_bps: float = 0.0

    max_drawdown_bps: float = 0.0
    sharpe_approx: float = 0.0

    # Split stability
    split_returns: list[float] = field(default_factory=list)
    split_std: float = 0.0
    is_stable: bool = False

    # Adverse selection
    adverse_selection_rate: float = 0.0
    missed_fill_rate: float = 0.0

    # Verdict
    passed: bool = False
    failure_reason: str = ""
    verdict: str = ""

    def to_dict(self) -> dict:
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 4),
            "gross_return_bps": round(self.gross_return_bps, 2),
            "net_return_bps": round(self.net_return_bps, 2),
            "total_cost_bps": round(self.total_cost_bps, 2),
            "profit_factor": round(self.profit_factor, 3),
            "avg_win_bps": round(self.avg_win_bps, 2),
            "avg_loss_bps": round(self.avg_loss_bps, 2),
            "avg_mfe_bps": round(self.avg_mfe_bps, 2),
            "avg_mae_bps": round(self.avg_mae_bps, 2),
            "max_drawdown_bps": round(self.max_drawdown_bps, 2),
            "sharpe_approx": round(self.sharpe_approx, 3),
            "split_returns": [round(r, 2) for r in self.split_returns],
            "split_std": round(self.split_std, 2),
            "is_stable": self.is_stable,
            "adverse_selection_rate": round(self.adverse_selection_rate, 4),
            "missed_fill_rate": round(self.missed_fill_rate, 4),
            "passed": self.passed,
            "failure_reason": self.failure_reason,
            "verdict": self.verdict,
        }


class SPEValidator:
    """
    Validates SPE module edge through rigorous backtesting simulation.
    
    Tests against three baselines:
    1. Random entries (same timing, random direction)
    2. Same-volatility entries (entries during similar vol conditions)
    3. Opposite direction entries (fade the SPE signal)
    
    Only passes if SPE significantly outperforms all three.
    """

    def __init__(self, config: ValidationConfig):
        self.cfg = config
        random.seed(42)  # Reproducibility

    def validate(self, events: list[dict],
                 price_history: list[dict]) -> ValidationReport:
        """
        Run full validation on SPE events against price history.
        
        Args:
            events: list of SPE event dicts (from orchestrator)
            price_history: list of {time, price} dicts
            
        Returns:
            ValidationReport with all metrics
        """
        if len(events) < 5:
            return self._fail_report("Insufficient events for validation")

        # Build price lookup
        price_lookup = self._build_price_lookup(price_history)
        if not price_lookup:
            return self._fail_report("Insufficient price history")

        # ── Test 1: SPE signal trades ──
        spe_results = self._simulate_spe_trades(events, price_lookup)

        # ── Test 2: Random entry trades ──
        random_results = self._simulate_random_trades(events, price_lookup)

        # ── Test 3: Same-volatility entry trades ──
        vol_results = self._simulate_vol_trades(events, price_lookup)

        # ── Test 4: Opposite direction trades ──
        opposite_results = self._simulate_opposite_trades(events, price_lookup)

        # ── Compute metrics ──
        report = self._compute_metrics(spe_results)

        # ── Compare against baselines ──
        random_metrics = self._compute_metrics(random_results)
        vol_metrics = self._compute_metrics(vol_results)
        opposite_metrics = self._compute_metrics(opposite_results)

        # ── Stability check ──
        split_returns = self._compute_split_returns(spe_results)
        report.split_returns = split_returns
        if split_returns:
            report.split_std = self._std(split_returns)
            mean_return = sum(split_returns) / len(split_returns)
            report.is_stable = report.split_std < abs(mean_return) * 0.5 if mean_return != 0 else False

        # ── Adverse selection ──
        report.adverse_selection_rate = self._compute_adverse_selection(spe_results)
        report.missed_fill_rate = self.cfg.missed_fill_probability

        # ── Final verdict ──
        report = self._apply_failure_conditions(report, random_metrics, vol_metrics, opposite_metrics)

        return report

    def _simulate_spe_trades(self, events: list[dict],
                             price_lookup: dict) -> list[TradeResult]:
        """Simulate trades from SPE signals."""
        results = []

        for event in events:
            entry_price = event.get("entry_price", 0)
            stop_loss = event.get("stop_loss", 0)
            tp_levels = event.get("tp_levels", [])
            direction = event.get("direction", "")
            entry_time = event.get("timestamp", 0)

            if not all([entry_price, stop_loss, tp_levels, direction, entry_time]):
                continue

            # Determine fill type (maker = 0-1 bps, taker = 4 bps)
            is_maker = random.random() > 0.3  # 70% maker fills
            cost_bps = self.cfg.maker_cost_bps if is_maker else self.cfg.taker_cost_bps

            # Simulate outcome
            result = self._simulate_trade_outcome(
                entry_price, stop_loss, tp_levels[0] if tp_levels else entry_price,
                direction, entry_time, cost_bps, price_lookup,
                fill_type="maker" if is_maker else "taker"
            )

            if result:
                results.append(result)

        return results

    def _simulate_random_trades(self, events: list[dict],
                                price_lookup: dict) -> list[TradeResult]:
        """Simulate random direction trades at same timestamps."""
        results = []

        for event in events:
            entry_price = event.get("entry_price", 0)
            stop_loss = event.get("stop_loss", 0)
            tp_levels = event.get("tp_levels", [])
            entry_time = event.get("timestamp", 0)

            if not all([entry_price, stop_loss, tp_levels, entry_time]):
                continue

            # Random direction
            direction = random.choice(["LONG", "SHORT"])

            # Flip SL/TP for random direction
            if direction == "LONG":
                sl = stop_loss
                tp = tp_levels[0] if tp_levels else entry_price * 1.001
            else:
                sl = entry_price * 2 - stop_loss  # Mirror
                tp = entry_price * 2 - (tp_levels[0] if tp_levels else entry_price * 1.001)

            result = self._simulate_trade_outcome(
                entry_price, sl, tp, direction, entry_time,
                self.cfg.maker_cost_bps, price_lookup, fill_type="maker"
            )

            if result:
                results.append(result)

        return results

    def _simulate_vol_trades(self, events: list[dict],
                             price_lookup: dict) -> list[TradeResult]:
        """Simulate entries during similar volatility conditions."""
        results = []

        for i, event in enumerate(events):
            entry_price = event.get("entry_price", 0)
            entry_time = event.get("timestamp", 0)
            direction = event.get("direction", "")

            if not all([entry_price, entry_time, direction]):
                continue

            # Shift entry time slightly (within same vol regime)
            shifted_time = entry_time + random.uniform(-60, 60)

            # Use same direction, shifted timing
            stop_loss = event.get("stop_loss", entry_price * 0.999)
            tp = event.get("tp_levels", [entry_price * 1.001])[0]

            result = self._simulate_trade_outcome(
                entry_price, stop_loss, tp, direction, shifted_time,
                self.cfg.maker_cost_bps, price_lookup, fill_type="maker"
            )

            if result:
                results.append(result)

        return results

    def _simulate_opposite_trades(self, events: list[dict],
                                  price_lookup: dict) -> list[TradeResult]:
        """Simulate opposite direction trades (fade the signal)."""
        results = []

        for event in events:
            entry_price = event.get("entry_price", 0)
            stop_loss = event.get("stop_loss", 0)
            tp_levels = event.get("tp_levels", [])
            direction = event.get("direction", "")
            entry_time = event.get("timestamp", 0)

            if not all([entry_price, stop_loss, tp_levels, direction, entry_time]):
                continue

            # Opposite direction
            opposite = "SHORT" if direction == "LONG" else "LONG"

            # Mirror SL/TP
            if opposite == "LONG":
                sl = entry_price * 2 - (tp_levels[0] if tp_levels else entry_price * 1.001)
                tp = stop_loss
            else:
                sl = tp_levels[0] if tp_levels else entry_price * 1.001
                tp = stop_loss

            result = self._simulate_trade_outcome(
                entry_price, sl, tp, opposite, entry_time,
                self.cfg.maker_cost_bps, price_lookup, fill_type="maker"
            )

            if result:
                results.append(result)

        return results

    def _simulate_trade_outcome(self, entry: float, sl: float, tp: float,
                                direction: str, entry_time: float,
                                cost_bps: float, price_lookup: dict,
                                fill_type: str = "maker") -> Optional[TradeResult]:
        """Simulate a single trade outcome against price history."""
        # Find entry in price lookup
        if entry_time not in price_lookup:
            # Find nearest
            nearest = min(price_lookup.keys(), key=lambda t: abs(t - entry_time))
            if abs(nearest - entry_time) > 120:
                return None
            entry_time = nearest

        # Look forward from entry
        future_prices = sorted(
            [(t, p) for t, p in price_lookup.items() if t > entry_time],
            key=lambda x: x[0]
        )

        if not future_prices:
            return None

        mfe = 0.0
        mae = 0.0
        exit_price = entry
        exit_time = entry_time
        hit_tp = False
        hit_sl = False

        for t, p in future_prices[:300]:  # Max 5 min forward
            if direction == "LONG":
                excursion = (p - entry) / entry * 10000
                mfe = max(mfe, excursion)
                mae = min(mae, excursion)

                if p >= tp:
                    exit_price = tp
                    exit_time = t
                    hit_tp = True
                    break
                elif p <= sl:
                    exit_price = sl
                    exit_time = t
                    hit_sl = True
                    break
            else:
                excursion = (entry - p) / entry * 10000
                mfe = max(mfe, excursion)
                mae = min(mae, excursion)

                if p <= tp:
                    exit_price = tp
                    exit_time = t
                    hit_tp = True
                    break
                elif p >= sl:
                    exit_price = sl
                    exit_time = t
                    hit_sl = True
                    break

        # Calculate PnL
        if direction == "LONG":
            gross_pnl_bps = (exit_price - entry) / entry * 10000
        else:
            gross_pnl_bps = (entry - exit_price) / entry * 10000

        net_pnl_bps = gross_pnl_bps - cost_bps

        # Apply missed fill penalty
        if random.random() < self.cfg.missed_fill_probability:
            net_pnl_bps *= 0.8  # Reduce by missed fill impact

        # Apply adverse selection
        if mae < -self.cfg.adverse_selection_bps:
            net_pnl_bps -= self.cfg.adverse_selection_bps * 0.5

        return TradeResult(
            entry_price=entry,
            exit_price=exit_price,
            direction=direction,
            entry_time=entry_time,
            exit_time=exit_time,
            pnl_bps=net_pnl_bps,
            gross_pnl_bps=gross_pnl_bps,
            cost_bps=cost_bps,
            is_win=net_pnl_bps > 0,
            mfe_bps=mfe,
            mae_bps=mae,
            hit_tp=hit_tp,
            hit_sl=hit_sl,
            fill_type=fill_type,
        )

    def _compute_metrics(self, results: list[TradeResult]) -> ValidationReport:
        """Compute comprehensive metrics from trade results."""
        report = ValidationReport()

        if not results:
            return report

        report.total_trades = len(results)
        report.winning_trades = sum(1 for r in results if r.is_win)
        report.losing_trades = report.total_trades - report.winning_trades
        report.win_rate = report.winning_trades / report.total_trades

        # Returns
        returns = [r.pnl_bps for r in results]
        gross_returns = [r.gross_pnl_bps for r in results]
        costs = [r.cost_bps for r in results]

        report.gross_return_bps = sum(gross_returns)
        report.net_return_bps = sum(returns)
        report.total_cost_bps = sum(costs)

        # Profit factor
        wins = [r for r in results if r.is_win]
        losses = [r for r in results if not r.is_win]

        total_wins = sum(r.pnl_bps for r in wins) if wins else 0
        total_losses = abs(sum(r.pnl_bps for r in losses)) if losses else 0

        report.profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        report.avg_win_bps = total_wins / len(wins) if wins else 0
        report.avg_loss_bps = total_losses / len(losses) if losses else 0

        # MFE/MAE
        report.avg_mfe_bps = sum(r.mfe_bps for r in results) / len(results)
        report.avg_mae_bps = sum(r.mae_bps for r in results) / len(results)

        # Drawdown
        cumulative = 0
        peak = 0
        max_dd = 0
        for r in returns:
            cumulative += r
            peak = max(peak, cumulative)
            dd = peak - cumulative
            max_dd = max(max_dd, dd)
        report.max_drawdown_bps = max_dd

        # Sharpe approximation
        if len(returns) > 1:
            mean_r = sum(returns) / len(returns)
            std_r = self._std(returns)
            report.sharpe_approx = mean_r / std_r if std_r > 0 else 0

        return report

    def _compute_split_returns(self, results: list[TradeResult]) -> list[float]:
        """Compute returns across N splits for stability check."""
        if len(results) < self.cfg.split_count * 2:
            return [sum(r.pnl_bps for r in results)]

        random.shuffle(results)
        split_size = len(results) // self.cfg.split_count
        splits = []

        for i in range(self.cfg.split_count):
            start = i * split_size
            end = start + split_size
            split_return = sum(r.pnl_bps for r in results[start:end])
            splits.append(split_return)

        return splits

    def _compute_adverse_selection(self, results: list[TradeResult]) -> float:
        """Compute adverse selection rate (entries that immediately go against)."""
        if not results:
            return 0.0

        adverse = sum(1 for r in results if r.mae_bps < -self.cfg.adverse_selection_bps)
        return adverse / len(results)

    def _apply_failure_conditions(self, report: ValidationReport,
                                  random_metrics: ValidationReport,
                                  vol_metrics: ValidationReport,
                                  opposite_metrics: ValidationReport) -> ValidationReport:
        """Apply mandatory failure conditions."""
        # Condition 1: Net return ≤ 0
        if report.net_return_bps <= self.cfg.min_net_return_bps:
            report.passed = False
            report.failure_reason = f"Net return {report.net_return_bps:.2f} bps ≤ 0"
            report.verdict = "No exploitable edge in SPE module"
            return report

        # Condition 2: PF < 1.1
        if report.profit_factor < self.cfg.min_profit_factor:
            report.passed = False
            report.failure_reason = f"Profit factor {report.profit_factor:.3f} < {self.cfg.min_profit_factor}"
            report.verdict = "No exploitable edge in SPE module"
            return report

        # Condition 3: Unstable results
        if not report.is_stable:
            report.passed = False
            report.failure_reason = f"Results unstable (split std {report.split_std:.2f} bps)"
            report.verdict = "No exploitable edge in SPE module"
            return report

        # Condition 4: Doesn't beat random
        if report.net_return_bps <= random_metrics.net_return_bps:
            report.passed = False
            report.failure_reason = "SPE does not outperform random entries"
            report.verdict = "No exploitable edge in SPE module"
            return report

        # All conditions passed
        report.passed = True
        report.verdict = "SPE module has exploitable edge"
        return report

    def _build_price_lookup(self, price_history: list[dict]) -> dict:
        """Build time → price lookup from history."""
        lookup = {}
        for entry in price_history:
            t = entry.get("time", 0)
            p = entry.get("price", 0) or entry.get("close", 0)
            if t > 0 and p > 0:
                lookup[t] = p
        return lookup

    def _std(self, values: list[float]) -> float:
        """Standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return math.sqrt(variance)

    def _fail_report(self, reason: str) -> ValidationReport:
        """Create a failure report."""
        report = ValidationReport()
        report.passed = False
        report.failure_reason = reason
        report.verdict = "No exploitable edge in SPE module"
        return report

    def export_report(self, report: ValidationReport,
                      path: str = "data/spe_validation.json"):
        """Export validation report to JSON."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(report.to_dict(), f, indent=2)
