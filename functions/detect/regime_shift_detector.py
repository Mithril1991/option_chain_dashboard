"""
Regime Shift Detector - Identifies technical regime changes in price action.

This detector identifies technical regime changes by analyzing price relationships
with moving averages and support/resistance levels. It detects three key regime
scenarios: golden crosses, death crosses, and support bounces.

Detection Logic:
    - Monitors price proximity to key moving averages (SMA50, SMA200)
    - Detects golden cross setup (SMA50 approaching SMA200 from below)
    - Detects death cross setup (SMA50 approaching SMA200 from above)
    - Detects support bounce setup (price bouncing off SMA50)
    - Applies momentum confirmation via MACD
    - Applies volume confirmation for conviction

Configuration:
    Key: "detectors.regime_shift"
    Fields:
        enabled (bool): Enable this detector
        proximity_threshold (float): % proximity to MA crossovers (default: 0.03 = 3%)
        volume_confirmation_pct (float): Volume multiple for confirmation (default: 1.2 = 20% above avg)

Risk Gate:
    Score must be >= 60 to pass risk gates and be actionable.

Regime Types:
    - "SMA_GOLDEN_CROSS": SMA50 crossing above SMA200 (bullish)
    - "SMA_DEATH_CROSS": SMA50 crossing below SMA200 (bearish)
    - "SUPPORT_BOUNCE": Price bouncing off SMA50 from below (bullish setup)

Strategies:
    - Bullish scenarios: ["Wheel", "Cash-Secured Put"] (CSP)
    - Bearish scenarios: ["Covered Call"]

Confidence Levels:
    - "high": Volume confirmed + momentum aligned
    - "medium": Momentum aligned OR volume confirmed (not both)
    - "low": No additional confirmation

Usage:
    from functions.detect.base import DetectorRegistry
    from functions.compute.feature_engine import FeatureSet

    registry = DetectorRegistry.get_registry()
    detector = registry.get_detector("RegimeShiftDetector")
    alert = detector.detect_safe(features)
    if alert:
        print(f"Regime shift detected: {alert.explanation['summary']}")
        print(f"Type: {alert.metrics['regime_type']}")
"""

import logging
import math
from typing import Optional, Dict, Any
from datetime import datetime

from functions.detect.base import DetectorPlugin, DetectorRegistry, AlertCandidate
from functions.compute.feature_engine import FeatureSet
from functions.config.settings import get_settings
from functions.util.logging_setup import get_logger

logger = get_logger(__name__)


