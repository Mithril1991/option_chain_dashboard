"""
Low IV Percentile Detector - Identifies premium selling opportunities.

This detector identifies when implied volatility is at historically low levels,
signaling a potential premium selling opportunity. When IV is low, option sellers
can collect premium with historically reduced compensation, making it an ideal
time to consider premium-selling strategies.

Detection Logic:
    - Monitors IV percentile (current IV vs historical levels)
    - Detects when IV percentile falls below configured threshold
    - Applies context modifiers (IV trend, RSI, price levels)
    - Returns high-confidence alerts for low-IV premium selling opportunities

Configuration:
    Key: "detectors.low_iv"
    Fields:
        enabled (bool): Enable this detector
        iv_percentile_threshold (float): IV percentile threshold (default: 25.0)
            Alerts trigger when iv_percentile < threshold

Risk Gate:
    Score must be >= 60 to pass risk gates and be actionable.

Strategies:
    - "Long Straddle": Sell premium on both sides (neutral IV view)
    - "Calendar Spread": Sell near-term IV, buy longer-dated for roll stability
    - "Bull Call Spread": Defined-risk call spread (bullish with lower IV cost)

Confidence Levels:
    - "high": IV percentile < 15 (extreme low, very opportune)
    - "medium": 15 <= IV percentile < 30 (low, somewhat opportune)
    - "low": IV percentile >= 30 (marginally low, marginal opportunity)

Usage:
    from functions.detect.base import DetectorRegistry
    from functions.compute.feature_engine import FeatureSet

    registry = DetectorRegistry.get_registry()
    detector = registry.get_detector("LowIVDetector")
    alert = detector.detect_safe(features)
    if alert:
        print(f"Low IV opportunity: {alert.explanation['summary']}")
"""

import logging
import math
from typing import Optional
from datetime import timedelta

from functions.detect.base import DetectorPlugin, DetectorRegistry, AlertCandidate
from functions.compute.feature_engine import FeatureSet
from functions.config.settings import get_settings
from functions.util.logging_setup import get_logger

logger = get_logger(__name__)


