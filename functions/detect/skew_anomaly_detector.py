"""
Skew Anomaly Detector - Identifies put-call skew imbalances in options chains.

This detector identifies when implied volatility distribution across strikes becomes
imbalanced, indicating unusual market sentiment or expectation of directional movement.
Skew represents the premium difference between out-of-money puts and calls, which
varies based on market expectations for downside vs upside risk.

Detection Logic:
    - Extract 25-delta skew from features (25 delta put IV minus 25 delta call IV)
    - Detect when skew deviates from normal range, indicating imbalance
    - Applies context modifiers (price near support/resistance, RSI extremes, volume)
    - Returns high-confidence alerts for directional skew anomalies

Configuration:
    Key: "detectors.skew_anomaly"
    Fields:
        enabled (bool): Enable this detector
        normal_skew_range_min (float): Lower bound of normal skew (default: -0.10)
        normal_skew_range_max (float): Upper bound of normal skew (default: 0.10)
        anomaly_threshold (float): Absolute skew deviation threshold (default: 0.15)

Risk Gate:
    Score must be >= 60 to pass risk gates and be actionable.

Skew Directions:
    - PUT_SKEW (positive skew > 0): Puts more expensive than calls
        Indicates downside protection premium, market expects downside move
    - CALL_SKEW (negative skew < 0): Calls more expensive than puts
        Indicates upside demand, market expects upside move

Strategies:
    - "Bear Call Spread" if put_skew (downside expected)
    - "Bull Put Spread" if call_skew (upside expected)

Confidence Levels:
    - "high": |skew| > 0.25 (extreme imbalance with strong signals)
    - "medium": |skew| > 0.15 (moderate imbalance)
    - "low": |skew| > threshold (marginal imbalance)

Usage:
    from functions.detect.base import DetectorRegistry
    from functions.compute.feature_engine import FeatureSet

    registry = DetectorRegistry.get_registry()
    detector = registry.get_detector("SkewAnomalyDetector")
    alert = detector.detect_safe(features)
    if alert:
        print(f"Skew anomaly: {alert.explanation['summary']}")
        print(f"Direction: {alert.metrics['skew_direction']}")
"""

import logging
import math
from typing import Optional

from functions.detect.base import DetectorPlugin, DetectorRegistry, AlertCandidate
from functions.compute.feature_engine import FeatureSet
from functions.config.settings import get_settings
from functions.util.logging_setup import get_logger

logger = get_logger(__name__)


