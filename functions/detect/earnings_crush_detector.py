"""
Earnings Crush Detector - Identifies pre-earnings IV crush opportunities.

This detector identifies when an earnings date is approaching within 0-14 days and implied
volatility is elevated. This creates a "IV crush" opportunity where IV is expected to
collapse post-earnings, making spread strategies attractive.

Detection Logic:
    - Checks days_to_earnings from features.earnings_info or earnings calendar
    - Validates earnings is within 0-14 days window
    - Checks if IV percentile is elevated (above configured threshold)
    - Calculates base score based on days_to_earnings (closer = higher score)
    - Applies context modifiers (IV rank, ATM IV level, price position)
    - Returns high-confidence alerts for IV crush opportunities

Configuration:
    Key: "detectors.earnings_crush"
    Fields:
        enabled (bool): Enable this detector
        iv_percentile_threshold (float): IV percentile threshold (default: 60.0)
            Alerts trigger when iv_percentile >= threshold
        max_days_to_earnings (int): Maximum days until earnings (default: 14)
            Alerts only trigger for earnings within this window

Risk Gate:
    Score must be >= 60 to pass risk gates and be actionable.

Strategies:
    - "Iron Condor": Sell call and put spreads, neutral directional bet
    - "Bull Put Spread": Sell put spread below support
    - "Bear Call Spread": Sell call spread above resistance

Confidence Levels:
    - "high": Days 0-7 (crush happens post-earnings, high certainty)
    - "medium": Days 8-14 (crush less certain, timing risk)

Usage:
    from functions.detect.base import DetectorRegistry
    from functions.compute.feature_engine import FeatureSet

    registry = DetectorRegistry.get_registry()
    detector = registry.get_detector("EarningsCrushDetector")
    alert = detector.detect_safe(features)
    if alert:
        print(f"Earnings crush opportunity: {alert.explanation['summary']}")
"""

import logging
import math
from typing import Optional

from functions.detect.base import DetectorPlugin, DetectorRegistry, AlertCandidate
from functions.compute.feature_engine import FeatureSet
from functions.config.settings import get_settings
from functions.util.logging_setup import get_logger

logger = get_logger(__name__)


