"""
Alert scoring module for applying portfolio-level adjustments to detector scores.

This module provides the AlertScorer class that takes detector output (AlertCandidate)
and applies portfolio-level bonuses and penalties based on:
- Investment thesis alignment
- Liquidity metrics
- Earnings proximity
- Technical alignment (MACD)
- Volatility regime matching

The scorer transforms raw detector scores (0-100) into portfolio-adjusted scores
that reflect additional context beyond what individual detectors can evaluate.

Usage:
    from functions.config.loader import get_config
    from functions.scoring.scorer import AlertScorer
    from functions.detect.base import AlertCandidate
    from functions.compute.feature_engine import FeatureSet

    config = get_config()
    scorer = AlertScorer(config)

    # Apply portfolio-level scoring adjustments
    adjusted_score = scorer.score_alert(alert, ticker="AAPL", features=features)
    print(f"Original: {alert.score}, Adjusted: {adjusted_score}")

Configuration Requirements:
    - config.theses: Dictionary of trading theses (keyed by ticker symbol)
      Each thesis should have at least a first sentence for logging
    - config.scan.liquidity: Liquidity filter configuration
    - Features should include earnings_info, liquidity metrics, technicals

Score Adjustments:
    - Thesis alignment: +20 if ticker has investment thesis
    - Liquidity penalty: -15 if bid-ask spread > 3% OR volume < threshold
    - Earnings proximity: -10 if earnings within 3 days (0-3 days)
    - Technical alignment: +10 if MACD histogram aligns with strategy
    - Volatility regime: +5 if current vol regime matches signal expectation

    Final score is clamped to [0, 100]
"""

from typing import Optional, Dict, Any
from datetime import datetime, timezone

from functions.util.logging_setup import get_logger
from functions.config.models import AppConfig
from functions.detect.base import AlertCandidate
from functions.compute.feature_engine import FeatureSet

logger = get_logger(__name__)


