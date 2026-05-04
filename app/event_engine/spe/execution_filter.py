"""
MANTIS SPE — Layer 6: Execution Quality Filter

Only allows execution if:
  - spread < threshold
  - no order book thinning
  - stable depth
  - no extreme volatility spike (unless cascade context)

This is the maker-logic gate: ensures execution conditions are clean.
"""

from collections import deque

from app.event_engine.spe.config import ExecutionFilterConfig
from app.event_engine.context import EngineContext


class ExecutionFilter:
    """
    Filters execution based on market microstructure quality.
    Ensures we only execute when conditions are favorable for passive fills.
    """

    def __init__(self, config: ExecutionFilterConfig, ctx: EngineContext):
        self.cfg = config
        self.ctx = ctx

        # Volatility tracking
        self._price_changes: deque = deque(maxlen=100)
        self._price_timestamps: deque = deque(maxlen=100)

        # Depth tracking
        self._depth_history: deque = deque(maxlen=50)

    def evaluate(self, timestamp: float, is_cascade: bool = False) -> dict:
        """
        Evaluate execution quality. Returns quality metrics.

        Args:
            timestamp: current time
            is_cascade: if True, allows higher volatility
        """
        book = self.ctx.book
        buffer = self.ctx.buffer

        # 1. Spread check
        spread_bps = book.spread_bps
        spread_ok = spread_bps <= self.cfg.max_spread_bps

        # 2. Depth check
        depth_btc = self._compute_depth(book)
        depth_ok = depth_btc >= self.cfg.min_depth_btc

        # Store depth for stability check
        self._depth_history.append(depth_btc)

        # 3. Depth stability (not thinning)
        depth_stable = self._check_depth_stability()

        # 4. Volatility spike check
        volatility_spike = self._check_volatility_spike(timestamp)
        volatility_ok = True
        if volatility_spike and not is_cascade:
            volatility_ok = False

        # 5. Book thinning check
        book_thinning = self._check_book_thinning(book)

        # Overall execution quality (0-100)
        quality = 0.0
        if spread_ok:
            quality += 30  # 30% for spread
        if depth_ok and depth_stable:
            quality += 30  # 30% for depth
        if not book_thinning:
            quality += 20  # 20% for book integrity
        if volatility_ok:
            quality += 20  # 20% for volatility

        return {
            "execution_quality": quality,
            "spread_bps": spread_bps,
            "spread_ok": spread_ok,
            "depth_btc": depth_btc,
            "depth_ok": depth_ok,
            "depth_stable": depth_stable,
            "volatility_ok": volatility_ok,
            "book_thinning": book_thinning,
        }

    def _compute_depth(self, book) -> float:
        """Compute total depth in top N levels for both sides."""
        total = 0.0

        # Bid depth
        sorted_bids = sorted(book.bids.items(), key=lambda x: -x[0])
        for _, qty in sorted_bids[:self.cfg.depth_levels]:
            total += qty

        # Ask depth
        sorted_asks = sorted(book.asks.items(), key=lambda x: x[0])
        for _, qty in sorted_asks[:self.cfg.depth_levels]:
            total += qty

        return total

    def _check_depth_stability(self) -> bool:
        """Check if depth is stable (not dropping rapidly)."""
        if len(self._depth_history) < 5:
            return True  # Assume stable with insufficient data

        recent = list(self._depth_history)[-5:]
        older = list(self._depth_history)[-10:-5] if len(self._depth_history) >= 10 else recent

        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)

        if older_avg <= 0:
            return True

        # Depth dropped by more than 50% = thinning
        if recent_avg < older_avg * 0.5:
            return False

        return True

    def _check_volatility_spike(self, timestamp: float) -> bool:
        """Check if volatility is spiking."""
        buffer = self.ctx.buffer
        prices, _, _, timestamps = buffer.get_window(30, timestamp)

        if len(prices) < 5:
            return False

        # Compute recent price change rate
        price_range = max(prices) - min(prices)
        avg_price = sum(prices) / len(prices) if prices else 1

        if avg_price <= 0:
            return False

        range_bps = (price_range / avg_price) * 10000

        # Store for baseline
        self._price_changes.append(range_bps)

        if len(self._price_changes) < 10:
            return False

        # Compare current to baseline
        baseline = sum(list(self._price_changes)[:-1]) / (len(self._price_changes) - 1)

        if baseline <= 0:
            return False

        # Spike = current > N times baseline
        return range_bps > baseline * self.cfg.max_volatility_spike_mult

    def _check_book_thinning(self, book) -> bool:
        """
        Check if order book is thinning (walls disappearing).
        Compares current depth to recent average.
        """
        if len(self._depth_history) < 3:
            return False  # Can't determine

        current = self._depth_history[-1]
        avg = sum(list(self._depth_history)[:-1]) / (len(self._depth_history) - 1)

        if avg <= 0:
            return False

        # Thinning: current depth < 30% of average
        return current < avg * 0.3
