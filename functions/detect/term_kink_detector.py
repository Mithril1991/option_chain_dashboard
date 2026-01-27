"""
Term Kink Detector - Identifies unusual term structure patterns.

This detector identifies when the implied volatility term structure exhibits
unusual patterns (abnormal contango/backwardation), signaling potential
opportunities in calendar spread strategies.

Detection Logic:
    - Monitors the ratio of back-month IV to front-month IV (term structure ratio)
    - Detects two anomalies:
        1. BACKWARDATION (ratio < normal_contango_min):
           Front-month IV is expensive relative to back-month (e.g., earnings/events)
           Suggests calendar spread selling opportunities
        2. STEEP_CONTANGO (ratio > normal_contango_max):
           Back-month IV is expensive relative to front-month (e.g., vol crush/premium decay)
           Suggests calendar spread buying opportunities
    - Applies context modifiers (IV percentile, OI concentration, skew)
    - Returns high-confidence alerts for unusual term structure patterns

Configuration:
    Key: "detectors.term_kink"
    Fields:
        enabled (bool): Enable this detector
        normal_contango_min (float): Lower bound of normal contango (default: 0.98)
            Ratios below this trigger backwardation alert
        normal_contango_max (float): Upper bound of normal contango (default: 1.15)
            Ratios above this trigger steep contango alert

Risk Gate:
    Score must be >= 60 to pass risk gates and be actionable.

Strategies:
    - "Calendar Spread": Buy/sell vol across expirations based on kink direction

Confidence Levels:
    - "high": Ratio deviation > 20% from normal band (extreme kink)
    - "medium": Ratio deviation > 10% from normal band (moderate kink)
    - "low": Ratio deviation at band edges (marginal kink)

Metrics Returned:
    - term_structure_ratio: Back IV / Front IV
    - iv_front: Front-month ATM IV
    - iv_back: Back-month ATM IV
    - front_oi: Front-month open interest
    - back_oi: Back-month open interest
    - skew: Put IV - Call IV (directional event indicator)
    - event_type: "BACKWARDATION" or "STEEP_CONTANGO"

Usage:
    from functions.detect.base import DetectorRegistry
    from functions.compute.feature_engine import FeatureSet

    registry = DetectorRegistry.get_registry()
    detector = registry.get_detector("TermKinkDetector")
    alert = detector.detect_safe(features)
    if alert:
        print(f"Term structure kink: {alert.explanation['summary']}")
"""

import logging
import math
from typing import Optional

from functions.detect.base import DetectorPlugin, DetectorRegistry, AlertCandidate
from functions.compute.feature_engine import FeatureSet
from functions.config.settings import get_settings
from functions.util.logging_setup import get_logger

logger = get_logger(__name__)


