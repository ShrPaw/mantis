"""
Auction Failure Research — Detectors

Four primitive event classes built on auction mechanics.
All thresholds are relative (bps, percentile, ratio).
No fixed USD amounts.

1. failed_aggressive_sell — sell aggression fails to move price lower
2. failed_aggressive_buy  — buy aggression fails to move price higher
3. breakout_acceptance    — price breaks level, holds, flow supports
4. breakout_rejection     — price breaks level, returns, flow fails
"""

from .config import AuctionFailureConfig
from .models import AuctionEvent
from .data_adapter import RollingWindow


class AuctionDetectors:
    """
    All four primitive detectors.
    Each returns a list of AuctionEvent (empty if no detection).
    """

    def __init__(self, config: AuctionFailureConfig):
        self.cfg = config

    # ================================================================
    # 1. FAILED AGGRESSIVE SELL
    # ================================================================

    def detect_failed_aggressive_sell(
        self, window: RollingWindow, now: float
    ) -> list[AuctionEvent]:
        """
        Strong sell aggression that fails to produce downside.

        Conditions:
          A. AGGRESSION:
             - delta_ratio <= -threshold (net selling)
             - |delta| percentile >= threshold (extreme vs recent)
             - volume percentile >= threshold (active period)

          B. FAILURE (one of):
             - Price moved < max_move_bps in detection window (no response)
             - Price broke below recent low but reclaimed within window

        Directional interpretation: sell_pressure (favorable = price falling)
        """
        cfg = self.cfg
        det = cfg.detection
        agg = cfg.aggression
        fail = cfg.failure

        prices, volumes, deltas, timestamps = window.get_window(
            det.detection_window_seconds, now
        )
        if len(prices) < agg.min_samples_in_window:
            return []

        total_vol = sum(volumes)
        total_delta = sum(deltas)

        # ── Condition A: AGGRESSION ──
        if total_vol <= 0:
            return []

        delta_ratio = total_delta / total_vol
        if delta_ratio > -agg.delta_ratio_threshold:
            return []  # not enough sell aggression

        abs_delta = abs(total_delta)
        delta_pct = window.percentile_delta(
            abs_delta, det.detection_window_seconds, now, agg.percentile_lookback
        )
        if delta_pct < agg.delta_percentile_threshold:
            return []

        vol_pct = window.percentile_volume(
            total_vol, det.detection_window_seconds, now, agg.percentile_lookback
        )
        if vol_pct < agg.volume_percentile_threshold:
            return []

        # ── Condition B: FAILURE ──
        price_change = prices[-1] - prices[0]
        price_move_bps = abs(price_change / prices[0]) * 10000 if prices[0] > 0 else 0

        # Check for break below recent low + reclaim
        lookback_prices, _, _, _ = window.get_window(
            fail.reclaim_window_seconds * 2, now
        )
        if lookback_prices and len(lookback_prices) >= 5:
            recent_low = min(lookback_prices[:-len(prices)]) if len(lookback_prices) > len(prices) else min(lookback_prices)
            distance_to_low_bps = (prices[0] - recent_low) / recent_low * 10000 if recent_low > 0 else 999

            broke_low = any(p < recent_low for p in prices)
            if broke_low:
                # Check if price reclaimed (came back above)
                reclaim_point = recent_low * (1 + fail.reclaim_threshold_bps / 10000)
                reclaimed = any(p > reclaim_point for p in prices[-5:]) if len(prices) >= 5 else False
                if not reclaimed:
                    return []  # broke low and stayed below — not a failure
            else:
                reclaimed = False
        else:
            distance_to_low_bps = 999
            broke_low = False
            reclaimed = False

        # No response OR broke-and-reclaimed
        no_response = price_move_bps < fail.max_move_bps
        broke_and_reclaimed = broke_low and reclaimed

        if not (no_response or broke_and_reclaimed):
            return []

        # ── BUILD EVENT ──
        price = prices[-1]
        explanation = (
            f"Failed aggressive sell: delta_ratio={delta_ratio:.2f} "
            f"(p{delta_pct*100:.0f}), vol_pct={vol_pct:.0%}. "
            f"Price moved {price_move_bps:.1f}bps. "
            f"{'Broke low and reclaimed' if broke_and_reclaimed else 'No downside response'}."
        )

        return [AuctionEvent(
            timestamp=now,
            event_class="failed_aggressive_sell",
            side="sell_pressure",
            price=price,
            delta_ratio=delta_ratio,
            delta_percentile=delta_pct,
            volume_percentile=vol_pct,
            price_move_bps=price_move_bps,
            distance_to_level_bps=distance_to_low_bps,
            reclaimed=reclaimed,
            explanation=explanation,
        )]

    # ================================================================
    # 2. FAILED AGGRESSIVE BUY
    # ================================================================

    def detect_failed_aggressive_buy(
        self, window: RollingWindow, now: float
    ) -> list[AuctionEvent]:
        """
        Strong buy aggression that fails to produce upside.

        Conditions:
          A. AGGRESSION:
             - delta_ratio >= +threshold (net buying)
             - |delta| percentile >= threshold (extreme vs recent)
             - volume percentile >= threshold (active period)

          B. FAILURE (one of):
             - Price moved < max_move_bps in detection window (no response)
             - Price broke above recent high but rejected within window

        Directional interpretation: buy_pressure (favorable = price rising)
        """
        cfg = self.cfg
        det = cfg.detection
        agg = cfg.aggression
        fail = cfg.failure

        prices, volumes, deltas, timestamps = window.get_window(
            det.detection_window_seconds, now
        )
        if len(prices) < agg.min_samples_in_window:
            return []

        total_vol = sum(volumes)
        total_delta = sum(deltas)

        # ── Condition A: AGGRESSION ──
        if total_vol <= 0:
            return []

        delta_ratio = total_delta / total_vol
        if delta_ratio < agg.delta_ratio_threshold:
            return []  # not enough buy aggression

        abs_delta = abs(total_delta)
        delta_pct = window.percentile_delta(
            abs_delta, det.detection_window_seconds, now, agg.percentile_lookback
        )
        if delta_pct < agg.delta_percentile_threshold:
            return []

        vol_pct = window.percentile_volume(
            total_vol, det.detection_window_seconds, now, agg.percentile_lookback
        )
        if vol_pct < agg.volume_percentile_threshold:
            return []

        # ── Condition B: FAILURE ──
        price_change = prices[-1] - prices[0]
        price_move_bps = abs(price_change / prices[0]) * 10000 if prices[0] > 0 else 0

        # Check for break above recent high + rejection
        lookback_prices, _, _, _ = window.get_window(
            fail.reclaim_window_seconds * 2, now
        )
        if lookback_prices and len(lookback_prices) >= 5:
            recent_high = max(lookback_prices[:-len(prices)]) if len(lookback_prices) > len(prices) else max(lookback_prices)
            distance_to_high_bps = (recent_high - prices[0]) / recent_high * 10000 if recent_high > 0 else 999

            broke_high = any(p > recent_high for p in prices)
            if broke_high:
                reject_point = recent_high * (1 - fail.reclaim_threshold_bps / 10000)
                rejected = any(p < reject_point for p in prices[-5:]) if len(prices) >= 5 else False
                if not rejected:
                    return []  # broke high and held — not a failure
            else:
                rejected = False
        else:
            distance_to_high_bps = 999
            broke_high = False
            rejected = False

        no_response = price_move_bps < fail.max_move_bps
        broke_and_rejected = broke_high and rejected

        if not (no_response or broke_and_rejected):
            return []

        price = prices[-1]
        explanation = (
            f"Failed aggressive buy: delta_ratio={delta_ratio:.2f} "
            f"(p{delta_pct*100:.0f}), vol_pct={vol_pct:.0%}. "
            f"Price moved {price_move_bps:.1f}bps. "
            f"{'Broke high and rejected' if broke_and_rejected else 'No upside response'}."
        )

        return [AuctionEvent(
            timestamp=now,
            event_class="failed_aggressive_buy",
            side="buy_pressure",
            price=price,
            delta_ratio=delta_ratio,
            delta_percentile=delta_pct,
            volume_percentile=vol_pct,
            price_move_bps=price_move_bps,
            distance_to_level_bps=distance_to_high_bps,
            reclaimed=rejected,  # "rejected" is analogous to "reclaimed" for sells
            explanation=explanation,
        )]

    # ================================================================
    # 3. BREAKOUT ACCEPTANCE
    # ================================================================

    def detect_breakout_acceptance(
        self, window: RollingWindow, now: float
    ) -> list[AuctionEvent]:
        """
        Price breaks a range boundary and HOLDS outside.
        Flow confirms the break direction.

        Conditions:
          A. RANGE EXISTS:
             - Sufficient lookback data
             - Range height >= min_range_height_bps
             - Price is currently OUTSIDE the range

          B. BREAKOUT:
             - Price exceeds range boundary by break_distance_range_fraction × range_height

          C. ACCEPTANCE (all of):
             - Price holds outside for hold_window_seconds
             - Delta in break direction (flow confirmation)
             - Volume percentile elevated

        Directional interpretation: depends on break direction.
        """
        cfg = self.cfg
        brk = cfg.breakout
        agg = cfg.aggression

        # Get range data (excluding recent break zone)
        range_prices, _, _, _ = window.get_window(
            brk.range_lookback_seconds, now
        )
        if len(range_prices) < 20:
            return []

        # Exclude recent ticks from range calculation
        exclude_count = max(5, int(len(range_prices) * 0.1))
        range_core = range_prices[:-exclude_count]
        if len(range_core) < 10:
            return []

        range_high = max(range_core)
        range_low = min(range_core)
        range_height = range_high - range_low

        if range_low <= 0:
            return []
        range_height_bps = (range_height / range_low) * 10000
        if range_height_bps < brk.min_range_height_bps:
            return []

        # Current price
        current_price = window.last_price
        if current_price <= 0:
            return []

        # Check if price is outside the range
        break_threshold = range_height * brk.break_distance_range_fraction

        events = []

        # Upside break
        if current_price > range_high + break_threshold:
            break_dist_bps = ((current_price - range_high) / range_high) * 10000

            # Check hold: has price stayed outside for hold_window?
            hold_prices, hold_vols, hold_deltas, _ = window.get_window(
                brk.hold_window_seconds, now
            )
            if len(hold_prices) < 3:
                return []

            held = all(p > range_high - break_threshold * 0.3 for p in hold_prices)
            if not held:
                return []

            # Flow confirmation: delta must be positive (buying supports upside break)
            hold_delta = sum(hold_deltas)
            hold_vol = sum(hold_vols)
            flow_ratio = hold_delta / hold_vol if hold_vol > 0 else 0

            if flow_ratio < brk.flow_confirmation_ratio:
                return []  # flow doesn't confirm

            vol_pct = window.percentile_volume(
                hold_vol, brk.hold_window_seconds, now, agg.percentile_lookback
            )

            explanation = (
                f"Breakout acceptance (upside): price {current_price:.0f} broke above "
                f"range [{range_low:.0f}-{range_high:.0f}] by {break_dist_bps:.1f}bps. "
                f"Held outside for {brk.hold_window_seconds:.0f}s. "
                f"Flow ratio={flow_ratio:.2f} (buying confirms)."
            )

            events.append(AuctionEvent(
                timestamp=now,
                event_class="breakout_acceptance",
                side="upside_break",
                price=current_price,
                delta_ratio=flow_ratio,
                delta_percentile=window.percentile_delta(
                    abs(hold_delta), brk.hold_window_seconds, now, agg.percentile_lookback
                ),
                volume_percentile=vol_pct,
                price_move_bps=break_dist_bps,
                distance_to_level_bps=break_dist_bps,
                range_high=range_high,
                range_low=range_low,
                range_height_bps=range_height_bps,
                break_distance_bps=break_dist_bps,
                held_outside=True,
                reclaimed=False,
                explanation=explanation,
            ))

        # Downside break
        elif current_price < range_low - break_threshold:
            break_dist_bps = ((range_low - current_price) / range_low) * 10000

            hold_prices, hold_vols, hold_deltas, _ = window.get_window(
                brk.hold_window_seconds, now
            )
            if len(hold_prices) < 3:
                return []

            held = all(p < range_low + break_threshold * 0.3 for p in hold_prices)
            if not held:
                return []

            # Flow confirmation: delta must be negative (selling supports downside break)
            hold_delta = sum(hold_deltas)
            hold_vol = sum(hold_vols)
            flow_ratio = hold_delta / hold_vol if hold_vol > 0 else 0

            if flow_ratio > -brk.flow_confirmation_ratio:
                return []  # flow doesn't confirm

            vol_pct = window.percentile_volume(
                hold_vol, brk.hold_window_seconds, now, agg.percentile_lookback
            )

            explanation = (
                f"Breakout acceptance (downside): price {current_price:.0f} broke below "
                f"range [{range_low:.0f}-{range_high:.0f}] by {break_dist_bps:.1f}bps. "
                f"Held outside for {brk.hold_window_seconds:.0f}s. "
                f"Flow ratio={flow_ratio:.2f} (selling confirms)."
            )

            events.append(AuctionEvent(
                timestamp=now,
                event_class="breakout_acceptance",
                side="downside_break",
                price=current_price,
                delta_ratio=flow_ratio,
                delta_percentile=window.percentile_delta(
                    abs(hold_delta), brk.hold_window_seconds, now, agg.percentile_lookback
                ),
                volume_percentile=vol_pct,
                price_move_bps=break_dist_bps,
                distance_to_level_bps=break_dist_bps,
                range_high=range_high,
                range_low=range_low,
                range_height_bps=range_height_bps,
                break_distance_bps=break_dist_bps,
                held_outside=True,
                reclaimed=False,
                explanation=explanation,
            ))

        return events

    # ================================================================
    # 4. BREAKOUT REJECTION
    # ================================================================

    def detect_breakout_rejection(
        self, window: RollingWindow, now: float
    ) -> list[AuctionEvent]:
        """
        Price breaks a range boundary but RETURNS inside.
        Flow fails to support the break.

        Conditions:
          A. RANGE EXISTS (same as acceptance)

          B. BREAKOUT:
             - Price WAS outside the range (in recent window)

          C. REJECTION (all of):
             - Price returned inside the range
             - Return happened within rejection_window_seconds
             - Flow does NOT confirm the break (delta opposes or flat)

        Directional interpretation: opposite of break direction
        (upside break rejected → sell_pressure, downside break rejected → buy_pressure)
        """
        cfg = self.cfg
        brk = cfg.breakout
        agg = cfg.aggression

        range_prices, _, _, _ = window.get_window(
            brk.range_lookback_seconds, now
        )
        if len(range_prices) < 20:
            return []

        exclude_count = max(5, int(len(range_prices) * 0.1))
        range_core = range_prices[:-exclude_count]
        if len(range_core) < 10:
            return []

        range_high = max(range_core)
        range_low = min(range_core)
        range_height = range_high - range_low

        if range_low <= 0:
            return []
        range_height_bps = (range_height / range_low) * 10000
        if range_height_bps < brk.min_range_height_bps:
            return []

        break_threshold = range_height * brk.break_distance_range_fraction

        # Check recent window for a breakout that failed
        recent_prices, recent_vols, recent_deltas, recent_ts = window.get_window(
            brk.rejection_window_seconds, now
        )
        if len(recent_prices) < 5:
            return []

        current_price = recent_prices[-1]
        events = []

        # Was there an upside breakout that failed?
        max_recent = max(recent_prices)
        if max_recent > range_high + break_threshold:
            # Price broke above — is it back inside?
            inside_range = range_low < current_price < range_high
            if not inside_range:
                return []  # still outside, not a rejection

            # Check flow during the break attempt
            # Find the segment where price was outside
            outside_start = None
            for i, p in enumerate(recent_prices):
                if p > range_high + break_threshold:
                    outside_start = i
                    break

            if outside_start is None:
                return []

            outside_deltas = recent_deltas[outside_start:]
            outside_vols = recent_vols[outside_start:]
            break_delta = sum(outside_deltas)
            break_vol = sum(outside_vols)
            flow_ratio = break_delta / break_vol if break_vol > 0 else 0

            # Flow should NOT confirm (should be flat or opposing)
            if flow_ratio > brk.flow_confirmation_ratio:
                return []  # flow was buying during break — not a rejection

            break_dist_bps = ((max_recent - range_high) / range_high) * 10000
            vol_pct = window.percentile_volume(
                break_vol, brk.rejection_window_seconds, now, agg.percentile_lookback
            )

            explanation = (
                f"Breakout rejection (upside): price hit {max_recent:.0f} "
                f"(+{break_dist_bps:.1f}bps above range [{range_low:.0f}-{range_high:.0f}]) "
                f"but returned to {current_price:.0f}. "
                f"Flow ratio={flow_ratio:.2f} (no buying support)."
            )

            events.append(AuctionEvent(
                timestamp=now,
                event_class="breakout_rejection",
                side="sell_pressure",  # rejected upside = sell pressure
                price=current_price,
                delta_ratio=flow_ratio,
                delta_percentile=window.percentile_delta(
                    abs(break_delta), brk.rejection_window_seconds, now, agg.percentile_lookback
                ),
                volume_percentile=vol_pct,
                price_move_bps=break_dist_bps,
                distance_to_level_bps=((current_price - range_high) / range_high) * 10000 if range_high > 0 else 0,
                range_high=range_high,
                range_low=range_low,
                range_height_bps=range_height_bps,
                break_distance_bps=break_dist_bps,
                held_outside=False,
                reclaimed=True,
                explanation=explanation,
            ))

        # Was there a downside breakout that failed?
        min_recent = min(recent_prices)
        if min_recent < range_low - break_threshold:
            inside_range = range_low < current_price < range_high
            if not inside_range:
                return []

            outside_start = None
            for i, p in enumerate(recent_prices):
                if p < range_low - break_threshold:
                    outside_start = i
                    break

            if outside_start is None:
                return []

            outside_deltas = recent_deltas[outside_start:]
            outside_vols = recent_vols[outside_start:]
            break_delta = sum(outside_deltas)
            break_vol = sum(outside_vols)
            flow_ratio = break_delta / break_vol if break_vol > 0 else 0

            # Flow should NOT confirm (should be flat or opposing for downside)
            if flow_ratio < -brk.flow_confirmation_ratio:
                return []  # flow was selling during break — not a rejection

            break_dist_bps = ((range_low - min_recent) / range_low) * 10000
            vol_pct = window.percentile_volume(
                break_vol, brk.rejection_window_seconds, now, agg.percentile_lookback
            )

            explanation = (
                f"Breakout rejection (downside): price hit {min_recent:.0f} "
                f"(-{break_dist_bps:.1f}bps below range [{range_low:.0f}-{range_high:.0f}]) "
                f"but returned to {current_price:.0f}. "
                f"Flow ratio={flow_ratio:.2f} (no selling support)."
            )

            events.append(AuctionEvent(
                timestamp=now,
                event_class="breakout_rejection",
                side="buy_pressure",  # rejected downside = buy pressure
                price=current_price,
                delta_ratio=flow_ratio,
                delta_percentile=window.percentile_delta(
                    abs(break_delta), brk.rejection_window_seconds, now, agg.percentile_lookback
                ),
                volume_percentile=vol_pct,
                price_move_bps=break_dist_bps,
                distance_to_level_bps=((range_low - current_price) / range_low) * 10000 if range_low > 0 else 0,
                range_high=range_high,
                range_low=range_low,
                range_height_bps=range_height_bps,
                break_distance_bps=break_dist_bps,
                held_outside=False,
                reclaimed=True,
                explanation=explanation,
            ))

        return events

    def detect_all(self, window: RollingWindow, now: float) -> list[AuctionEvent]:
        """Run all four detectors. Returns combined list."""
        events = []
        events.extend(self.detect_failed_aggressive_sell(window, now))
        events.extend(self.detect_failed_aggressive_buy(window, now))
        events.extend(self.detect_breakout_acceptance(window, now))
        events.extend(self.detect_breakout_rejection(window, now))
        return events