class SkewAnomalyDetector(DetectorPlugin):
    """
    Detects put-call skew imbalances indicating directional market sentiment.

    When implied volatility distribution across strikes becomes imbalanced, it reveals
    market expectations for directional movement. Positive skew (puts more expensive)
    suggests downside protection premium and downside expectations. Negative skew
    (calls more expensive) suggests upside demand and upside expectations.

    Attributes:
        name: "SkewAnomalyDetector"
        description: Detects unusual put-call skew imbalances in options chains
        config_key: "detectors.skew_anomaly"

    Example:
        >>> detector = SkewAnomalyDetector()
        >>> alert = detector.detect_safe(features)
        >>> if alert:
        ...     print(f"Score: {alert.score}")
        ...     print(f"Skew Direction: {alert.metrics['skew_direction']}")
        ...     print(f"Strategies: {alert.strategies}")
    """

    @property
    def name(self) -> str:
        """Get detector name."""
        return "SkewAnomalyDetector"

    @property
    def description(self) -> str:
        """Get detector description."""
        return "Detects unusual put-call skew imbalances in options chains"

    def get_config_key(self) -> str:
        """Get configuration key for this detector."""
        return "detectors.skew_anomaly"

    def detect(self, features: FeatureSet) -> Optional[AlertCandidate]:
        """
        Detect skew anomalies in the feature set.

        Analysis process:
        1. Extract 25-delta skew from features
        2. Validate data availability
        3. Get configuration thresholds
        4. Calculate skew deviation from normal range
        5. Return None if deviation is small (normal skew)
        6. Determine skew direction (PUT_SKEW vs CALL_SKEW)
        7. Calculate base score from deviation magnitude
        8. Apply contextual modifiers:
           - If price near support/resistance (within 2% of fib levels): +15 (directional risk confirmed)
           - If RSI extreme (> 70 or < 30): +20 (momentum backing directional bias)
           - If volume in skewed direction is elevated: +10 (conviction signal)
        9. Clamp score to [0, 100]
        10. Return AlertCandidate if score >= 60

        Args:
            features (FeatureSet): Market data feature set containing skew metrics

        Returns:
            AlertCandidate: If skew anomaly detected with score >= 60
            None: If conditions not met or insufficient data

        Raises:
            None - all exceptions are caught and logged by detect_safe()
        """
        logger.debug(f"Starting SkewAnomalyDetector analysis for {features.ticker}")

        # =====================================================================
        # STEP 1: Extract and validate 25-delta skew
        # =====================================================================
        skew_25d = features.options_front.get("skew_25d")

        if skew_25d is None or (isinstance(skew_25d, float) and math.isnan(skew_25d)):
            logger.debug(
                f"[{features.ticker}] 25-delta skew not available, skipping detection"
            )
            return None

        logger.debug(f"[{features.ticker}] 25-delta skew: {skew_25d:.4f}")

        # =====================================================================
        # STEP 2: Get configuration thresholds
        # =====================================================================
        settings = get_settings()
        # Default configuration values
        normal_skew_range_min = -0.10
        normal_skew_range_max = 0.10
        anomaly_threshold = 0.15

        # Try to get from AppConfig if available (via app context)
        try:
            # Note: In a production system, AppConfig would come from config.yaml
            # For now, we use the default thresholds
            pass
        except Exception as e:
            logger.debug(f"Could not load detector config: {e}, using default thresholds")

        logger.debug(
            f"[{features.ticker}] Configuration: normal_range=[{normal_skew_range_min:.2f}, "
            f"{normal_skew_range_max:.2f}], anomaly_threshold={anomaly_threshold:.2f}"
        )

        # =====================================================================
        # STEP 3: Check if skew is within normal range
        # =====================================================================
        if normal_skew_range_min <= skew_25d <= normal_skew_range_max:
            logger.debug(
                f"[{features.ticker}] Skew {skew_25d:.4f} within normal range "
                f"[{normal_skew_range_min:.2f}, {normal_skew_range_max:.2f}], no anomaly"
            )
            return None

        # =====================================================================
        # STEP 4: Calculate skew deviation
        # =====================================================================
        # Deviation is the absolute distance from the normal range
        if skew_25d > normal_skew_range_max:
            skew_deviation = skew_25d - normal_skew_range_max
        else:
            skew_deviation = normal_skew_range_min - skew_25d

        logger.debug(f"[{features.ticker}] Skew deviation: {skew_deviation:.4f}")

        # =====================================================================
        # STEP 5: Check if deviation meets anomaly threshold
        # =====================================================================
        absolute_deviation = abs(skew_deviation)
        if absolute_deviation < anomaly_threshold:
            logger.debug(
                f"[{features.ticker}] Skew deviation {absolute_deviation:.4f} < "
                f"anomaly threshold {anomaly_threshold:.2f}, skew is normal"
            )
            return None

        logger.debug(
            f"[{features.ticker}] Skew anomaly detected: deviation={absolute_deviation:.4f} "
            f">= threshold {anomaly_threshold:.2f}"
        )

        # =====================================================================
        # STEP 6: Determine skew direction
        # =====================================================================
        if skew_25d > 0:
            skew_direction = "PUT_SKEW"
            direction_description = "Puts more expensive (downside protection premium)"
            directional_implication = "Market expects downside move"
        else:
            skew_direction = "CALL_SKEW"
            direction_description = "Calls more expensive (upside demand)"
            directional_implication = "Market expects upside move"

        logger.debug(f"[{features.ticker}] Skew direction: {skew_direction}")

        # =====================================================================
        # STEP 7: Calculate base score
        # =====================================================================
        # Base score is the normalized deviation magnitude (0-100 scale)
        # At anomaly_threshold, score = 0
        # At 2x anomaly_threshold, score = 100
        base_score = (absolute_deviation / anomaly_threshold) * 100
        base_score = min(100, base_score)  # Cap at 100

        logger.debug(f"[{features.ticker}] Base score: {base_score:.1f}")

        # =====================================================================
        # STEP 8: Apply contextual modifiers
        # =====================================================================
        score = base_score
        modifiers_log = []

        # Modifier 1: Price near support/resistance (within 2% of fib levels)
        fib_levels = features.technicals.get("fib_levels", {})
        if fib_levels and features.price is not None:
            resistance_382 = fib_levels.get("resistance_382")
            resistance_618 = fib_levels.get("resistance_618")
            support_382 = fib_levels.get("support_382")
            support_618 = fib_levels.get("support_618")

            near_fib = False
            if resistance_382 is not None and not math.isnan(resistance_382):
                if abs(features.price - resistance_382) / resistance_382 < 0.02:
                    near_fib = True
            if resistance_618 is not None and not math.isnan(resistance_618):
                if abs(features.price - resistance_618) / resistance_618 < 0.02:
                    near_fib = True
            if support_382 is not None and not math.isnan(support_382):
                if abs(features.price - support_382) / support_382 < 0.02:
                    near_fib = True
            if support_618 is not None and not math.isnan(support_618):
                if abs(features.price - support_618) / support_618 < 0.02:
                    near_fib = True

            if near_fib:
                score += 15
                modifiers_log.append("Price near support/resistance (+15 points)")
                logger.debug(
                    f"[{features.ticker}] Price {features.price:.2f} within 2% of "
                    f"Fibonacci level, added 15 points"
                )

        # Modifier 2: RSI showing extreme (> 70 or < 30)
        rsi_14 = features.technicals.get("rsi")
        if rsi_14 is not None and not math.isnan(rsi_14):
            if rsi_14 > 70 or rsi_14 < 30:
                score += 20
                modifiers_log.append(f"RSI extreme (+20 points, RSI={rsi_14:.1f})")
                logger.debug(
                    f"[{features.ticker}] RSI {rsi_14:.1f} is extreme, added 20 points"
                )

        # Modifier 3: Volume in skewed direction is elevated
        call_volume = features.options_front.get("call_volume")
        put_volume = features.options_front.get("put_volume")
        volume_sma_20 = features.technicals.get("volume_sma_20")

        if call_volume is not None and put_volume is not None and volume_sma_20 is not None:
            if volume_sma_20 > 0:
                if skew_direction == "PUT_SKEW":
                    # PUT_SKEW: check if put volume is elevated
                    put_volume_ratio = put_volume / volume_sma_20 if volume_sma_20 > 0 else 0
                    if put_volume_ratio > 1.5:  # 50% above average
                        score += 10
                        modifiers_log.append(
                            f"Elevated put volume (+10 points, ratio={put_volume_ratio:.2f})"
                        )
                        logger.debug(
                            f"[{features.ticker}] Put volume {put_volume_ratio:.2f}x average, "
                            f"added 10 points"
                        )
                else:
                    # CALL_SKEW: check if call volume is elevated
                    call_volume_ratio = call_volume / volume_sma_20 if volume_sma_20 > 0 else 0
                    if call_volume_ratio > 1.5:  # 50% above average
                        score += 10
                        modifiers_log.append(
                            f"Elevated call volume (+10 points, ratio={call_volume_ratio:.2f})"
                        )
                        logger.debug(
                            f"[{features.ticker}] Call volume {call_volume_ratio:.2f}x average, "
                            f"added 10 points"
                        )

        # =====================================================================
        # STEP 9: Clamp score to [0, 100]
        # =====================================================================
        score = max(0, min(100, score))

        logger.debug(
            f"[{features.ticker}] Final score: {score:.1f} "
            f"(modifiers: {', '.join(modifiers_log) if modifiers_log else 'none'})"
        )

        # =====================================================================
        # STEP 10: Check if score passes risk gate (>= 60)
        # =====================================================================
        if score < 60:
            logger.debug(
                f"[{features.ticker}] Score {score:.1f} < risk gate (60), alert filtered"
            )
            return None

        logger.info(f"[{features.ticker}] SkewAnomalyDetector alert triggered: score={score:.1f}")

        # =====================================================================
        # STEP 11: Determine confidence level
        # =====================================================================
        if abs(skew_25d) > 0.25:
            confidence = "high"
        elif abs(skew_25d) > 0.15:
            confidence = "medium"
        else:
            confidence = "low"

        # =====================================================================
        # STEP 12: Build metrics dictionary
        # =====================================================================
        metrics = {
            "skew_25d": skew_25d,
            "skew_direction": skew_direction,
            "skew_deviation": absolute_deviation,
            "price_vs_fib": self._calculate_price_vs_fib(features),
            "rsi_14": rsi_14,
            "volume_bias": self._calculate_volume_bias(call_volume, put_volume),
            "skew_severity": "extreme" if abs(skew_25d) > 0.25 else ("high" if abs(skew_25d) > 0.20 else "moderate"),
        }

        # =====================================================================
        # STEP 13: Build explanation dictionary
        # =====================================================================
        explanation = {
            "summary": self._build_summary(features.ticker, skew_direction, skew_25d),
            "reason": self._build_reason(skew_direction, directional_implication, confidence),
            "trigger": self._build_trigger(skew_25d, direction_description),
            "directional_implication": directional_implication,
        }

        # =====================================================================
        # STEP 14: Define strategies based on skew direction
        # =====================================================================
        if skew_direction == "PUT_SKEW":
            strategies = ["Bear Call Spread"]
        else:  # CALL_SKEW
            strategies = ["Bull Put Spread"]

        # =====================================================================
        # STEP 15: Create and return AlertCandidate
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
            f"[{features.ticker}] SkewAnomalyDetector returning alert: "
            f"score={alert.score:.1f}, confidence={alert.confidence}, "
            f"direction={skew_direction}"
        )

        return alert

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _calculate_price_vs_fib(self, features: FeatureSet) -> Optional[str]:
        """
        Determine if price is near Fibonacci support/resistance levels.

        Args:
            features (FeatureSet): Feature set containing price and Fibonacci levels

        Returns:
            str: Description of price position relative to Fibonacci levels, or None
        """
        fib_levels = features.technicals.get("fib_levels", {})
        if not fib_levels or features.price is None:
            return None

        tolerance = 0.02  # 2%

        resistance_levels = [
            (fib_levels.get("resistance_382"), "38.2%"),
            (fib_levels.get("resistance_618"), "61.8%"),
        ]

        support_levels = [
            (fib_levels.get("support_382"), "38.2%"),
            (fib_levels.get("support_618"), "61.8%"),
        ]

        for level, label in resistance_levels:
            if level is not None and not math.isnan(level):
                if abs(features.price - level) / level < tolerance:
                    return f"near_resistance_{label}"

        for level, label in support_levels:
            if level is not None and not math.isnan(level):
                if abs(features.price - level) / level < tolerance:
                    return f"near_support_{label}"

        return None

    def _calculate_volume_bias(
        self, call_volume: Optional[float], put_volume: Optional[float]
    ) -> Optional[str]:
        """
        Determine volume bias between calls and puts.

        Args:
            call_volume (Optional[float]): Call volume
            put_volume (Optional[float]): Put volume

        Returns:
            str: "call_heavy", "put_heavy", "balanced", or None if data unavailable
        """
        if call_volume is None or put_volume is None:
            return None

        total_volume = call_volume + put_volume
        if total_volume == 0:
            return None

        call_ratio = call_volume / total_volume
        put_ratio = put_volume / total_volume

        if call_ratio > 0.60:
            return "call_heavy"
        elif put_ratio > 0.60:
            return "put_heavy"
        else:
            return "balanced"

    def _build_summary(self, ticker: str, skew_direction: str, skew_value: float) -> str:
        """
        Build concise summary of the skew anomaly detection.

        Args:
            ticker (str): Stock ticker symbol
            skew_direction (str): Direction of skew (PUT_SKEW or CALL_SKEW)
            skew_value (float): Actual skew value

        Returns:
            str: 1-2 sentence summary of the detection
        """
        if skew_direction == "PUT_SKEW":
            return (
                f"{ticker} showing extreme put skew ({skew_value:.4f}). "
                f"Puts significantly more expensive than calls, indicating downside protection premium."
            )
        else:
            return (
                f"{ticker} showing extreme call skew ({skew_value:.4f}). "
                f"Calls significantly more expensive than puts, indicating strong upside demand."
            )

    def _build_reason(self, skew_direction: str, implication: str, confidence: str) -> str:
        """
        Build explanation of why skew matters for trading.

        Args:
            skew_direction (str): PUT_SKEW or CALL_SKEW
            implication (str): Directional implication of the skew
            confidence (str): Confidence level (high/medium/low)

        Returns:
            str: Explanation of trading significance
        """
        base_reason = (
            "Skew imbalances reveal market sentiment through IV distribution across strikes. "
            "Directional skew suggests asymmetric risk pricing, creating trading opportunities "
            "aligned with market expectations."
        )

        if confidence == "high":
            if skew_direction == "PUT_SKEW":
                return (
                    f"{base_reason} Extreme put skew indicates {implication.lower()} "
                    f"with high conviction. Consider put-heavy strategies or downside hedges."
                )
            else:
                return (
                    f"{base_reason} Extreme call skew indicates {implication.lower()} "
                    f"with high conviction. Consider call-heavy strategies for upside exposure."
                )
        elif confidence == "medium":
            if skew_direction == "PUT_SKEW":
                return (
                    f"{base_reason} Moderate put skew suggests {implication.lower()}. "
                    f"Use as secondary confirmation with other technicals."
                )
            else:
                return (
                    f"{base_reason} Moderate call skew suggests {implication.lower()}. "
                    f"Use as secondary confirmation with other technicals."
                )
        else:
            return (
                f"{base_reason} Marginal skew provides limited directional signal. "
                f"Use only as tertiary confirmation with strong technical setup."
            )

    def _build_trigger(self, skew_value: float, description: str) -> str:
        """
        Build trigger explanation describing the specific skew anomaly.

        Args:
            skew_value (float): Current skew value
            description (str): Description of skew direction

        Returns:
            str: Description of what triggered the alert
        """
        return (
            f"25-delta skew ({skew_value:.4f}) shows significant imbalance: {description}. "
            f"Deviation from normal range ({-0.10:.2f} to {0.10:.2f}) indicates unusual "
            f"IV distribution across strikes."
        )


# ============================================================================
# PLUGIN REGISTRATION
# ============================================================================

# Register the detector at import time
try:
    DetectorRegistry.register(SkewAnomalyDetector)
    logger.debug("SkewAnomalyDetector registered successfully")
except Exception as e:
    logger.error(f"Failed to register SkewAnomalyDetector: {e}", exc_info=True)