class TermKinkDetector(DetectorPlugin):
    """
    Detects unusual term structure patterns for calendar spread opportunities.

    When the implied volatility term structure deviates from normal contango/backwardation,
    it creates opportunities for calendar spread trading. This detector identifies these
    kinks and quantifies their severity.

    Attributes:
        name: "TermKinkDetector"
        description: Detects abnormal IV term structure patterns
        config_key: "detectors.term_kink"

    Example:
        >>> detector = TermKinkDetector()
        >>> alert = detector.detect_safe(features)
        >>> if alert:
        ...     print(f"Score: {alert.score}")
        ...     print(f"Term structure ratio: {alert.metrics['term_structure_ratio']}")
        ...     print(f"Event type: {alert.metrics['event_type']}")
    """

    @property
    def name(self) -> str:
        """Get detector name."""
        return "TermKinkDetector"

    @property
    def description(self) -> str:
        """Get detector description."""
        return "Detects abnormal IV term structure patterns for calendar spread opportunities"

    def get_config_key(self) -> str:
        """Get configuration key for this detector."""
        return "detectors.term_kink"

    def detect(self, features: FeatureSet) -> Optional[AlertCandidate]:
        """
        Detect unusual term structure patterns in the feature set.

        Analysis process:
        1. Extract IV values from front and back month options
        2. Validate data availability
        3. Calculate term structure ratio (back IV / front IV)
        4. Get configuration parameters (normal contango bounds)
        5. Detect anomalies (backwardation or steep contango)
        6. Calculate base score based on deviation magnitude
        7. Apply contextual modifiers:
           - IV percentile: If low (<30) with backwardation, penalty (less unusual)
           - OI concentration: If volume concentrated in front, bonus (liquidity explains it)
           - Skew: If extreme (|put_iv - call_iv| > 0.15), bonus (directional event)
        8. Return AlertCandidate if score >= 60

        Args:
            features (FeatureSet): Market data feature set containing options metrics

        Returns:
            AlertCandidate: If unusual term structure detected with score >= 60
            None: If conditions not met or insufficient data

        Raises:
            None - all exceptions are caught and logged by detect_safe()
        """
        logger.debug(f"Starting TermKinkDetector analysis for {features.ticker}")

        # =====================================================================
        # STEP 1: Extract and validate IV values
        # =====================================================================
        iv_front = features.options_front.get("atm_iv")
        iv_back = features.options_back.get("atm_iv")

        if iv_front is None or iv_back is None:
            logger.debug(
                f"[{features.ticker}] IV front or back not available, skipping detection"
            )
            return None

        # Check for NaN values
        if isinstance(iv_front, float) and math.isnan(iv_front):
            logger.debug(f"[{features.ticker}] IV front is NaN, skipping detection")
            return None

        if isinstance(iv_back, float) and math.isnan(iv_back):
            logger.debug(f"[{features.ticker}] IV back is NaN, skipping detection")
            return None

        # Check for zero values
        if iv_front == 0 or iv_back == 0:
            logger.debug(
                f"[{features.ticker}] IV front or back is zero, skipping detection"
            )
            return None

        logger.debug(
            f"[{features.ticker}] IV front: {iv_front:.4f}, IV back: {iv_back:.4f}"
        )

        # =====================================================================
        # STEP 2: Calculate term structure ratio
        # =====================================================================
        term_structure_ratio = iv_back / iv_front

        logger.debug(
            f"[{features.ticker}] Term structure ratio (back/front): {term_structure_ratio:.4f}"
        )

        # =====================================================================
        # STEP 3: Get configuration parameters
        # =====================================================================
        settings = get_settings()
        normal_contango_min = 0.98
        normal_contango_max = 1.15

        # Try to get from AppConfig if available (via app context)
        try:
            # Note: In a production system, AppConfig would come from config.yaml
            # For now, we use the default thresholds
            pass
        except Exception as e:
            logger.debug(f"Could not load detector config: {e}, using default thresholds")

        logger.debug(
            f"[{features.ticker}] Normal contango range: [{normal_contango_min:.4f}, {normal_contango_max:.4f}]"
        )

        # =====================================================================
        # STEP 4: Check if term structure is normal
        # =====================================================================
        if normal_contango_min <= term_structure_ratio <= normal_contango_max:
            logger.debug(
                f"[{features.ticker}] Term structure ratio {term_structure_ratio:.4f} "
                f"within normal range, no kink detected"
            )
            return None

        logger.debug(
            f"[{features.ticker}] Term structure ratio {term_structure_ratio:.4f} "
            f"outside normal range, kink detected"
        )

        # =====================================================================
        # STEP 5: Determine kink type and calculate base score
        # =====================================================================
        event_type = None
        base_score = 0

        if term_structure_ratio < normal_contango_min:
            # BACKWARDATION: front-month IV is expensive
            event_type = "BACKWARDATION"
            base_score = (normal_contango_min - term_structure_ratio) / normal_contango_min * 100
            logger.debug(
                f"[{features.ticker}] Backwardation detected: "
                f"ratio {term_structure_ratio:.4f} < {normal_contango_min:.4f}, "
                f"base_score={base_score:.1f}"
            )

        elif term_structure_ratio > normal_contango_max:
            # STEEP_CONTANGO: back-month IV is expensive
            event_type = "STEEP_CONTANGO"
            base_score = (term_structure_ratio - normal_contango_max) / normal_contango_max * 100
            logger.debug(
                f"[{features.ticker}] Steep contango detected: "
                f"ratio {term_structure_ratio:.4f} > {normal_contango_max:.4f}, "
                f"base_score={base_score:.1f}"
            )

        logger.debug(f"[{features.ticker}] Event type: {event_type}, base score: {base_score:.1f}")

        # =====================================================================
        # STEP 6: Apply context modifiers
        # =====================================================================
        score = base_score
        modifiers_log = []

        # Modifier 1: IV percentile < 30 AND backwardation - penalty (less unusual if IV low)
        iv_percentile = features.iv_metrics.get("iv_percentile")
        if (
            iv_percentile is not None
            and not math.isnan(iv_percentile)
            and iv_percentile < 30
            and event_type == "BACKWARDATION"
        ):
            score -= 20
            modifiers_log.append(f"Low IV percentile + backwardation (-20 points, IV%={iv_percentile:.1f})")
            logger.debug(
                f"[{features.ticker}] IV percentile {iv_percentile:.1f} < 30 "
                f"with backwardation, reduced score by 20"
            )

        # Modifier 2: Volume concentrated in front month - bonus (liquidity explains kink)
        front_oi = features.options_front.get("oi")
        back_oi = features.options_back.get("oi")
        if front_oi is not None and back_oi is not None:
            if back_oi > 0 and front_oi > back_oi * 1.5:
                score += 15
                modifiers_log.append(f"Front OI > back OI 1.5x (+15 points, front_oi={front_oi}, back_oi={back_oi})")
                logger.debug(
                    f"[{features.ticker}] Front OI {front_oi} > back OI {back_oi} * 1.5, "
                    f"added 15 points"
                )

        # Modifier 3: Extreme skew - bonus (directional event indicator)
        # Try to calculate skew from options_front greeks if available
        skew = self._calculate_skew(features)
        if skew is not None and not math.isnan(skew):
            abs_skew = abs(skew)
            if abs_skew > 0.15:
                score += 10
                modifiers_log.append(f"Extreme skew (+10 points, |skew|={abs_skew:.4f})")
                logger.debug(
                    f"[{features.ticker}] Extreme skew {abs_skew:.4f} > 0.15, added 10 points"
                )

        # =====================================================================
        # STEP 7: Clamp score to [0, 100]
        # =====================================================================
        score = max(0, min(100, score))

        logger.debug(
            f"[{features.ticker}] Final score: {score:.1f} "
            f"(modifiers: {', '.join(modifiers_log) if modifiers_log else 'none'})"
        )

        # =====================================================================
        # STEP 8: Check if score passes risk gate (>= 60)
        # =====================================================================
        if score < 60:
            logger.debug(
                f"[{features.ticker}] Score {score:.1f} < risk gate (60), alert filtered"
            )
            return None

        logger.info(f"[{features.ticker}] TermKinkDetector alert triggered: score={score:.1f}")

        # =====================================================================
        # STEP 9: Determine confidence level
        # =====================================================================
        # Calculate ratio deviation as percentage from normal band
        if event_type == "BACKWARDATION":
            ratio_deviation_pct = (
                (normal_contango_min - term_structure_ratio) / normal_contango_min * 100
            )
        else:  # STEEP_CONTANGO
            ratio_deviation_pct = (
                (term_structure_ratio - normal_contango_max) / normal_contango_max * 100
            )

        if ratio_deviation_pct > 20:
            confidence = "high"
        elif ratio_deviation_pct > 10:
            confidence = "medium"
        else:
            confidence = "low"

        logger.debug(
            f"[{features.ticker}] Ratio deviation: {ratio_deviation_pct:.1f}%, confidence: {confidence}"
        )

        # =====================================================================
        # STEP 10: Build metrics dictionary
        # =====================================================================
        metrics = {
            "term_structure_ratio": term_structure_ratio,
            "iv_front": iv_front,
            "iv_back": iv_back,
            "front_oi": front_oi,
            "back_oi": back_oi,
            "skew": skew,
            "event_type": event_type,
            "iv_percentile": iv_percentile,
        }

        # =====================================================================
        # STEP 11: Build explanation dictionary
        # =====================================================================
        explanation = {
            "summary": self._build_summary(features.ticker, event_type, term_structure_ratio),
            "reason": self._build_reason(event_type, ratio_deviation_pct, confidence),
            "trigger": self._build_trigger(event_type, term_structure_ratio, normal_contango_min, normal_contango_max),
            "opportunity": self._build_opportunity(event_type),
        }

        # =====================================================================
        # STEP 12: Define strategies
        # =====================================================================
        strategies = ["Calendar Spread"]

        # =====================================================================
        # STEP 13: Create and return AlertCandidate
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
            f"[{features.ticker}] TermKinkDetector returning alert: "
            f"score={alert.score:.1f}, confidence={alert.confidence}, "
            f"event_type={event_type}, ratio={term_structure_ratio:.4f}"
        )

        return alert

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _calculate_skew(self, features: FeatureSet) -> Optional[float]:
        """
        Calculate implied volatility skew (put IV - call IV).

        Attempts to extract put and call IV estimates from options Greeks data
        in the front-month options. If data unavailable, returns None.

        Args:
            features (FeatureSet): Feature set containing options data

        Returns:
            float: Put IV - Call IV (positive = put IV higher = bearish skew), or None
        """
        # Try to get skew from options_front if available
        # Note: This is a simplified approach; actual implementation would need
        # put/call IV data from the options chain
        # For now, we return None as this data may not be readily available

        # In a full implementation, you would:
        # 1. Get put and call options from options_front
        # 2. Calculate IV for each
        # 3. Return put_iv - call_iv

        return None

    def _build_summary(self, ticker: str, event_type: str, ratio: float) -> str:
        """
        Build concise summary of the term structure kink detection.

        Args:
            ticker (str): Stock ticker symbol
            event_type (str): "BACKWARDATION" or "STEEP_CONTANGO"
            ratio (float): Term structure ratio (back IV / front IV)

        Returns:
            str: 1-2 sentence summary of the detection
        """
        if event_type == "BACKWARDATION":
            return (
                f"{ticker} exhibiting unusual backwardation in IV term structure "
                f"(ratio {ratio:.4f}). Front-month IV expensive relative to back-month."
            )
        else:  # STEEP_CONTANGO
            return (
                f"{ticker} exhibiting steep contango in IV term structure "
                f"(ratio {ratio:.4f}). Back-month IV expensive relative to front-month."
            )

    def _build_reason(self, event_type: str, deviation_pct: float, confidence: str) -> str:
        """
        Build explanation of why term structure kink matters for trading.

        Args:
            event_type (str): "BACKWARDATION" or "STEEP_CONTANGO"
            deviation_pct (float): Percentage deviation from normal band
            confidence (str): Confidence level (high/medium/low)

        Returns:
            str: Explanation of trading significance
        """
        if event_type == "BACKWARDATION":
            base_reason = (
                "Backwardation (front-month IV premium) often signals upcoming catalysts "
                "(earnings, events) or market stress. Calendar spreads can monetize the "
                "relative expensiveness of near-term volatility."
            )

            if confidence == "high":
                return (
                    f"{base_reason} Extreme backwardation ({deviation_pct:.1f}% deviation) "
                    f"creates exceptional calendar spread selling opportunity."
                )
            elif confidence == "medium":
                return (
                    f"{base_reason} Moderate backwardation ({deviation_pct:.1f}% deviation) "
                    f"provides reasonable calendar spread opportunity."
                )
            else:
                return (
                    f"{base_reason} Marginal backwardation ({deviation_pct:.1f}% deviation) "
                    f"provides limited calendar spread opportunity."
                )
        else:  # STEEP_CONTANGO
            base_reason = (
                "Steep contango (back-month IV premium) can signal volatility crush "
                "expectations or theta decay opportunities. Calendar spreads can capture "
                "the premium decay in back-month vol as time passes."
            )

            if confidence == "high":
                return (
                    f"{base_reason} Extreme contango ({deviation_pct:.1f}% deviation) "
                    f"creates exceptional calendar spread buying opportunity."
                )
            elif confidence == "medium":
                return (
                    f"{base_reason} Moderate contango ({deviation_pct:.1f}% deviation) "
                    f"provides reasonable calendar spread opportunity."
                )
            else:
                return (
                    f"{base_reason} Marginal contango ({deviation_pct:.1f}% deviation) "
                    f"provides limited calendar spread opportunity."
                )

    def _build_trigger(
        self, event_type: str, ratio: float, min_bound: float, max_bound: float
    ) -> str:
        """
        Build trigger explanation describing the specific threshold cross.

        Args:
            event_type (str): "BACKWARDATION" or "STEEP_CONTANGO"
            ratio (float): Term structure ratio
            min_bound (float): Lower bound of normal range
            max_bound (float): Upper bound of normal range

        Returns:
            str: Description of what triggered the alert
        """
        if event_type == "BACKWARDATION":
            return (
                f"IV term structure ratio ({ratio:.4f}) fell below lower bound ({min_bound:.4f}), "
                f"indicating front-month IV expensive relative to back-month"
            )
        else:  # STEEP_CONTANGO
            return (
                f"IV term structure ratio ({ratio:.4f}) exceeded upper bound ({max_bound:.4f}), "
                f"indicating back-month IV expensive relative to front-month"
            )

    def _build_opportunity(self, event_type: str) -> str:
        """
        Build explanation of trading opportunity.

        Args:
            event_type (str): "BACKWARDATION" or "STEEP_CONTANGO"

        Returns:
            str: Description of the trading opportunity
        """
        if event_type == "BACKWARDATION":
            return (
                "Consider selling near-term calls/puts (sell volatility where it's expensive) "
                "and buying longer-dated calls/puts. This calendar spread captures the "
                "relative expensiveness of front-month volatility."
            )
        else:  # STEEP_CONTANGO
            return (
                "Consider buying near-term calls/puts (buy volatility where it's cheap) "
                "and selling longer-dated calls/puts. This reverse calendar spread captures "
                "the premium decay in back-month volatility."
            )


# ============================================================================
# PLUGIN REGISTRATION
# ============================================================================

# Register the detector at import time
try:
    DetectorRegistry.register(TermKinkDetector)
    logger.debug("TermKinkDetector registered successfully")
except Exception as e:
    logger.error(f"Failed to register TermKinkDetector: {e}", exc_info=True)
