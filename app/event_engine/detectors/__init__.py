"""MANTIS Event Engine — Detectors Package"""

from app.event_engine.detectors.absorption import AbsorptionDetector
from app.event_engine.detectors.exhaustion import ExhaustionDetector
from app.event_engine.detectors.sweep import SweepDetector
from app.event_engine.detectors.divergence import DivergenceDetector
from app.event_engine.detectors.imbalance import ImbalanceDetector
from app.event_engine.detectors.large_trades import LargeTradeClusterDetector
from app.event_engine.detectors.range_break import RangeBreakDetector
from app.event_engine.detectors.vwap import VWAPDetector

ALL_DETECTORS = [
    AbsorptionDetector,
    ExhaustionDetector,
    SweepDetector,
    DivergenceDetector,
    ImbalanceDetector,
    LargeTradeClusterDetector,
    RangeBreakDetector,
    VWAPDetector,
]