class RegimeShiftDetector(DetectorPlugin):
    """
    Detects technical regime changes (moving average crossovers and support bounces).

    This detector identifies when price is near key technical levels that could signal
    a shift in trading regime. It looks for:
    1. Golden cross setups (SMA50 near crossing above SMA200)
    2. Death cross setups (SMA50 near crossing below SMA200)
    3. Support bounce setups (price near SMA50 from below)

    Attributes:
        name: "RegimeShiftDetector"
        description: Detects technical regime changes via MA crossovers and support bounces
        config_key: "detectors.regime_shift"

    Example:
        >>> detector = RegimeShiftDetector()
        >>> alert = detector.detect_safe(features)
        >>> if alert:
        ...     print(f"Regime Type: {alert.metrics['regime_type']}")
        ...     print(f"Score: {alert.score}")
        ...     print(f"Strategies: {alert.strategies}")
    """

    @property
    def name(self) -> str:
        """Get detector name."""
        return "RegimeShiftDetector"

    @property
    def description(self) -> str:
        """Get detector description."""
        return "Detects technical regime changes via MA crossovers and support bounces"

    def get_config_key(self) -> str:
        """Get configuration key for this detector."""
        return "detectors.regime_shift"

    def detect(self, features: FeatureSet) -> Optional[AlertCandidate]:
        """
        Detect technical regime changes in the feature set.

        Analysis process:
        1. Extract SMA/EMA and price data
        2. Validate data availability
        3. Check for three regime scenarios:
           - SMA golden cross (SMA50 approaching SMA200 from below)
           - SMA death cross (SMA50 approaching SMA200 from above)
           - Support bounce (price bouncing off SMA50)
        4. Apply context modifiers (momentum, volume)
        5. Return AlertCandidate if score >= 60

        Args:
            features (FeatureSet): Market data feature set containing technical indicators

        Returns:
            AlertCandidate: If regime change detected with score >= 60
            None: If conditions not met or insufficient data

        Raises:
            None - all exceptions are caught and logged by detect_safe()
        """
        logger.debug(f"Starting RegimeShiftDetector analysis for {features.ticker}")

        # =====================================================================
        # STEP 1: Extract and validate required technical indicators
        # =====================================================================
        price = features.price
        sma_20 = features.technicals.get("sma_20")
        sma_50 = features.technicals.get("sma_50")
        sma_200 = features.technicals.get("sma_200")
        ema_9 = features.technicals.get("ema_9")
        ema_21 = features.technicals.get("ema_21")
        rsi = features.technicals.get("rsi")
        volume = features.technicals.get("volume")
        volume_sma_20 = features.technicals.get("volume_sma_20")

        # Extract MACD histogram for momentum confirmation
        macd_hist = self._extract_macd_histogram(features)

        logger.debug(
            f"[{features.ticker}] Price: {price:.2f}, SMA50: {sma_50}, SMA200: {sma_200}, "
            f"MACD Hist: {macd_hist}, Volume: {volume}"
        )

        # Validate critical data
        if not self._validate_data(
            price, sma_50, sma_200, macd_hist, features.ticker
        ):
            return None

        # =====================================================================
        # STEP 2: Get configuration parameters
        # =====================================================================
        proximity_threshold = 0.03  # Default: 3%
        volume_confirmation_pct = 1.2  # Default: 20% above average

        # Try to get from AppConfig if available
        try:
            # Note: In a production system, AppConfig would come from config.yaml
            # For now, we use default thresholds
            pass
        except Exception as e:
            logger.debug(
                f"Could not load detector config: {e}, using default thresholds"
            )

        logger.debug(
            f"[{features.ticker}] Proximity threshold: {proximity_threshold*100:.1f}%, "
            f"Volume confirmation: {volume_confirmation_pct}x"
        )

        # =====================================================================
        # STEP 3: Check for regime scenarios
        # =====================================================================
        regime_info = self._detect_regime_scenario(
            price, sma_50, sma_200, proximity_threshold, features.ticker
        )

        if regime_info is None:
            logger.debug(f"[{features.ticker}] No regime scenario detected")
            return None

        regime_type, base_score = regime_info
        logger.debug(
            f"[{features.ticker}] Regime scenario detected: {regime_type}, "
            f"base_score: {base_score:.1f}"
        )

        # =====================================================================
        # STEP 4: Apply context modifiers
        # =====================================================================
        score = base_score
        modifiers_log = []

        # Modifier 1: MACD histogram momentum confirmation
        if macd_hist is not None and not math.isnan(macd_hist):
            if macd_hist > 0 and macd_hist > 0:
                # Positive histogram, momentum aligned
                score += 15
                modifiers_log.append(f"MACD positive (+15 points)")
                logger.debug(
                    f"[{features.ticker}] MACD histogram positive, added 15 points"
                )
            elif macd_hist < 0 and macd_hist < 0:
                # Negative histogram, momentum aligned
                score += 15
                modifiers_log.append(f"MACD negative (+15 points)")
                logger.debug(
                    f"[{features.ticker}] MACD histogram negative, added 15 points"
                )

        # Modifier 2: Volume confirmation (volume > confirmation_pct * avg_volume)
        if (
            volume is not None
            and volume_sma_20 is not None
            and not math.isnan(volume)
            and not math.isnan(volume_sma_20)
            and volume_sma_20 > 0
        ):
            if volume > volume_confirmation_pct * volume_sma_20:
                score += 10
                modifiers_log.append(f"Strong volume confirmation (+10 points)")
                logger.debug(
                    f"[{features.ticker}] Volume {volume} > {volume_confirmation_pct}x SMA20 "
                    f"{volume_sma_20}, added 10 points"
                )

        # Modifier 3: RSI neutral zone penalty (40-60)
        if rsi is not None and not math.isnan(rsi):
            if 40 <= rsi <= 60:
                score -= 10
                modifiers_log.append(f"RSI neutral zone (40-60) (-10 points)")
                logger.debug(f"[{features.ticker}] RSI in neutral zone, reduced by 10")

        # =====================================================================
        # STEP 5: Clamp score to [0, 100]
        # =====================================================================
        score = max(0, min(100, score))

        logger.debug(
            f"[{features.ticker}] Final score: {score:.1f} "
            f"(modifiers: {', '.join(modifiers_log) if modifiers_log else 'none'})"
        )

        # =====================================================================
        # STEP 6: Check if score passes risk gate (>= 60)
        # =====================================================================
        if score < 60:
            logger.debug(
                f"[{features.ticker}] Score {score:.1f} < risk gate (60), alert filtered"
            )
            return None

        logger.info(f"[{features.ticker}] RegimeShiftDetector alert triggered: score={score:.1f}")

        # =====================================================================
        # STEP 7: Determine confidence level
        # =====================================================================
        momentum_aligned = self._is_momentum_aligned(macd_hist)
        volume_confirmed = self._is_volume_confirmed(
            volume, volume_sma_20, volume_confirmation_pct
        )

        if momentum_aligned and volume_confirmed:
            confidence = "high"
        elif momentum_aligned or volume_confirmed:
            confidence = "medium"
        else:
            confidence = "low"

        # =====================================================================
        # STEP 8: Build metrics dictionary
        # =====================================================================
        metrics = {
            "regime_type": regime_type,
            "price": price,
            "sma_20": sma_20,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "rsi": rsi,
            "macd_hist": macd_hist,
            "volume": volume,
            "volume_sma20": volume_sma_20,
        }

        # =====================================================================
        # STEP 9: Build explanation dictionary
        # =====================================================================
        is_bullish = regime_type in ["SMA_GOLDEN_CROSS", "SUPPORT_BOUNCE"]

        explanation = {
            "summary": self._build_summary(features.ticker, regime_type),
            "reason": self._build_reason(regime_type),
            "trigger": self._build_trigger(regime_type, price, sma_50, sma_200),
            "opportunity": self._build_opportunity(regime_type, is_bullish),
        }

        # =====================================================================
        # STEP 10: Define strategies based on regime direction
        # =====================================================================
        if is_bullish:
            strategies = ["Wheel", "Cash-Secured Put"]
        else:
            strategies = ["Covered Call"]

        # =====================================================================
        # STEP 11: Create and return AlertCandidate
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
            f"[{features.ticker}] RegimeShiftDetector returning alert: "
            f"score={alert.score:.1f}, confidence={alert.confidence}, "
            f"regime={regime_type}"
        )

        return alert

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _validate_data(
        self, price: float, sma_50: Any, sma_200: Any, macd_hist: Any, ticker: str
    ) -> bool:
        """
        Validate that critical data is available.

        Args:
            price (float): Current price
            sma_50 (Any): 50-day SMA
            sma_200 (Any): 200-day SMA
            macd_hist (Any): MACD histogram
            ticker (str): Stock ticker

        Returns:
            bool: True if data is valid, False otherwise
        """
        if sma_50 is None or (isinstance(sma_50, float) and math.isnan(sma_50)):
            logger.debug(f"[{ticker}] SMA50 not available, skipping detection")
            return False

        if sma_200 is None or (isinstance(sma_200, float) and math.isnan(sma_200)):
            logger.debug(f"[{ticker}] SMA200 not available, skipping detection")
            return False

        if price <= 0:
            logger.debug(f"[{ticker}] Invalid price {price}, skipping detection")
            return False

        return True

    def _extract_macd_histogram(self, features: FeatureSet) -> Optional[float]:
        """
        Extract MACD histogram from technicals.

        MACD data can be stored as a dict with 'histogram' key.

        Args:
            features (FeatureSet): Feature set with technicals

        Returns:
            float: MACD histogram value, or None if unavailable
        """
        macd = features.technicals.get("macd")

        if macd is None:
            return None

        # MACD can be stored as dict with 'histogram' key or direct value
        if isinstance(macd, dict):
            return macd.get("histogram")
        else:
            return macd

    def _detect_regime_scenario(
        self, price: float, sma_50: float, sma_200: float, proximity_threshold: float, ticker: str
    ) -> Optional[tuple]:
        """
        Detect which regime scenario is occurring.

        Returns:
            tuple: (regime_type, base_score) or None if no scenario detected

        Scenarios:
        1. SMA_GOLDEN_CROSS: SMA50 within proximity_threshold of SMA200, and approaching from below
        2. SMA_DEATH_CROSS: SMA50 within proximity_threshold of SMA200, and approaching from above
        3. SUPPORT_BOUNCE: Price within proximity_threshold of SMA50 from below (approaching from above)
        """
        # Calculate distance between SMA50 and SMA200
        sma_diff = abs(sma_50 - sma_200)
        sma_diff_pct = sma_diff / sma_200 if sma_200 > 0 else 0

        # Calculate distance between price and SMA50
        price_diff = abs(price - sma_50)
        price_diff_pct = price_diff / sma_50 if sma_50 > 0 else 0

        logger.debug(
            f"[{ticker}] SMA diff: {sma_diff:.2f} ({sma_diff_pct*100:.2f}%), "
            f"Price-SMA50 diff: {price_diff:.2f} ({price_diff_pct*100:.2f}%)"
        )

        # Scenario 1: SMA_GOLDEN_CROSS
        # SMA50 < SMA200 (bearish) AND within proximity AND price > SMA50 (bullish setup)
        if (
            sma_50 < sma_200
            and sma_diff_pct <= proximity_threshold
            and price > sma_50
        ):
            # Base score depends on where price is
            if sma_50 < price < sma_200:
                # Price between the two MAs - strong signal
                base_score = 80
            else:
                # Price above both MAs - weaker signal
                base_score = 60
            logger.debug(
                f"[{ticker}] SMA_GOLDEN_CROSS scenario detected, base_score: {base_score}"
            )
            return ("SMA_GOLDEN_CROSS", base_score)

        # Scenario 2: SMA_DEATH_CROSS
        # SMA50 > SMA200 (bullish) AND within proximity AND price < SMA50 (bearish setup)
        if (
            sma_50 > sma_200
            and sma_diff_pct <= proximity_threshold
            and price < sma_50
        ):
            # Base score depends on where price is
            if sma_200 < price < sma_50:
                # Price between the two MAs - strong signal
                base_score = 80
            else:
                # Price below both MAs - weaker signal
                base_score = 60
            logger.debug(
                f"[{ticker}] SMA_DEATH_CROSS scenario detected, base_score: {base_score}"
            )
            return ("SMA_DEATH_CROSS", base_score)

        # Scenario 3: SUPPORT_BOUNCE
        # Price within proximity of SMA50 from above (approaching from above)
        if price >= sma_50 and price_diff_pct <= proximity_threshold:
            base_score = 70
            logger.debug(
                f"[{ticker}] SUPPORT_BOUNCE scenario detected, base_score: {base_score}"
            )
            return ("SUPPORT_BOUNCE", base_score)

        return None

    def _is_momentum_aligned(self, macd_hist: Optional[float]) -> bool:
        """
        Check if MACD momentum is aligned (positive or negative, not crossing zero).

        Args:
            macd_hist (Optional[float]): MACD histogram value

        Returns:
            bool: True if momentum is clearly aligned (not near zero)
        """
        if macd_hist is None or math.isnan(macd_hist):
            return False

        # Consider momentum aligned if clearly positive or negative (not near zero)
        return abs(macd_hist) > 0.0001

    def _is_volume_confirmed(
        self, volume: Optional[float], volume_sma_20: Optional[float], threshold: float
    ) -> bool:
        """
        Check if volume confirms the move.

        Args:
            volume (Optional[float]): Current volume
            volume_sma_20 (Optional[float]): 20-day average volume
            threshold (float): Multiplier threshold

        Returns:
            bool: True if volume is above threshold
        """
        if (
            volume is None
            or volume_sma_20 is None
            or math.isnan(volume)
            or math.isnan(volume_sma_20)
            or volume_sma_20 <= 0
        ):
            return False

        return volume > threshold * volume_sma_20

    def _build_summary(self, ticker: str, regime_type: str) -> str:
        """
        Build concise summary of the regime shift detection.

        Args:
            ticker (str): Stock ticker symbol
            regime_type (str): Type of regime detected

        Returns:
            str: 1-2 sentence summary
        """
        regime_descriptions = {
            "SMA_GOLDEN_CROSS": "bullish moving average crossover setup",
            "SMA_DEATH_CROSS": "bearish moving average crossover setup",
            "SUPPORT_BOUNCE": "bullish support bounce setup",
        }

        description = regime_descriptions.get(regime_type, "technical regime shift")
        return f"{ticker} showing {description}. Key moving averages near critical levels."

    def _build_reason(self, regime_type: str) -> str:
        """
        Build explanation of why this regime shift matters for trading.

        Args:
            regime_type (str): Type of regime detected

        Returns:
            str: Explanation of trading significance
        """
        reasons = {
            "SMA_GOLDEN_CROSS": (
                "Golden cross (SMA50 crossing above SMA200) is a classic bullish signal. "
                "When price is positioned between the two MAs, it suggests strong momentum "
                "confirmation of the uptrend initiation."
            ),
            "SMA_DEATH_CROSS": (
                "Death cross (SMA50 crossing below SMA200) is a classic bearish signal. "
                "When price is positioned between the two MAs, it suggests strong momentum "
                "confirmation of the downtrend initiation."
            ),
            "SUPPORT_BOUNCE": (
                "Price bouncing off the 50-day MA from below indicates strong support. "
                "This setup suggests institutional buying interest and potential for "
                "continued uptrend within the bullish regime."
            ),
        }

        return reasons.get(
            regime_type,
            "Technical regime shift near critical moving average levels."
        )

    def _build_trigger(
        self, regime_type: str, price: float, sma_50: float, sma_200: float
    ) -> str:
        """
        Build trigger explanation describing the specific setup.

        Args:
            regime_type (str): Type of regime
            price (float): Current price
            sma_50 (float): 50-day SMA
            sma_200 (float): 200-day SMA

        Returns:
            str: Description of what triggered the alert
        """
        if regime_type == "SMA_GOLDEN_CROSS":
            return (
                f"SMA50 ({sma_50:.2f}) approaching SMA200 ({sma_200:.2f}) from below. "
                f"Price ({price:.2f}) positioned constructively for upside breakout."
            )
        elif regime_type == "SMA_DEATH_CROSS":
            return (
                f"SMA50 ({sma_50:.2f}) approaching SMA200 ({sma_200:.2f}) from above. "
                f"Price ({price:.2f}) positioned constructively for downside breakdown."
            )
        else:  # SUPPORT_BOUNCE
            return (
                f"Price ({price:.2f}) bouncing near SMA50 support ({sma_50:.2f}). "
                f"Strong support zone indicates potential for continuation higher."
            )

    def _build_opportunity(self, regime_type: str, is_bullish: bool) -> str:
        """
        Build explanation of the trading opportunity.

        Args:
            regime_type (str): Type of regime
            is_bullish (bool): Whether the regime is bullish

        Returns:
            str: Explanation of the opportunity
        """
        if is_bullish:
            return (
                "Bullish regime setup favors directional call buying or covered puts. "
                "Consider strategies that benefit from upside participation with lower cost."
            )
        else:
            return (
                "Bearish regime setup favors defined-risk call selling or put spreads. "
                "Consider strategies that collect premium in downtrending environment."
            )


# ============================================================================
# PLUGIN REGISTRATION
# ============================================================================

# Register the detector at import time
try:
    DetectorRegistry.register(RegimeShiftDetector)
    logger.debug("RegimeShiftDetector registered successfully")
except Exception as e:
    logger.error(f"Failed to register RegimeShiftDetector: {e}", exc_info=True)