class EarningsCrushDetector(DetectorPlugin):
    """
    Detects pre-earnings IV crush setup for spread trading strategies.

    When an earnings date approaches within 14 days and IV is elevated, options
    pricing reflects high uncertainty. Post-earnings, IV typically collapses as
    uncertainty is resolved, creating a profitable opportunity for spread sellers
    who benefit from IV crush.

    Attributes:
        name: "EarningsCrushDetector"
        description: Detects pre-earnings IV crush setup (earnings within 0-14 days, elevated IV)
        config_key: "detectors.earnings_crush"

    Example:
        >>> detector = EarningsCrushDetector()
        >>> alert = detector.detect_safe(features)
        >>> if alert:
        ...     print(f"Score: {alert.score}")
        ...     print(f"Days to earnings: {alert.metrics['days_to_earnings']}")
        ...     print(f"Strategies: {alert.strategies}")
    """

    @property
    def name(self) -> str:
        """Get detector name."""
        return "EarningsCrushDetector"

    @property
    def description(self) -> str:
        """Get detector description."""
        return "Detects pre-earnings IV crush setup (earnings within 0-14 days, elevated IV)"

    def get_config_key(self) -> str:
        """Get configuration key for this detector."""
        return "detectors.earnings_crush"

    def detect(self, features: FeatureSet) -> Optional[AlertCandidate]:
        """
        Detect earnings crush opportunities in the feature set.

        Analysis process:
        1. Extract days_to_earnings from features
        2. Validate earnings is within 0-14 days window
        3. Extract IV percentile from features
        4. Get configuration thresholds
        5. Check if IV percentile meets threshold
        6. Calculate base score based on days_to_earnings:
           - Days 0-3: base = 95 (crush happens post-earnings)
           - Days 4-7: base = 85 (IV crush risk still high)
           - Days 8-14: base = 70 (farther out, less certain)
        7. Apply context modifiers:
           - If IV rank > 75: bonus +10 (extreme high IV)
           - If ATM IV > 0.60: bonus +5 (huge premium to crush)
           - If price at 52-week high relative to sector: penalty -15 (surprise risk)
        8. Clamp score to [0, 100]
        9. Return AlertCandidate if score >= 60

        Args:
            features (FeatureSet): Market data feature set containing earnings and IV data

        Returns:
            AlertCandidate: If earnings crush setup detected with score >= 60
            None: If conditions not met or insufficient data

        Raises:
            None - all exceptions are caught and logged by detect_safe()
        """
        logger.debug(f"Starting EarningsCrushDetector analysis for {features.ticker}")

        # =====================================================================
        # STEP 1: Extract and validate days_to_earnings
        # =====================================================================
        days_to_earnings = features.earnings.get("days_to_earnings")

        if days_to_earnings is None:
            logger.debug(
                f"[{features.ticker}] Days to earnings not available, skipping detection"
            )
            return None

        logger.debug(f"[{features.ticker}] Days to earnings: {days_to_earnings}")

        # =====================================================================
        # STEP 2: Validate earnings is within 0-14 days window
        # =====================================================================
        # Get config threshold (default: 14 days)
        max_days_to_earnings = 14
        try:
            settings = get_settings()
            # In production, would load from config.yaml
            # max_days_to_earnings = config.get("detectors.earnings_crush.max_days_to_earnings", 14)
        except Exception as e:
            logger.debug(f"Could not load max_days_to_earnings config: {e}, using default 14")

        # Check if earnings is within valid window (0-14 days, not past or too far)
        if days_to_earnings is None or days_to_earnings <= 0 or days_to_earnings > max_days_to_earnings:
            logger.debug(
                f"[{features.ticker}] Earnings in {days_to_earnings} days, "
                f"outside window [0-{max_days_to_earnings}], skipping"
            )
            return None

        logger.debug(
            f"[{features.ticker}] Earnings within {days_to_earnings} days (window: 0-{max_days_to_earnings})"
        )

        # =====================================================================
        # STEP 3: Extract IV percentile
        # =====================================================================
        iv_percentile = features.iv_metrics.get("iv_percentile")

        if iv_percentile is None or (isinstance(iv_percentile, float) and math.isnan(iv_percentile)):
            logger.debug(
                f"[{features.ticker}] IV percentile not available, skipping detection"
            )
            return None

        logger.debug(f"[{features.ticker}] IV percentile: {iv_percentile:.1f}")

        # =====================================================================
        # STEP 4: Get configuration threshold for IV percentile
        # =====================================================================
        # Default to 60.0 if not configured
        iv_percentile_threshold = 60.0

        try:
            settings = get_settings()
            # In production, would load from config.yaml
            # iv_percentile_threshold = config.get("detectors.earnings_crush.iv_percentile_threshold", 60.0)
        except Exception as e:
            logger.debug(f"Could not load IV threshold config: {e}, using default 60.0")

        logger.debug(f"[{features.ticker}] IV percentile threshold: {iv_percentile_threshold:.1f}")

        # =====================================================================
        # STEP 5: Check if IV percentile meets threshold
        # =====================================================================
        if iv_percentile < iv_percentile_threshold:
            logger.debug(
                f"[{features.ticker}] IV percentile {iv_percentile:.1f} < threshold {iv_percentile_threshold:.1f}, "
                f"IV not elevated enough for crush opportunity"
            )
            return None

        logger.debug(
            f"[{features.ticker}] IV percentile {iv_percentile:.1f} >= threshold {iv_percentile_threshold:.1f}, "
            f"elevated IV confirmed"
        )

        # =====================================================================
        # STEP 6: Calculate base score based on days_to_earnings
        # =====================================================================
        if days_to_earnings <= 3:
            base_score = 95  # Crush happens post-earnings
        elif days_to_earnings <= 7:
            base_score = 85  # IV crush risk still high
        else:  # 8-14 days
            base_score = 70  # Farther out, less certain

        logger.debug(f"[{features.ticker}] Base score: {base_score} (days_to_earnings={days_to_earnings})")

        # =====================================================================
        # STEP 7: Apply context modifiers
        # =====================================================================
        score = base_score
        modifiers_log = []

        # Modifier 1: IV rank > 75 (extreme high IV - bonus)
        iv_rank = features.iv_metrics.get("iv_rank")
        if iv_rank is not None and not math.isnan(iv_rank):
            if iv_rank > 75:
                score += 10
                modifiers_log.append(f"IV rank > 75 (+10 points, rank={iv_rank:.1f})")
                logger.debug(f"[{features.ticker}] IV rank > 75, added 10 points (rank={iv_rank:.1f})")

        # Modifier 2: ATM IV > 0.60 (60% annualized - huge premium - bonus)
        atm_iv_front = features.options_front.get("atm_iv")
        if atm_iv_front is not None and not math.isnan(atm_iv_front):
            if atm_iv_front > 0.60:
                score += 5
                modifiers_log.append(f"ATM IV > 60% (+5 points, IV={atm_iv_front:.2%})")
                logger.debug(
                    f"[{features.ticker}] ATM IV {atm_iv_front:.2%} > 60%, added 5 points"
                )

        # Modifier 3: Price at 52-week high relative to position (post-earnings risk - penalty)
        # If price is significantly above historical levels, there's higher risk of post-earnings disappointment
        price_52w_high = features.technicals.get("price_52w_high")
        if price_52w_high is not None and not math.isnan(price_52w_high):
            if price_52w_high > 0:
                price_pct_of_high = features.price / price_52w_high
                # If price is 95%+ of 52-week high, there's elevated downside risk
                if price_pct_of_high >= 0.95:
                    score -= 15
                    modifiers_log.append(f"Price near 52w high (-15 points, {price_pct_of_high:.1%} of high)")
                    logger.debug(
                        f"[{features.ticker}] Price {price_pct_of_high:.1%} of 52w high, "
                        f"reduced score by 15 (surprise risk)"
                    )

        # =====================================================================
        # STEP 8: Clamp score to [0, 100]
        # =====================================================================
        score = max(0, min(100, score))

        logger.debug(
            f"[{features.ticker}] Final score: {score:.1f} "
            f"(modifiers: {', '.join(modifiers_log) if modifiers_log else 'none'})"
        )

        # =====================================================================
        # STEP 9: Check if score passes risk gate (>= 60)
        # =====================================================================
        if score < 60:
            logger.debug(
                f"[{features.ticker}] Score {score:.1f} < risk gate (60), alert filtered"
            )
            return None

        logger.info(f"[{features.ticker}] EarningsCrushDetector alert triggered: score={score:.1f}")

        # =====================================================================
        # STEP 10: Determine confidence level
        # =====================================================================
        if days_to_earnings <= 7:
            confidence = "high"
        else:  # 8-14 days
            confidence = "medium"

        # =====================================================================
        # STEP 11: Build metrics dictionary
        # =====================================================================
        metrics = {
            "days_to_earnings": days_to_earnings,
            "iv_percentile": iv_percentile,
            "iv_rank": iv_rank,
            "atm_iv_front": atm_iv_front,
            "event_timing": self._describe_event_timing(days_to_earnings),
        }

        # =====================================================================
        # STEP 12: Build explanation dictionary
        # =====================================================================
        explanation = {
            "summary": self._build_summary(features.ticker, days_to_earnings, iv_percentile),
            "reason": self._build_reason(days_to_earnings, iv_percentile),
            "trigger": self._build_trigger(days_to_earnings, iv_percentile, iv_percentile_threshold),
            "warning": self._build_warning(days_to_earnings),
        }

        # =====================================================================
        # STEP 13: Define strategies
        # =====================================================================
        strategies = [
            "Iron Condor",
            "Bull Put Spread",
            "Bear Call Spread",
        ]

        # =====================================================================
        # STEP 14: Create and return AlertCandidate
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
            f"[{features.ticker}] EarningsCrushDetector returning alert: "
            f"score={alert.score:.1f}, confidence={alert.confidence}, "
            f"days_to_earnings={days_to_earnings}"
        )

        return alert

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _describe_event_timing(self, days_to_earnings: int) -> str:
        """
        Describe the event timing for alerts.

        Args:
            days_to_earnings (int): Days until earnings announcement

        Returns:
            str: Human-readable description of event timing
        """
        if days_to_earnings <= 1:
            return "Earnings tomorrow or today"
        elif days_to_earnings <= 3:
            return f"Earnings in {days_to_earnings} days (within week)"
        elif days_to_earnings <= 7:
            return f"Earnings in {days_to_earnings} days (within 1-2 weeks)"
        else:
            return f"Earnings in {days_to_earnings} days (2+ weeks)"

    def _build_summary(self, ticker: str, days_to_earnings: int, iv_percentile: float) -> str:
        """
        Build concise summary of the earnings crush detection.

        Args:
            ticker (str): Stock ticker symbol
            days_to_earnings (int): Days until earnings
            iv_percentile (float): Current IV percentile (0-100)

        Returns:
            str: 1-2 sentence summary of the detection
        """
        timing = self._describe_event_timing(days_to_earnings)
        return (
            f"{ticker} has earnings {timing} with elevated IV ({iv_percentile:.0f}th percentile). "
            f"IV crush opportunity post-earnings as uncertainty resolves."
        )

    def _build_reason(self, days_to_earnings: int, iv_percentile: float) -> str:
        """
        Build explanation of why earnings crush matters for trading.

        Args:
            days_to_earnings (int): Days until earnings
            iv_percentile (float): Current IV percentile

        Returns:
            str: Explanation of trading significance
        """
        return (
            f"Pre-earnings, implied volatility is elevated ({iv_percentile:.0f}th percentile) "
            f"reflecting market uncertainty about earnings outcome. Post-earnings, once uncertainty "
            f"is resolved, IV typically collapses significantly. Spread sellers (iron condors, put/call "
            f"spreads) benefit from this IV crush, collecting premium with defined risk."
        )

    def _build_trigger(
        self, days_to_earnings: int, iv_percentile: float, threshold: float
    ) -> str:
        """
        Build trigger explanation describing what triggered the alert.

        Args:
            days_to_earnings (int): Days until earnings
            iv_percentile (float): Current IV percentile
            threshold (float): IV percentile threshold

        Returns:
            str: Description of what triggered the alert
        """
        return (
            f"Earnings in {days_to_earnings} days with IV percentile ({iv_percentile:.1f}) "
            f"at/above threshold ({threshold:.1f}), creating elevated IV crush opportunity."
        )

    def _build_warning(self, days_to_earnings: int) -> str:
        """
        Build warning text about earnings-specific risks.

        Args:
            days_to_earnings (int): Days until earnings

        Returns:
            str: Warning about post-earnings risks and large moves
        """
        if days_to_earnings <= 1:
            return (
                "CRITICAL: Earnings announcement imminent. Large directional moves likely. "
                "Spreads may gap through short strikes. Consider shorter duration, wider strikes."
            )
        elif days_to_earnings <= 3:
            return (
                "WARNING: Earnings very soon (within 3 days). Market may move significantly. "
                "Ensure strike selection accounts for implied move magnitude."
            )
        else:
            return (
                "NOTE: Post-earnings, stock may move dramatically. Spreads should use appropriate "
                "strike widths to contain directional risk."
            )


# ============================================================================
# PLUGIN REGISTRATION
# ============================================================================

# Register the detector at import time
try:
    DetectorRegistry.register(EarningsCrushDetector)
    logger.debug("EarningsCrushDetector registered successfully")
except Exception as e:
    logger.error(f"Failed to register EarningsCrushDetector: {e}", exc_info=True)
