"""
MANTIS Event Engine — Transparent Scoring
Every score is explainable. Components are stored in the event.
No hidden models, no magic.
"""

from app.event_engine.config import EventEngineConfig
from app.event_engine.models import ScoreBreakdown


class ScoringEngine:
    """Computes strength, confidence, noise, and composite scores."""

    def __init__(self, config: EventEngineConfig):
        self.cfg = config.scoring
        self.global_cfg = config

    def score_absorption(self, volume_pct: float, delta_pct: float,
                         price_non_continuation: float, repeated_tests: int,
                         book_support: float, spread_ok: bool,
                         regime: str) -> ScoreBreakdown:
        """Score an absorption event."""
        strength = {
            "volume": min(volume_pct, 1.0),
            "delta": min(delta_pct, 1.0),
            "price_action": min(price_non_continuation, 1.0),
            "repetition": min(repeated_tests / 3.0, 1.0),
        }
        confidence = {
            "regime": self._regime_score(regime),
            "liquidity": min(book_support / 5.0, 1.0),
            "spread": 1.0 if spread_ok else 0.3,
            "sample_size": min(volume_pct * 2, 1.0),
        }
        noise = {
            "low_volume": max(0, 1.0 - volume_pct * 2),
            "wide_spread": 0.0 if spread_ok else 0.5,
            "low_volatility": 0.3 if regime == "low_volatility" else 0.0,
            "cluster_duplicate": 0.0,
        }
        return self._compute(strength, confidence, noise, regime)

    def score_exhaustion(self, volume_pct: float, impact_decline: float,
                         bubble_count: int, cvd_div: float,
                         near_extreme: bool, regime: str) -> ScoreBreakdown:
        strength = {
            "volume": min(volume_pct, 1.0),
            "delta": min(impact_decline, 1.0),
            "price_action": 1.0 if near_extreme else 0.3,
            "repetition": min(bubble_count / 5.0, 1.0),
        }
        confidence = {
            "regime": self._regime_score(regime),
            "liquidity": min(abs(cvd_div) * 2, 1.0),
            "spread": 0.7,
            "sample_size": min(volume_pct * 1.5, 1.0),
        }
        noise = {
            "low_volume": max(0, 1.0 - volume_pct * 2),
            "wide_spread": 0.0,
            "low_volatility": 0.4 if regime == "low_volatility" else 0.0,
            "cluster_duplicate": 0.0,
        }
        return self._compute(strength, confidence, noise, regime)

    def score_sweep(self, distance_pct: float, volume_pct: float,
                    reclaimed: bool, reversal: bool,
                    prior_touches: int, regime: str) -> ScoreBreakdown:
        strength = {
            "volume": min(volume_pct, 1.0),
            "delta": 1.0 if reversal else 0.3,
            "price_action": min(distance_pct, 1.0),
            "repetition": min(prior_touches / 4.0, 1.0),
        }
        confidence = {
            "regime": self._regime_score(regime),
            "liquidity": 0.8 if reclaimed else 0.4,
            "spread": 0.7,
            "sample_size": min(volume_pct * 1.5, 1.0),
        }
        noise = {
            "low_volume": max(0, 1.0 - volume_pct * 2),
            "wide_spread": 0.0,
            "low_volatility": 0.3 if regime == "low_volatility" else 0.0,
            "cluster_duplicate": 0.0,
        }
        return self._compute(strength, confidence, noise, regime)

    def score_divergence(self, price_move_pct: float, cvd_opposition: float,
                         regime: str) -> ScoreBreakdown:
        strength = {
            "volume": 0.5,
            "delta": min(cvd_opposition, 1.0),
            "price_action": min(price_move_pct, 1.0),
            "repetition": 0.3,
        }
        confidence = {
            "regime": self._regime_score(regime),
            "liquidity": 0.5,
            "spread": 0.7,
            "sample_size": 0.5,
        }
        noise = {
            "low_volume": 0.2,
            "wide_spread": 0.0,
            "low_volatility": 0.5 if regime == "low_volatility" else 0.0,
            "cluster_duplicate": 0.0,
        }
        return self._compute(strength, confidence, noise, regime)

    def score_imbalance(self, ratio: float, volume_pct: float,
                        price_response: float, regime: str) -> ScoreBreakdown:
        strength = {
            "volume": min(volume_pct, 1.0),
            "delta": min((ratio - 1) / 5.0, 1.0),
            "price_action": min(abs(price_response) / 20.0, 1.0),
            "repetition": 0.3,
        }
        confidence = {
            "regime": self._regime_score(regime),
            "liquidity": 0.6,
            "spread": 0.7,
            "sample_size": min(volume_pct * 1.5, 1.0),
        }
        noise = {
            "low_volume": max(0, 1.0 - volume_pct * 2),
            "wide_spread": 0.0,
            "low_volatility": 0.2 if regime == "low_volatility" else 0.0,
            "cluster_duplicate": 0.0,
        }
        return self._compute(strength, confidence, noise, regime)

    def score_large_cluster(self, cluster_count: int, volume_pct: float,
                            percentile: float, regime: str) -> ScoreBreakdown:
        strength = {
            "volume": min(volume_pct, 1.0),
            "delta": min(percentile, 1.0),
            "price_action": min(cluster_count / 8.0, 1.0),
            "repetition": min(cluster_count / 5.0, 1.0),
        }
        confidence = {
            "regime": self._regime_score(regime),
            "liquidity": 0.6,
            "spread": 0.7,
            "sample_size": min(percentile, 1.0),
        }
        noise = {
            "low_volume": max(0, 1.0 - volume_pct * 2),
            "wide_spread": 0.0,
            "low_volatility": 0.2,
            "cluster_duplicate": 0.0,
        }
        return self._compute(strength, confidence, noise, regime)

    def score_range_break(self, break_strength: float, volume_pct: float,
                          range_quality: float, regime: str) -> ScoreBreakdown:
        strength = {
            "volume": min(volume_pct, 1.0),
            "delta": min(break_strength, 1.0),
            "price_action": min(range_quality, 1.0),
            "repetition": 0.5,
        }
        confidence = {
            "regime": self._regime_score(regime),
            "liquidity": 0.7,
            "spread": 0.7,
            "sample_size": min(volume_pct * 1.5, 1.0),
        }
        noise = {
            "low_volume": max(0, 1.0 - volume_pct * 2),
            "wide_spread": 0.0,
            "low_volatility": 0.3 if regime == "low_volatility" else 0.0,
            "cluster_duplicate": 0.0,
        }
        return self._compute(strength, confidence, noise, regime)

    def score_vwap_reaction(self, volume_pct: float, delta_strength: float,
                            follow_through: float, regime: str) -> ScoreBreakdown:
        strength = {
            "volume": min(volume_pct, 1.0),
            "delta": min(delta_strength, 1.0),
            "price_action": min(abs(follow_through) / 20.0, 1.0),
            "repetition": 0.4,
        }
        confidence = {
            "regime": self._regime_score(regime),
            "liquidity": 0.6,
            "spread": 0.7,
            "sample_size": min(volume_pct * 1.5, 1.0),
        }
        noise = {
            "low_volume": max(0, 1.0 - volume_pct * 2),
            "wide_spread": 0.0,
            "low_volatility": 0.3 if regime == "low_volatility" else 0.0,
            "cluster_duplicate": 0.0,
        }
        return self._compute(strength, confidence, noise, regime)

    # --- Internal ---

    def _compute(self, strength: dict, confidence: dict,
                 noise: dict, regime: str) -> ScoreBreakdown:
        sw = self.cfg.strength_weights
        cw = self.cfg.confidence_weights
        nw = self.cfg.noise_penalty_weights

        s_score = sum(strength.get(k, 0) * v for k, v in sw.items())
        c_score = sum(confidence.get(k, 0) * v for k, v in cw.items())
        n_score = sum(noise.get(k, 0) * v for k, v in nw.items())

        # Composite: strength * confidence * (1 - noise)
        composite = s_score * c_score * (1.0 - n_score * 0.5)

        return ScoreBreakdown(
            strength_components=strength,
            confidence_components=confidence,
            noise_components=noise,
            regime_score=self._regime_score(regime),
            strength_score=min(max(s_score, 0), 1),
            confidence_score=min(max(c_score, 0), 1),
            noise_score=min(max(n_score, 0), 1),
            composite_score=min(max(composite, 0), 1),
        )

    def _regime_score(self, regime: str) -> float:
        return {"high_volatility": 0.9, "normal": 0.7, "low_volatility": 0.4, "unknown": 0.3}.get(regime, 0.3)
