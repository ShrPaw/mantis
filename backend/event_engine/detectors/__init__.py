"""MANTIS Event Engine — Detectors Package"""

from .absorption import AbsorptionDetector
from .exhaustion import ExhaustionDetector
from .sweep import SweepDetector
from .divergence import DivergenceDetector
from .imbalance import ImbalanceDetector
from .large_trades import LargeTradeClusterDetector
from .range_break import RangeBreakDetector
from .vwap import VWAPDetector

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