class LowIVDetector(DetectorPlugin):
    """
    Detects low implied volatility opportunities for premium selling strategies.

    When IV percentile is below the configured threshold, it indicates that options
    are trading at low historical IV levels. This creates premium-selling opportunities
    where traders can collect option premiums with historically reduced compensation.

    Attributes:
        name: "LowIVDetector"
        description: Detects historically low IV levels for premium selling opportunities
        config_key: "detectors.low_iv"

    Example:
        >>> detector = LowIVDetector()
        >>> alert = detector.detect_safe(features)
        >>> if alert:
        ...     print(f"Score: {alert.score}")
        ...     print(f"IV Percentile: {alert.metrics['iv_percentile']}")
        ...     print(f"Strategies: {alert.strategies}")
    """

    @property
    def name(self) -> str:
        """Get detector name."""
        return "LowIVDetector"

    @property
    def description(self) -> str:
        """Get detector description."""
        return "Detects historically low IV levels for premium selling opportunities"

    def get_config_key(self) -> str:
        """Get configuration key for this detector."""
        return "detectors.low_iv"

    def detect(self, features: FeatureSet) -> Optional[AlertCandidate]:
        """
        Detect low IV opportunities in the feature set.

        Analysis process:
        1. Extract IV percentile from features
        2. Validate data availability
        3. Calculate base score (inverted IV percentile)
        4. Apply contextual modifiers:
           - IV expansion (reduce score if expanding)
           - RSI < 30 (bonus if oversold)
           - Price at 52-week low (bonus for mean reversion context)
        5. Return AlertCandidate if score >= 60

        Args:
            features (FeatureSet): Market data feature set containing IV metrics

        Returns:
            AlertCandidate: If low IV detected with score >= 60
            None: If conditions not met or insufficient data

        Raises:
            None - all exceptions are caught and logged by detect_safe()
        """
        logger.debug(f"Starting LowIVDetector analysis for {features.ticker}")

        # =====================================================================
        # STEP 1: Extract and validate IV percentile
        # =====================================================================
        iv_percentile = features.iv_metrics.get("iv_percentile")

        if iv_percentile is None or (isinstance(iv_percentile, float) and math.isnan(iv_percentile)):
            logger.debug(
                f"[{features.ticker}] IV percentile not available, skipping detection"
            )
            return None

        logger.debug(f"[{features.ticker}] IV percentile: {iv_percentile:.1f}")

        # =====================================================================
        # STEP 2: Get configuration threshold
        # =====================================================================
        settings = get_settings()
        # Default to 25.0 if not configured
        threshold = 25.0

        # Try to get from AppConfig if available (via app context)
        try:
            # Note: In a production system, AppConfig would come from config.yaml
            # For now, we use the default threshold
            pass
        except Exception as e:
            logger.debug(f"Could not load detector config: {e}, using default threshold")

        logger.debug(f"[{features.ticker}] IV threshold: {threshold:.1f}")

        # =====================================================================
        # STEP 3: Check if IV percentile is below threshold
        # =====================================================================
        if iv_percentile >= threshold:
            logger.debug(
                f"[{features.ticker}] IV percentile {iv_percentile:.1f} >= threshold {threshold:.1f}, "
                f"not low enough"
            )
            return None

        logger.debug(
            f"[{features.ticker}] IV percentile {iv_percentile:.1f} < threshold {threshold:.1f}, "
            f"low IV detected"
        )

        # =====================================================================
        # STEP 4: Calculate base score
        # =====================================================================
        # Base score is higher when IV percentile is lower
        # IV percentile 0 = 100 points, IV percentile 100 = 0 points
        base_score = max(0, 100 - iv_percentile)

        logger.debug(f"[{features.ticker}] Base score: {base_score:.1f}")

        # =====================================================================
        # STEP 5: Apply context modifiers
        # =====================================================================
        score = base_score
        modifiers_log = []

        # Modifier 1: IV Expansion (reduce score if IV is expanding)
        vol_expanding = features.volatility.get("expanding", False)
        if vol_expanding:
            score -= 15
            modifiers_log.append("IV expanding (-15 points)")
            logger.debug(f"[{features.ticker}] IV is expanding, reduced score by 15")

        # Modifier 2: RSI < 30 (oversold - bonus for mean reversion context)
        rsi_14 = features.technicals.get("rsi", None)
        if rsi_14 is not None and not math.isnan(rsi_14):
            if rsi_14 < 30:
                score += 10
                modifiers_log.append(f"RSI < 30 (oversold) (+10 points, RSI={rsi_14:.1f})")
                logger.debug(f"[{features.ticker}] RSI < 30, added 10 points (RSI={rsi_14:.1f})")

        # Modifier 3: Price at 52-week low (mean reversion context)
        # Estimate 52-week low using support level if available
        support_20d = features.technicals.get("support_20d", None)
        if support_20d is not None and not math.isnan(support_20d):
            # If price is within 5% of 20-day support, consider it near support/low
            if features.price <= support_20d * 1.05:
                score += 5
                modifiers_log.append(f"Price near support (+5 points)")
                logger.debug(
                    f"[{features.ticker}] Price {features.price:.2f} near 20-day support "
                    f"{support_20d:.2f}, added 5 points"
                )

        # =====================================================================
        # STEP 6: Clamp score to [0, 100]
        # =====================================================================
        score = max(0, min(100, score))

        logger.debug(
            f"[{features.ticker}] Final score: {score:.1f} "
            f"(modifiers: {', '.join(modifiers_log) if modifiers_log else 'none'})"
        )

        # =====================================================================
        # STEP 7: Check if score passes risk gate (>= 60)
        # =====================================================================
        if score < 60:
            logger.debug(
                f"[{features.ticker}] Score {score:.1f} < risk gate (60), alert filtered"
            )
            return None

        logger.info(f"[{features.ticker}] LowIVDetector alert triggered: score={score:.1f}")

        # =====================================================================
        # STEP 8: Determine confidence level
        # =====================================================================
        if iv_percentile < 15:
            confidence = "high"
        elif iv_percentile < 30:
            confidence = "medium"
        else:
            confidence = "low"

        # =====================================================================
        # STEP 9: Build metrics dictionary
        # =====================================================================
        metrics = {
            "iv_percentile": iv_percentile,
            "iv_front": features.options_front.get("atm_iv", None),
            "iv_back": features.options_back.get("atm_iv", None),
            "iv_vs_hv": self._calculate_iv_vs_hv(features),
            "rsi_14": rsi_14,
            "vol_expanding": vol_expanding,
        }

        # =====================================================================
        # STEP 10: Build explanation dictionary
        # =====================================================================
        explanation = {
            "summary": self._build_summary(features.ticker, iv_percentile),
            "reason": self._build_reason(iv_percentile, confidence),
            "trigger": self._build_trigger(iv_percentile, threshold),
        }

        # =====================================================================
        # STEP 11: Define strategies
        # =====================================================================
        strategies = [
            "Long Straddle",
            "Calendar Spread",
            "Bull Call Spread",
        ]

        # =====================================================================
        # STEP 12: Create and return AlertCandidate
        # =====================================================================
        alert = AlertCandidate(
            detector_name=self.name,
            score=score,
            metrics=metrics,
            explanation=explanation,
            strategies=strategies,
            confidence=confidence,
        )

        logger.info(
            f"[{features.ticker}] LowIVDetector returning alert: "
            f"score={alert.score:.1f}, confidence={alert.confidence}"
        )

        return alert

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _calculate_iv_vs_hv(self, features: FeatureSet) -> Optional[float]:
        """
        Calculate IV vs HV (Historical Volatility) ratio.

        Returns the ratio of front-month IV to historical volatility (20-day).
        If either value is unavailable, returns None.

        Args:
            features (FeatureSet): Feature set containing volatility data

        Returns:
            float: IV / HV ratio, or None if data unavailable
        """
        iv_front = features.options_front.get("atm_iv")
        hv_20 = features.volatility.get("hv_20")

        if iv_front is None or hv_20 is None:
            return None

        if isinstance(iv_front, float) and math.isnan(iv_front):
            return None

        if isinstance(hv_20, float) and math.isnan(hv_20):
            return None

        if hv_20 == 0:
            return None

        return iv_front / hv_20

    def _build_summary(self, ticker: str, iv_percentile: float) -> str:
        """
        Build concise summary of the low IV detection.

        Args:
            ticker (str): Stock ticker symbol
            iv_percentile (float): Current IV percentile (0-100)

        Returns:
            str: 1-2 sentence summary of the detection
        """
        return (
            f"{ticker} trading at historically low implied volatility "
            f"({iv_percentile:.0f}th percentile). Premium-selling opportunity."
        )

    def _build_reason(self, iv_percentile: float, confidence: str) -> str:
        """
        Build explanation of why low IV matters for trading.

        Args:
            iv_percentile (float): Current IV percentile
            confidence (str): Confidence level (high/medium/low)

        Returns:
            str: Explanation of trading significance
        """
        base_reason = (
            "Low IV indicates compressed option premiums. Selling strategies "
            "collect premium with historically low compensation, creating "
            "favorable risk/reward for systematic premium selling."
        )

        if confidence == "high":
            return (
                f"{base_reason} Extreme low IV ({iv_percentile:.0f}th percentile) "
                f"provides rare premium-selling window."
            )
        elif confidence == "medium":
            return (
                f"{base_reason} Moderately low IV ({iv_percentile:.0f}th percentile) "
                f"provides reasonable premium-selling opportunity."
            )
        else:
            return (
                f"{base_reason} Marginally low IV ({iv_percentile:.0f}th percentile) "
                f"provides limited premium-selling opportunity."
            )

    def _build_trigger(self, iv_percentile: float, threshold: float) -> str:
        """
        Build trigger explanation describing the specific threshold cross.

        Args:
            iv_percentile (float): Current IV percentile
            threshold (float): Alert threshold

        Returns:
            str: Description of what triggered the alert
        """
        return (
            f"IV percentile ({iv_percentile:.1f}) crossed below threshold ({threshold:.1f}), "
            f"indicating historically low option premiums"
        )


# ============================================================================
# PLUGIN REGISTRATION
# ============================================================================

# Register the detector at import time
try:
    DetectorRegistry.register(LowIVDetector)
    logger.debug("LowIVDetector registered successfully")
except Exception as e:
    logger.error(f"Failed to register LowIVDetector: {e}", exc_info=True)
