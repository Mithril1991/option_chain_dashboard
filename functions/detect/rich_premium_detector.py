"""
Rich Premium Detector - Identifies premium buying/selling opportunities.

This detector identifies when implied volatility is at historically high levels,
signaling a potential premium buying opportunity (when selling high IV). When IV is high,
option buyers can purchase premium at historically elevated levels, while option sellers
can collect premium with enhanced compensation.

Detection Logic:
    - Monitors IV percentile (current IV vs historical levels)
    - Detects when IV percentile rises above configured threshold
    - Applies context modifiers (IV trend, price momentum, term structure, volume)
    - Returns high-confidence alerts for rich IV premium opportunities

Configuration:
    Key: "detectors.rich_premium"
    Fields:
        enabled (bool): Enable this detector
        iv_percentile_threshold (float): IV percentile threshold (default: 75.0)
            Alerts trigger when iv_percentile >= threshold

Risk Gate:
    Score must be >= 60 to pass risk gates and be actionable.

Strategies:
    - "CSP": Cash-secured puts (sell puts, collect premium)
    - "Covered Call": Sell calls against equity holdings
    - "Iron Condor": Sell both call and put spreads, neutral
    - "Bull Put Spread": Sell put spread, collect premium

Confidence Levels:
    - "high": IV percentile >= 85 (extreme high, very premium-rich)
    - "medium": 75 <= IV percentile < 85 (elevated, moderately premium-rich)
    - "low": IV percentile < 75 (marginally elevated, marginal opportunity)

Usage:
    from functions.detect.base import DetectorRegistry
    from functions.compute.feature_engine import FeatureSet

    registry = DetectorRegistry.get_registry()
    detector = registry.get_detector("RichPremiumDetector")
    alert = detector.detect_safe(features)
    if alert:
        print(f"Rich premium opportunity: {alert.explanation['summary']}")
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


class RichPremiumDetector(DetectorPlugin):
    """
    Detects high implied volatility opportunities for premium selling strategies.

    When IV percentile is above the configured threshold, it indicates that options
    are trading at high historical IV levels. This creates premium-selling opportunities
    where traders can collect option premiums with historically enhanced compensation.

    Attributes:
        name: "RichPremiumDetector"
        description: Detects historically high IV levels for premium selling opportunities
        config_key: "detectors.rich_premium"

    Example:
        >>> detector = RichPremiumDetector()
        >>> alert = detector.detect_safe(features)
        >>> if alert:
        ...     print(f"Score: {alert.score}")
        ...     print(f"IV Percentile: {alert.metrics['iv_percentile']}")
        ...     print(f"Strategies: {alert.strategies}")
    """

    @property
    def name(self) -> str:
        """Get detector name."""
        return "RichPremiumDetector"

    @property
    def description(self) -> str:
        """Get detector description."""
        return "Detects historically high IV levels for premium selling opportunities"

    def get_config_key(self) -> str:
        """Get configuration key for this detector."""
        return "detectors.rich_premium"

    def detect(self, features: FeatureSet) -> Optional[AlertCandidate]:
        """
        Detect rich premium opportunities in the feature set.

        Analysis process:
        1. Extract IV percentile from features
        2. Validate data availability
        3. Get configuration threshold
        4. Calculate base score (IV percentile)
        5. Apply contextual modifiers:
           - If IV rank > 80: bonus +15 (extreme high)
           - If price above SMA200: bonus +10 (premium sustainable, trending)
           - If term structure in contango: bonus +5 (normal condition)
           - If volume low (< 20th percentile): penalty -10 (liquidity concern)
        6. Clamp score to [0, 100]
        7. Return AlertCandidate if score >= 60

        Args:
            features (FeatureSet): Market data feature set containing IV metrics

        Returns:
            AlertCandidate: If rich IV detected with score >= 60
            None: If conditions not met or insufficient data

        Raises:
            None - all exceptions are caught and logged by detect_safe()
        """
        logger.debug(f"Starting RichPremiumDetector analysis for {features.ticker}")

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
        # Default to 75.0 if not configured
        threshold = 75.0

        # Try to get from AppConfig if available (via app context)
        try:
            # Note: In a production system, AppConfig would come from config.yaml
            # For now, we use the default threshold
            pass
        except Exception as e:
            logger.debug(f"Could not load detector config: {e}, using default threshold")

        logger.debug(f"[{features.ticker}] IV threshold: {threshold:.1f}")

        # =====================================================================
        # STEP 3: Check if IV percentile is above threshold
        # =====================================================================
        if iv_percentile < threshold:
            logger.debug(
                f"[{features.ticker}] IV percentile {iv_percentile:.1f} < threshold {threshold:.1f}, "
                f"not rich enough"
            )
            return None

        logger.debug(
            f"[{features.ticker}] IV percentile {iv_percentile:.1f} >= threshold {threshold:.1f}, "
            f"rich premium detected"
        )

        # =====================================================================
        # STEP 4: Calculate base score
        # =====================================================================
        # Base score is higher when IV percentile is higher
        # IV percentile 0 = 0 points, IV percentile 100 = 100 points
        base_score = iv_percentile

        logger.debug(f"[{features.ticker}] Base score: {base_score:.1f}")

        # =====================================================================
        # STEP 5: Apply context modifiers
        # =====================================================================
        score = base_score
        modifiers_log = []

        # Modifier 1: IV rank > 80 (extreme high - bonus)
        iv_rank = features.iv_metrics.get("iv_rank")
        if iv_rank is not None and not math.isnan(iv_rank):
            if iv_rank > 80:
                score += 15
                modifiers_log.append(f"IV rank > 80 (+15 points, rank={iv_rank:.1f})")
                logger.debug(f"[{features.ticker}] IV rank > 80, added 15 points (rank={iv_rank:.1f})")

        # Modifier 2: Price above SMA200 (trending, premium sustainable - bonus)
        sma_200 = features.technicals.get("sma_200")
        if sma_200 is not None and not math.isnan(sma_200):
            if features.price > sma_200:
                score += 10
                modifiers_log.append(f"Price above SMA200 (+10 points, trending)")
                logger.debug(
                    f"[{features.ticker}] Price {features.price:.2f} above SMA200 "
                    f"{sma_200:.2f}, added 10 points"
                )

        # Modifier 3: Term structure in contango (iv_back > iv_front - bonus)
        iv_front = features.options_front.get("atm_iv")
        iv_back = features.options_back.get("atm_iv")
        if iv_front is not None and iv_back is not None:
            if not math.isnan(iv_front) and not math.isnan(iv_back):
                if iv_back > iv_front:
                    score += 5
                    modifiers_log.append(f"Term structure in contango (+5 points)")
                    logger.debug(
                        f"[{features.ticker}] Term structure in contango "
                        f"(front={iv_front:.4f}, back={iv_back:.4f}), added 5 points"
                    )

        # Modifier 4: Volume low (< 20th percentile - penalty)
        volume = features.options_front.get("volume")
        volume_sma_20 = features.technicals.get("volume_sma_20")
        if volume is not None and volume_sma_20 is not None:
            if volume > 0 and volume_sma_20 > 0:
                volume_ratio = volume / volume_sma_20
                # If volume is low (< 20th percentile, roughly 0.2x average)
                if volume_ratio < 0.2:
                    score -= 10
                    modifiers_log.append(f"Low volume (-10 points, ratio={volume_ratio:.2f})")
                    logger.debug(
                        f"[{features.ticker}] Volume low at {volume_ratio:.2f}x average, "
                        f"reduced score by 10"
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

        logger.info(f"[{features.ticker}] RichPremiumDetector alert triggered: score={score:.1f}")

        # =====================================================================
        # STEP 8: Determine confidence level
        # =====================================================================
        if iv_percentile >= 85:
            confidence = "high"
        elif iv_percentile >= 75:
            confidence = "medium"
        else:
            confidence = "low"

        # =====================================================================
        # STEP 9: Build metrics dictionary
        # =====================================================================
        metrics = {
            "iv_percentile": iv_percentile,
            "iv_rank": iv_rank,
            "iv_front": iv_front,
            "iv_back": iv_back,
            "term_structure_ratio": self._calculate_term_structure_ratio(iv_front, iv_back),
            "rsi_14": features.technicals.get("rsi"),
            "price_vs_sma200": self._calculate_price_vs_sma200(features.price, sma_200),
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
            "CSP",
            "Covered Call",
            "Iron Condor",
            "Bull Put Spread",
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
            f"[{features.ticker}] RichPremiumDetector returning alert: "
            f"score={alert.score:.1f}, confidence={alert.confidence}"
        )

        return alert

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _calculate_term_structure_ratio(self, iv_front: Optional[float], iv_back: Optional[float]) -> Optional[float]:
        """
        Calculate term structure ratio (back IV / front IV).

        Returns the ratio of back-month IV to front-month IV.
        If either value is unavailable or zero, returns None.

        Args:
            iv_front (Optional[float]): Front-month IV
            iv_back (Optional[float]): Back-month IV

        Returns:
            float: Back IV / Front IV ratio, or None if data unavailable
        """
        if iv_front is None or iv_back is None:
            return None

        if isinstance(iv_front, float) and math.isnan(iv_front):
            return None

        if isinstance(iv_back, float) and math.isnan(iv_back):
            return None

        if iv_front == 0:
            return None

        return iv_back / iv_front

    def _calculate_price_vs_sma200(self, price: float, sma_200: Optional[float]) -> Optional[float]:
        """
        Calculate price position relative to SMA200.

        Returns the percentage difference between price and SMA200.
        Positive values indicate price is above SMA200 (bullish).

        Args:
            price (float): Current price
            sma_200 (Optional[float]): 200-day simple moving average

        Returns:
            float: (Price - SMA200) / SMA200 * 100, or None if SMA200 unavailable
        """
        if sma_200 is None:
            return None

        if isinstance(sma_200, float) and math.isnan(sma_200):
            return None

        if sma_200 == 0:
            return None

        return (price - sma_200) / sma_200 * 100

    def _build_summary(self, ticker: str, iv_percentile: float) -> str:
        """
        Build concise summary of the rich premium detection.

        Args:
            ticker (str): Stock ticker symbol
            iv_percentile (float): Current IV percentile (0-100)

        Returns:
            str: 1-2 sentence summary of the detection
        """
        return (
            f"{ticker} trading at historically high implied volatility "
            f"({iv_percentile:.0f}th percentile). Premium selling opportunity."
        )

    def _build_reason(self, iv_percentile: float, confidence: str) -> str:
        """
        Build explanation of why rich premium matters for trading.

        Args:
            iv_percentile (float): Current IV percentile
            confidence (str): Confidence level (high/medium/low)

        Returns:
            str: Explanation of trading significance
        """
        base_reason = (
            "High IV indicates elevated option premiums. Selling strategies "
            "collect premium with historically enhanced compensation, creating "
            "favorable risk/reward for systematic premium selling."
        )

        if confidence == "high":
            return (
                f"{base_reason} Extreme high IV ({iv_percentile:.0f}th percentile) "
                f"provides rare premium-selling window with maximum compensation."
            )
        elif confidence == "medium":
            return (
                f"{base_reason} Moderately high IV ({iv_percentile:.0f}th percentile) "
                f"provides reasonable premium-selling opportunity."
            )
        else:
            return (
                f"{base_reason} Marginally high IV ({iv_percentile:.0f}th percentile) "
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
            f"IV percentile ({iv_percentile:.1f}) crossed above threshold ({threshold:.1f}), "
            f"indicating historically high option premiums"
        )


# ============================================================================
# PLUGIN REGISTRATION
# ============================================================================

# Register the detector at import time
try:
    DetectorRegistry.register(RichPremiumDetector)
    logger.debug("RichPremiumDetector registered successfully")
except Exception as e:
    logger.error(f"Failed to register RichPremiumDetector: {e}", exc_info=True)