class AlertScorer:
    """
    Applies portfolio-level scoring adjustments to detector base scores.

    This class enhances raw detector scores with additional context that requires
    portfolio-level information, such as:
    - Whether a ticker aligns with portfolio investment theses
    - Whether liquidity is sufficient for trading
    - Proximity to earnings (to avoid IV crush/expansion surprises)
    - Technical confirmation via MACD
    - Volatility regime alignment

    The scorer is initialized with AppConfig containing threshold values and
    thesis definitions, then used to adjust individual alerts through score_alert().

    Attributes:
        config (AppConfig): Application configuration with thresholds and theses
        logger: Configured logger instance for decision tracking
    """

    def __init__(self, config: AppConfig) -> None:
        """
        Initialize AlertScorer with configuration.

        Stores configuration reference for threshold values and thesis lookups.
        Initializes logger for decision tracking.

        Args:
            config (AppConfig): Application configuration containing:
                - theses: Dict[str, Dict] of investment theses keyed by ticker
                - scan.liquidity: Liquidity filter configuration
                - Other threshold values

        Raises:
            TypeError: If config is not an AppConfig instance
            ValueError: If config is missing required fields
        """
        if not isinstance(config, AppConfig):
            raise TypeError(
                f"config must be AppConfig instance, got {type(config).__name__}"
            )

        self.config = config
        logger.info(
            f"Initialized AlertScorer with {len(getattr(config, 'theses', {}))} theses"
        )

    def score_alert(
        self, alert_candidate: AlertCandidate, ticker: str, features: FeatureSet
    ) -> float:
        """
        Apply portfolio-level scoring adjustments to detector base score.

        Takes a detector's base score and applies bonuses/penalties based on:
        1. Thesis alignment: +20 if ticker has investment thesis
        2. Liquidity check: -15 if bid-ask spread > 3% OR volume < threshold
        3. Earnings proximity: -10 if earnings within 3 days
        4. Technical alignment: +10 if MACD histogram aligns with strategy
        5. Volatility regime: +5 if current vol regime matches signal expectation

        Final score is clamped to [0, 100] and logged at INFO level with details.

        Args:
            alert_candidate (AlertCandidate): Detector output with base score
            ticker (str): Stock ticker symbol (e.g., "AAPL")
            features (FeatureSet): Comprehensive feature set with market metrics

        Returns:
            float: Adjusted score between 0.0 and 100.0

        Raises:
            TypeError: If alert_candidate or features have wrong types
            ValueError: If ticker is invalid

        Example:
            >>> scorer = AlertScorer(config)
            >>> adjusted = scorer.score_alert(alert, "AAPL", features)
            >>> print(f"Score: {adjusted}")
            Score: 78.5
        """
        # Validate inputs
        if not isinstance(alert_candidate, AlertCandidate):
            raise TypeError(
                f"alert_candidate must be AlertCandidate, got {type(alert_candidate).__name__}"
            )
        if not isinstance(features, FeatureSet):
            raise TypeError(
                f"features must be FeatureSet, got {type(features).__name__}"
            )
        if not ticker or not isinstance(ticker, str):
            raise ValueError(f"ticker must be non-empty string, got {ticker}")

        ticker = ticker.upper()

        # Start with detector's base score
        base_score = alert_candidate.score
        adjusted_score = float(base_score)

        logger.debug(
            f"Starting score adjustment for {ticker} (detector: {alert_candidate.detector_name}, "
            f"base: {base_score})"
        )

        # Apply adjustments in order
        try:
            # 1. Apply thesis alignment bonus
            adjusted_score = self.apply_thesis_bonus(adjusted_score, ticker)

            # 2. Apply liquidity penalty
            adjusted_score = self.apply_liquidity_penalty(adjusted_score, features)

            # 3. Apply earnings proximity penalty
            adjusted_score = self.apply_earnings_penalty(adjusted_score, features)

            # 4. Apply technical alignment bonus (MACD)
            adjusted_score = self._apply_technical_bonus(adjusted_score, features)

            # 5. Apply volatility regime bonus
            adjusted_score = self._apply_volatility_bonus(adjusted_score, features)

            # Clamp final score to [0, 100]
            final_score = max(0.0, min(100.0, adjusted_score))

            # Log decision with details
            adjustments = adjusted_score - base_score
            logger.info(
                f"Alert scoring complete: ticker={ticker}, detector={alert_candidate.detector_name}, "
                f"base={base_score:.1f}, adjusted={final_score:.1f}, "
                f"change={adjustments:+.1f}, confidence={alert_candidate.confidence}"
            )

            return final_score

        except Exception as e:
            logger.error(
                f"Error during score adjustment for {ticker}: {e}", exc_info=True
            )
            # Return clamped base score if error occurs
            return max(0.0, min(100.0, base_score))

    def apply_thesis_bonus(self, alert_score: float, ticker: str) -> float:
        """
        Check if ticker has investment thesis and apply +20 bonus.

        Looks up ticker in config.theses dictionary. If found, adds 20 points
        to the score. Otherwise returns score unchanged.

        This bonus reflects the portfolio's strategic alignment with the opportunity.

        Args:
            alert_score (float): Current alert score before adjustment
            ticker (str): Stock ticker symbol (uppercase)

        Returns:
            float: Score with +20 bonus if thesis exists, otherwise unchanged

        Example:
            >>> if config has thesis for AAPL:
            ...     score = scorer.apply_thesis_bonus(65.0, "AAPL")
            ...     print(score)  # 85.0
            >>> else:
            ...     score = scorer.apply_thesis_bonus(65.0, "AAPL")
            ...     print(score)  # 65.0
        """
        try:
            # Get theses dictionary from config (may not exist if no theses loaded)
            theses = getattr(self.config, "theses", {})

            if not isinstance(theses, dict):
                logger.warning(
                    f"config.theses is not a dict, got {type(theses).__name__}"
                )
                return alert_score

            ticker_upper = ticker.upper()

            # Check if ticker has a thesis
            if ticker_upper in theses:
                thesis_summary = self._get_thesis_summary(ticker_upper)
                adjusted_score = alert_score + 20.0
                logger.debug(
                    f"Thesis alignment bonus applied to {ticker_upper}: "
                    f"{alert_score:.1f} -> {adjusted_score:.1f} | Thesis: {thesis_summary}"
                )
                return adjusted_score
            else:
                logger.debug(f"No thesis found for {ticker_upper}")
                return alert_score

        except Exception as e:
            logger.warning(
                f"Error applying thesis bonus for {ticker}: {e}", exc_info=True
            )
            return alert_score

    def apply_liquidity_penalty(
        self, alert_score: float, features: FeatureSet
    ) -> float:
        """
        Apply -15 penalty if bid-ask spread > 3% OR volume < threshold.

        Extracts liquidity metrics from features.liquidity and checks:
        - bid_ask_spread_pct > 3.0
        - atm_volume < config threshold

        If either condition is met, subtracts 15 points from score.

        This penalty ensures we avoid illiquid opportunities that are risky to trade.

        Args:
            alert_score (float): Current alert score before adjustment
            features (FeatureSet): Features containing liquidity data

        Returns:
            float: Score with -15 penalty if liquidity insufficient, otherwise unchanged

        Example:
            >>> features.liquidity = {"spread_pct": 5.0}  # > 3%
            >>> score = scorer.apply_liquidity_penalty(75.0, features)
            >>> print(score)  # 60.0

        Note:
            Returns unchanged score and logs warning if liquidity data is missing.
        """
        try:
            liquidity = features.liquidity

            if not isinstance(liquidity, dict):
                logger.warning(
                    f"features.liquidity is not a dict, got {type(liquidity).__name__}"
                )
                return alert_score

            # Extract metrics with safe defaults
            bid_ask_spread_pct = liquidity.get("spread_pct", 0.0)
            atm_volume = liquidity.get("atm_volume", 0)

            # Get volume threshold from config
            volume_threshold = getattr(
                self.config.scan.liquidity, "min_option_volume", 10
            )

            # Check liquidity conditions
            if bid_ask_spread_pct > 3.0 or atm_volume < volume_threshold:
                adjusted_score = alert_score - 15.0
                reason = []
                if bid_ask_spread_pct > 3.0:
                    reason.append(f"spread {bid_ask_spread_pct:.1f}% > 3%")
                if atm_volume < volume_threshold:
                    reason.append(f"volume {atm_volume} < {volume_threshold}")

                logger.debug(
                    f"Liquidity penalty applied: {alert_score:.1f} -> {adjusted_score:.1f} | "
                    f"Reason: {', '.join(reason)}"
                )
                return adjusted_score
            else:
                logger.debug(
                    f"Liquidity check passed: spread={bid_ask_spread_pct:.1f}%, "
                    f"volume={atm_volume}"
                )
                return alert_score

        except Exception as e:
            logger.warning(
                f"Error applying liquidity penalty: {e}", exc_info=True
            )
            return alert_score

    def apply_earnings_penalty(
        self, alert_score: float, features: FeatureSet
    ) -> float:
        """
        Apply -10 penalty if earnings within 3 days (0 <= days <= 3).

        Extracts days_to_earnings from features.earnings. If the value exists
        and falls within the 0-3 day window, subtracts 10 points.

        This penalty reflects the high IV risk around earnings announcements,
        where surprises can cause sharp directional moves or IV crush.

        Args:
            alert_score (float): Current alert score before adjustment
            features (FeatureSet): Features containing earnings_info

        Returns:
            float: Score with -10 penalty if earnings within 3 days, otherwise unchanged

        Example:
            >>> features.earnings = {"days_to_earnings": 2}  # Within 3 days
            >>> score = scorer.apply_earnings_penalty(75.0, features)
            >>> print(score)  # 65.0

        Note:
            Returns unchanged score and logs warning if earnings data is missing.
        """
        try:
            earnings = features.earnings

            if not isinstance(earnings, dict):
                logger.warning(
                    f"features.earnings is not a dict, got {type(earnings).__name__}"
                )
                return alert_score

            days_to_earnings = earnings.get("days_to_earnings")

            # Check if days_to_earnings is valid and within penalty window
            if days_to_earnings is not None:
                if isinstance(days_to_earnings, (int, float)) and 0 <= days_to_earnings <= 3:
                    adjusted_score = alert_score - 10.0
                    logger.debug(
                        f"Earnings penalty applied: {alert_score:.1f} -> {adjusted_score:.1f} | "
                        f"Days to earnings: {days_to_earnings}"
                    )
                    return adjusted_score
                else:
                    logger.debug(
                        f"Earnings check: {days_to_earnings} days (outside penalty window)"
                    )
            else:
                logger.debug("Earnings data not available for penalty check")

            return alert_score

        except Exception as e:
            logger.warning(
                f"Error applying earnings penalty: {e}", exc_info=True
            )
            return alert_score

    def _apply_technical_bonus(
        self, alert_score: float, features: FeatureSet
    ) -> float:
        """
        Apply +10 bonus if MACD histogram aligns with strategy direction.

        Checks if MACD histogram exists in features.technicals and has the
        expected sign (positive for bullish strategies, negative for bearish).

        Currently assumes bullish bias (MACD > 0). Future enhancement: pass
        strategy direction as parameter.

        Args:
            alert_score (float): Current alert score before adjustment
            features (FeatureSet): Features containing MACD data

        Returns:
            float: Score with +10 bonus if MACD aligns, otherwise unchanged

        Example:
            >>> features.technicals = {"macd": 0.5}  # Positive = bullish
            >>> score = scorer._apply_technical_bonus(65.0, features)
            >>> print(score)  # 75.0
        """
        try:
            technicals = features.technicals

            if not isinstance(technicals, dict):
                logger.debug(
                    f"features.technicals not available, skipping technical bonus"
                )
                return alert_score

            macd = technicals.get("macd")

            if macd is not None and isinstance(macd, (int, float)):
                # For now assume bullish bias: positive MACD = alignment
                if macd > 0:
                    adjusted_score = alert_score + 10.0
                    logger.debug(
                        f"Technical bonus applied: {alert_score:.1f} -> {adjusted_score:.1f} | "
                        f"MACD: {macd:.4f}"
                    )
                    return adjusted_score
                else:
                    logger.debug(
                        f"Technical check: MACD {macd:.4f} negative (no alignment)"
                    )
            else:
                logger.debug("MACD data not available for technical bonus")

            return alert_score

        except Exception as e:
            logger.warning(
                f"Error applying technical bonus: {e}", exc_info=True
            )
            return alert_score

    def _apply_volatility_bonus(
        self, alert_score: float, features: FeatureSet
    ) -> float:
        """
        Apply +5 bonus if current volatility regime matches signal expectation.

        Checks if volatility trend exists in features.volatility and is in
        expected state for the alert.

        Currently checks if vol_trend is "increasing" (bullish expectation).
        Future enhancement: pass signal direction to refine this logic.

        Args:
            alert_score (float): Current alert score before adjustment
            features (FeatureSet): Features containing volatility regime data

        Returns:
            float: Score with +5 bonus if vol regime matches, otherwise unchanged

        Example:
            >>> features.volatility = {"vol_trend": "increasing"}
            >>> score = scorer._apply_volatility_bonus(65.0, features)
            >>> print(score)  # 70.0
        """
        try:
            volatility = features.volatility

            if not isinstance(volatility, dict):
                logger.debug(
                    f"features.volatility not available, skipping volatility bonus"
                )
                return alert_score

            vol_trend = volatility.get("vol_trend")

            if vol_trend is not None and isinstance(vol_trend, str):
                # For now assume bullish bias: increasing vol = positive
                if vol_trend.lower() in ["increasing", "rising", "up"]:
                    adjusted_score = alert_score + 5.0
                    logger.debug(
                        f"Volatility bonus applied: {alert_score:.1f} -> {adjusted_score:.1f} | "
                        f"Vol trend: {vol_trend}"
                    )
                    return adjusted_score
                else:
                    logger.debug(
                        f"Volatility check: trend {vol_trend} does not match expectation"
                    )
            else:
                logger.debug("Volatility trend data not available for bonus")

            return alert_score

        except Exception as e:
            logger.warning(
                f"Error applying volatility bonus: {e}", exc_info=True
            )
            return alert_score

    def _get_thesis_summary(self, ticker: str) -> Optional[str]:
        """
        Extract first sentence of thesis for logging.

        Looks up ticker in config.theses and extracts the first sentence from
        the thesis text. Returns None if thesis not found or doesn't contain text.

        Used for informative debug/info logging about which thesis triggered bonus.

        Args:
            ticker (str): Stock ticker symbol (uppercase)

        Returns:
            Optional[str]: First sentence of thesis, or None if not found

        Example:
            >>> # If AAPL thesis starts with "Apple has strong secular growth..."
            >>> summary = scorer._get_thesis_summary("AAPL")
            >>> print(summary)
            "Apple has strong secular growth..."

        Note:
            Extracts first sentence by looking for period followed by space.
            Returns full text if no period found.
        """
        try:
            theses = getattr(self.config, "theses", {})

            if not isinstance(theses, dict):
                return None

            ticker_upper = ticker.upper()

            if ticker_upper not in theses:
                return None

            thesis_data = theses[ticker_upper]

            # Handle different thesis data structures
            if isinstance(thesis_data, dict):
                # Try to find text in common keys
                text = (
                    thesis_data.get("text")
                    or thesis_data.get("description")
                    or thesis_data.get("summary")
                    or ""
                )
            elif isinstance(thesis_data, str):
                text = thesis_data
            else:
                return None

            if not text:
                return None

            # Extract first sentence (up to first period followed by space)
            sentence_end = text.find(". ")
            if sentence_end > 0:
                return text[: sentence_end + 1]
            else:
                # No period found, return first 100 chars
                return text[:100] if len(text) > 100 else text

        except Exception as e:
            logger.warning(
                f"Error extracting thesis summary for {ticker}: {e}", exc_info=True
            )
            return None
