"""
Scoring module for alert ranking and portfolio-level adjustments.

This module provides scoring functionality that transforms raw detector scores
into portfolio-adjusted scores that reflect additional context like thesis alignment,
liquidity, earnings proximity, technical confirmation, and volatility regime.

Main Components:
    - AlertScorer: Applies portfolio-level bonuses/penalties to detector scores
    - AlertThrottler: Manages alert throttling with cooldown and daily rate limiting
    - score_alert(): Convenience function for scoring alerts

Usage:
    from functions.scoring.scorer import AlertScorer
    from functions.scoring.throttler import AlertThrottler
    from functions.config.loader import get_config
    from functions.db.connection import get_db

    config = get_config()
    scorer = AlertScorer(config)
    throttler = AlertThrottler(get_db(), config)

    adjusted_score = scorer.score_alert(alert, "AAPL", features)

    if throttler.should_alert("AAPL", "detector_name", adjusted_score):
        # Send alert and record it
        alert_id = send_alert(...)
        throttler.record_alert("AAPL", "detector_name", adjusted_score, alert_id)
"""

from functions.scoring.scorer import AlertScorer
from functions.scoring.throttler import AlertThrottler

__all__ = ["AlertScorer", "AlertThrottler"]
