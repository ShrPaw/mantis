"""
Large Trade Cluster Detector — Detects clusters of large trades.
"""

from ..base import BaseEventDetector
from ..models import LargeTradeClusterEvent, MicrostructureEvent


class LargeTradeClusterDetector(BaseEventDetector):

    @property
    def event_type(self) -> str:
        return "large_trade_cluster"

    def update(self, trade_price: float, trade_qty: float,
               trade_delta: float, timestamp: float) -> list[MicrostructureEvent]:
        # This detector is triggered by the manager when large trades arrive
        # It checks for clusters in the recent large trade history
        cfg = self.ctx.config.large_trade_cluster
        ctx = self.ctx

        window_trades = ctx.large_trades.get_window(cfg.cluster_window_seconds, timestamp)
        if len(window_trades) < cfg.min_cluster_count:
            return []

        total_vol = sum(t["qty"] for t in window_trades)
        if total_vol < cfg.min_cluster_volume_btc:
            return []

        # Check percentile rank of this cluster
        # Compare total volume to other windows
        vol_pct = ctx.buffer.percentile_volume(total_vol, cfg.cluster_window_seconds, timestamp)

        avg_size = total_vol / len(window_trades)
        max_size = max(t["qty"] for t in window_trades)

        # Determine side from delta in the window
        prices, _, deltas, _ = ctx.buffer.get_window(cfg.cluster_window_seconds, timestamp)
        net_delta = sum(deltas) if deltas else 0
        side = "buy_cluster" if net_delta > 0 else "sell_cluster"

        # Price response
        price_resp = (prices[-1] - prices[0]) if len(prices) > 1 else 0

        # Continuation or failure
        recent_prices, _, _, _ = ctx.buffer.get_window(5, timestamp)
        if len(recent_prices) > 1:
            recent_move = recent_prices[-1] - recent_prices[0]
            if (side == "buy_cluster" and recent_move > 5) or (side == "sell_cluster" and recent_move < -5):
                label = "continuation"
            else:
                label = "failure"
        else:
            label = "pending"

        regime = ctx.classify_regime()
        scorer = ctx.scoring
        scores = scorer.score_large_cluster(
            cluster_count=len(window_trades),
            volume_pct=vol_pct,
            percentile=vol_pct,
            regime=regime,
        )

        explanation = (
            f"{side.replace('_', ' ').title()} detected: {len(window_trades)} large trades "
            f"totaling {total_vol:.2f} BTC in {cfg.cluster_window_seconds}s. "
            f"Avg size {avg_size:.3f} BTC, max {max_size:.3f} BTC. "
            f"Price response: {price_resp:+.1f} USD. Status: {label}."
        )

        return [LargeTradeClusterEvent(
            price=trade_price,
            timestamp=timestamp,
            side=side,
            explanation=explanation,
            scores=scores,
            total_cluster_volume=total_vol,
            number_of_large_trades=len(window_trades),
            average_trade_size=avg_size,
            max_trade_size=max_size,
            local_percentile_rank=vol_pct,
            price_response_after_cluster=price_resp,
            continuation_or_failure_label=label,
            raw_metrics={
                "cluster_count": len(window_trades),
                "total_volume": total_vol,
                "avg_size": avg_size,
                "max_size": max_size,
            },
            context_metrics={"regime": regime, "label": label},
        )]
