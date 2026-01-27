"""
Template-Based Explanation Generator for trading alerts.

This module provides deterministic, template-based explanations for trading alerts
without requiring an LLM. Each detector type has dedicated helper methods that
generate consistent, data-driven explanations based on market features and metrics.

The ExplanationGenerator class takes an AlertCandidate from a detector and enriches
it with comprehensive explanation data suitable for dashboards and trading decisions.

Core Components:
    - ExplanationGenerator: Main class orchestrating explanation generation
    - Detector-specific helper methods: _explain_low_iv, _explain_rich_premium, etc.
    - Utility methods: _format_metric, _get_metric_value

Design:
    - Deterministic: No randomness or LLM calls
    - Template-based: Each detector has predefined explanation structure
    - Robust: Gracefully handles missing data by omitting relevant sections
    - UTC timestamps: All timestamps in UTC for consistency

Usage:
    from functions.explain.template_explain import ExplanationGenerator
    from functions.config.models import AppConfig
    from functions.detect.base import AlertCandidate
    from functions.compute.feature_engine import FeatureSet

    # Initialize generator
    generator = ExplanationGenerator(config)

    # Generate enriched explanation
    explanation = generator.generate_explanation(
        alert=alert_candidate,
        ticker="AAPL",
        features=feature_set
    )

    # Use explanation in dashboard/UI
    print(explanation["summary"])
    print(f"Timeframe: {explanation['timeframe']}")
    print(f"Risk factors: {explanation['risk_factors']}")
"""

import logging
import math
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from functions.util.logging_setup import get_logger
from functions.config.models import AppConfig
from functions.detect.base import AlertCandidate
from functions.compute.feature_engine import FeatureSet

logger = get_logger(__name__)


# ============================================================================
# EXPLANATION GENERATOR CLASS
# ============================================================================


class ExplanationGenerator:
    """
    Generates template-based explanations for trading alerts.

    This class takes AlertCandidate objects from detectors and enriches them
    with comprehensive explanation data including summaries, rationale, key metrics,
    risk factors, opportunities, and monitoring points.

    All explanations are deterministic (no randomness) and don't require LLM calls.
    Missing data is handled gracefully by omitting relevant sections.

    Attributes:
        config (AppConfig): Application configuration for explanation templates
        logger: Instance logger for this generator

    Example:
        >>> gen = ExplanationGenerator(config)
        >>> explanation = gen.generate_explanation(alert, "AAPL", features)
        >>> print(explanation["summary"])
        >>> print(f"Opportunities: {explanation['opportunities']}")
    """

    def __init__(self, config: AppConfig) -> None:
        """
        Initialize ExplanationGenerator.

        Args:
            config (AppConfig): Application configuration containing explanation
                templates and settings

        Raises:
            TypeError: If config is not an AppConfig instance
        """
        if not isinstance(config, AppConfig):
            raise TypeError(
                f"config must be AppConfig instance, got {type(config).__name__}"
            )

        self.config = config
        logger.info("ExplanationGenerator initialized")

    def generate_explanation(
        self, alert: AlertCandidate, ticker: str, features: FeatureSet
    ) -> Dict[str, Any]:
        """
        Generate enriched explanation for an alert.

        This is the main entry point. It routes to detector-specific helpers
        based on alert.detector_name and returns a complete explanation dict.

        Args:
            alert (AlertCandidate): The alert to explain (from detector)
            ticker (str): Stock ticker symbol (e.g., "AAPL")
            features (FeatureSet): Market data features with IV, technicals, etc.

        Returns:
            Dict with keys:
                - summary (str): 1-2 sentence explanation
                - rationale (str): Why this matters for trading
                - key_metrics (List[Dict]): List of {metric, value, unit}
                - directional_bias (str): "bullish", "bearish", or "neutral"
                - risk_factors (List[str]): Risk factors to consider
                - opportunities (List[str]): Trading opportunities
                - timeframe (str): Suggested holding period
                - next_monitoring_points (List[str]): What to watch
                - timestamp (str): UTC timestamp of explanation

        Raises:
            ValueError: If alert.detector_name is not recognized
            TypeError: If inputs have wrong types
        """
        if not isinstance(alert, AlertCandidate):
            raise TypeError(
                f"alert must be AlertCandidate, got {type(alert).__name__}"
            )
        if not isinstance(ticker, str) or not ticker.strip():
            raise TypeError(f"ticker must be non-empty string, got {ticker}")
        if not isinstance(features, FeatureSet):
            raise TypeError(
                f"features must be FeatureSet, got {type(features).__name__}"
            )

        logger.debug(
            f"Generating explanation for {alert.detector_name} alert on {ticker}"
        )

        # Route to detector-specific helper based on detector_name
        detector_name = alert.detector_name

        if detector_name == "LowIVDetector":
            explanation = self._explain_low_iv(alert, ticker, features)
        elif detector_name == "RichPremiumDetector":
            explanation = self._explain_rich_premium(alert, ticker, features)
        elif detector_name == "EarningsCrushDetector":
            explanation = self._explain_earnings_crush(alert, ticker, features)
        elif detector_name == "TermKinkDetector":
            explanation = self._explain_term_kink(alert, ticker, features)
        elif detector_name == "SkewAnomalyDetector":
            explanation = self._explain_skew_anomaly(alert, ticker, features)
        elif detector_name == "RegimeShiftDetector":
            explanation = self._explain_regime_shift(alert, ticker, features)
        else:
            logger.warning(
                f"Unknown detector: {detector_name}, using generic explanation"
            )
            explanation = self._explain_generic(alert, ticker, features)

        # Add timestamp
        explanation["timestamp"] = datetime.now(timezone.utc).isoformat() + "Z"

        logger.info(
            f"Generated explanation for {detector_name} on {ticker} "
            f"with {len(explanation.get('risk_factors', []))} risk factors"
        )

        return explanation

    # =========================================================================
    # DETECTOR-SPECIFIC EXPLANATION METHODS
    # =========================================================================

    def _explain_low_iv(
        self, alert: AlertCandidate, ticker: str, features: FeatureSet
    ) -> Dict[str, Any]:
        """
        Generate explanation for low IV detection.

        Low IV indicates that options are trading at historically compressed premiums,
        creating premium-selling opportunities. This is ideal for income strategies
        like covered calls, cash-secured puts, and spreads.

        Args:
            alert (AlertCandidate): The low IV alert
            ticker (str): Stock ticker
            features (FeatureSet): Market features with IV metrics

        Returns:
            Explanation dict with low IV context
        """
        iv_percentile = alert.metrics.get("iv_percentile", 0)
        iv_front = alert.metrics.get("iv_front")

        explanation = {
            "summary": (
                f"{ticker} implied volatility at {iv_percentile:.0f}th percentile. "
                f"Historically compressed premium environment for selling strategies."
            ),
            "rationale": (
                "Low implied volatility (IV) means option premiums are trading at "
                "historically reduced levels. This creates attractive opportunities for "
                "premium-selling strategies (cash-secured puts, covered calls, spreads) "
                "where you can collect premium with favorable risk/reward ratios. "
                "The compressed premium compensates for lower probability of large moves."
            ),
            "key_metrics": [
                self._format_metric("IV Percentile", iv_percentile, "%"),
                self._format_metric("IV Level", iv_front, None) if iv_front else {},
                self._format_metric(
                    "IV Rank", alert.metrics.get("iv_vs_hv", 0), "ratio"
                ),
                self._format_metric("Score", alert.score, "points"),
            ],
            "directional_bias": "neutral",
            "risk_factors": [
                "IV can compress further (theta decay accelerates on short premium positions)",
                "Low IV may indicate absent catalysts or complacency (can change quickly)",
                "IV compression thesis may not pan out if market reprices higher",
                "Directional moves against position can exceed expected range",
            ],
            "opportunities": [
                "Sell cash-secured puts at support levels (income generation)",
                "Sell covered calls for income on existing longs",
                "Calendar spreads: sell front month, buy back month IV",
                "Iron condors at wide strike widths (low IV = cheaper credit spreads)",
                "Short straddles at ATM (neutral directional bias)",
            ],
            "timeframe": "2-4 weeks (collect theta decay before earnings/events)",
            "next_monitoring_points": [
                "Watch for IV expansion (exit premium sells early if IV rises)",
                "Monitor technical support levels (where you sold puts)",
                "Track days to expiration (take profits at 50% max if risk remains)",
                "Watch for earnings announcements (IV crush risk before earnings)",
                "Track overall market volatility (VIX levels, sector rotation)",
            ],
        }

        return explanation

    def _explain_rich_premium(
        self, alert: AlertCandidate, ticker: str, features: FeatureSet
    ) -> Dict[str, Any]:
        """
        Generate explanation for rich premium detection.

        Rich premium (high IV) indicates elevated option prices, creating opportunities
        for premium buying strategies. This is ideal for directional trades with
        defined risk through spreads.

        Args:
            alert (AlertCandidate): The rich premium alert
            ticker (str): Stock ticker
            features (FeatureSet): Market features with IV metrics

        Returns:
            Explanation dict with rich premium context
        """
        iv_percentile = alert.metrics.get("iv_percentile", 0)
        iv_front = alert.metrics.get("iv_front")

        explanation = {
            "summary": (
                f"{ticker} implied volatility at {iv_percentile:.0f}th percentile. "
                f"Elevated premium environment favoring premium-buying strategies."
            ),
            "rationale": (
                "High implied volatility (IV) means option premiums are trading at "
                "historically elevated levels, indicating market uncertainty or expected "
                "catalysts. This creates opportunities for premium-buying strategies "
                "(long calls, long puts, spreads) where you benefit from directional "
                "moves. The high premium pricing reflects genuine expected volatility."
            ),
            "key_metrics": [
                self._format_metric("IV Percentile", iv_percentile, "%"),
                self._format_metric("IV Level", iv_front, None) if iv_front else {},
                self._format_metric(
                    "IV Rank", alert.metrics.get("iv_vs_hv", 0), "ratio"
                ),
                self._format_metric("Score", alert.score, "points"),
            ],
            "directional_bias": "bullish or bearish (depends on position direction)",
            "risk_factors": [
                "Position assigned if incorrect directional bet (put assignment, call assignment)",
                "IV can remain high longer than expected (IV crush timing is uncertain)",
                "IV crush (sudden drop) can hurt long premium positions significantly",
                "Theta decay works against long premium buyers (time decay cost)",
                "Underlying may not move as much as IV implies (overestimated move)",
            ],
            "opportunities": [
                "Bull call spreads (directional up, defined risk via short call)",
                "Bear put spreads (directional down, defined risk via short put)",
                "Bull put spreads (directional up, defined risk via short call)",
                "Directional spreads with lower breakeven due to high premiums",
                "Long calls/puts if expecting directional breakout soon",
            ],
            "timeframe": "1-3 weeks (capture IV crush before expiration)",
            "next_monitoring_points": [
                "Watch for IV collapse (exit if IV drops faster than realized move)",
                "Monitor price action near strike prices (breakeven points)",
                "Track theta decay (monitor P&L daily, especially near expiration)",
                "Watch for catalyst events (earnings, FOMC, other catalysts)",
                "Monitor implied move vs actual daily ranges (validate IV thesis)",
            ],
        }

        return explanation

    def _explain_earnings_crush(
        self, alert: AlertCandidate, ticker: str, features: FeatureSet
    ) -> Dict[str, Any]:
        """
        Generate explanation for earnings crush detection.

        Earnings events cause IV to spike in advance and crush after the announcement.
        This creates opportunities for IV selling strategies that capitalize on the
        IV crush, but with timing risk around the earnings date.

        Args:
            alert (AlertCandidate): The earnings crush alert
            ticker (str): Stock ticker
            features (FeatureSet): Market features with earnings data

        Returns:
            Explanation dict with earnings crush context
        """
        days_to_earnings = self._get_metric_value(features, "earnings.days_to_earnings")
        iv_front = alert.metrics.get("iv_front")

        explanation = {
            "summary": (
                f"{ticker} approaching earnings with elevated IV "
                f"({days_to_earnings:.0f} days to earnings). "
                f"IV crush opportunity post-earnings."
            ),
            "rationale": (
                "Earnings events drive IV expansion in the days before announcement. "
                "This creates two strategies: (1) Sell premium into the event if expecting "
                "mean reversion after, or (2) Buy spreads to benefit from directional move "
                "if earnings catalyst is known. Post-earnings, IV typically crushes rapidly, "
                "hurting long premium positions but benefiting short premium sellers."
            ),
            "key_metrics": [
                self._format_metric("Days to Earnings", days_to_earnings, "days"),
                self._format_metric("IV Level", iv_front, None) if iv_front else {},
                self._format_metric("IV Percentile", alert.metrics.get("iv_percentile", 0), "%"),
                self._format_metric("Score", alert.score, "points"),
            ],
            "directional_bias": "neutral (unless post-earnings direction is known)",
            "risk_factors": [
                "Post-earnings gap moves can be large and unpredictable (surprise impact)",
                "IV crush timing varies (doesn't always happen immediately after)",
                "Short premium positions face risk of wide gap move before/after earnings",
                "IV may stay elevated if earnings miss leads to guidance issues",
                "Liquidity can drop significantly immediately after earnings announcement",
            ],
            "opportunities": [
                "Short straddles: sell both calls and puts (neutral to small moves)",
                "Short iron condors: defined risk, benefit from IV crush if direction correct",
                "Short premium spreads: take profit on premiums if market is directional",
                "Short calendar spreads: exploit pre-earnings IV elevation",
                "Wait-and-see directional trades post-earnings with better entry points",
            ],
            "timeframe": (
                "1-7 days pre-earnings for IV selling, then post-earnings management"
            ),
            "next_monitoring_points": [
                "Watch earnings announcement time (pre-market, market open, after hours)",
                "Monitor IV changes (crush timing relative to earnings call)",
                "Track price gaps at market open if earnings after hours",
                "Watch realized volatility post-earnings vs pre-earnings IV expectations",
                "Monitor guidance changes (future earnings implications)",
                "Track stock reactions to quarterly guidance/management commentary",
            ],
        }

        return explanation

    def _explain_term_kink(
        self, alert: AlertCandidate, ticker: str, features: FeatureSet
    ) -> Dict[str, Any]:
        """
        Generate explanation for term structure kink detection.

        Term structure anomalies (abnormal contango/backwardation patterns) indicate
        market dislocations or specific cost-of-carry dynamics. Calendar spreads
        can exploit these inefficiencies.

        Args:
            alert (AlertCandidate): The term structure alert
            ticker (str): Stock ticker
            features (FeatureSet): Market features with term structure data

        Returns:
            Explanation dict with term structure context
        """
        iv_ratio = self._get_metric_value(features, "term_structure.iv_ratio")
        iv_diff = self._get_metric_value(features, "term_structure.iv_diff")

        explanation = {
            "summary": (
                f"{ticker} term structure abnormal "
                f"(IV ratio: {iv_ratio:.2f} vs normal 0.95-1.05). "
                f"Calendar spread opportunity detected."
            ),
            "rationale": (
                "Option IV term structure normally slopes slightly upward (backwardation) "
                "due to cost of carry and volatility term premium. Abnormal patterns "
                "(steep backwardation, flattening, or inversion) indicate market dislocations "
                "or specific catalysts. Calendar spreads can exploit these by selling near-term "
                "IV and buying longer-term IV (or vice versa) to normalize the structure."
            ),
            "key_metrics": [
                self._format_metric("IV Ratio (Front/Back)", iv_ratio, "ratio"),
                self._format_metric("IV Diff (Front-Back)", iv_diff, "points"),
                self._format_metric(
                    "Front IV", alert.metrics.get("iv_front"), None
                ) if alert.metrics.get("iv_front") else {},
                self._format_metric("Score", alert.score, "points"),
            ],
            "directional_bias": "neutral (term structure agnostic to direction)",
            "risk_factors": [
                "Term structure can normalize quickly (mean reversion of the kink)",
                "Cost of carry (dividends, borrow rates) can change unexpectedly",
                "Earnings or catalysts between expirations can break relationships",
                "Liquidity differences between front/back can make spreads hard to execute",
                "Roll risk (short side expires while long side still profitable)",
            ],
            "opportunities": [
                "Calendar spreads: sell front month IV, buy back month IV (if front elevated)",
                "Reverse calendar spreads if back IV is elevated relative to front",
                "Diagonal spreads combining calendar + directional bias",
                "Spread adjustments as term structure normalizes back to typical levels",
            ],
            "timeframe": "3-6 weeks (capture term structure normalization)",
            "next_monitoring_points": [
                "Watch IV ratio as time passes (structure should normalize)",
                "Track front month IV decay (theta)",
                "Monitor back month IV changes (independent movement)",
                "Watch for earnings announcements between expirations",
                "Monitor dividend announcements (affects forward premiums)",
                "Track cost-of-carry indicators (repo rates, dividend dates)",
            ],
        }

        return explanation

    def _explain_skew_anomaly(
        self, alert: AlertCandidate, ticker: str, features: FeatureSet
    ) -> Dict[str, Any]:
        """
        Generate explanation for skew anomaly detection.

        Put/call skew imbalances indicate directional conviction in the options market.
        Elevated put skew suggests bearish sentiment; elevated call skew suggests bullish.
        These can be traded with directional spreads.

        Args:
            alert (AlertCandidate): The skew anomaly alert
            ticker (str): Stock ticker
            features (FeatureSet): Market features with options data

        Returns:
            Explanation dict with skew anomaly context
        """
        explanation = {
            "summary": (
                f"{ticker} put/call skew imbalanced. "
                f"Market showing directional conviction signal. "
                f"Opportunity for directional spread strategies."
            ),
            "rationale": (
                "Put/call skew measures the volatility difference between puts and calls "
                "at same strikes. Elevated put skew (puts more expensive) indicates bearish "
                "sentiment; elevated call skew (calls more expensive) indicates bullish. "
                "These skew anomalies often persist and can be traded with spreads that "
                "benefit from the directional bias implied by the skew."
            ),
            "key_metrics": [
                self._format_metric("Score", alert.score, "points"),
                self._format_metric(
                    "Put/Call IV Ratio", alert.metrics.get("put_call_iv_ratio", 0), "ratio"
                ),
                self._format_metric(
                    "Directional Signal", alert.metrics.get("directional_signal"), None
                ) if alert.metrics.get("directional_signal") else {},
            ],
            "directional_bias": alert.metrics.get("directional_signal", "bullish/bearish"),
            "risk_factors": [
                "Skew can reverse quickly if directional thesis changes",
                "Market can prove wrong on skew-implied direction (no guarantee)",
                "Execution risk on skew-dependent spreads (hard to leg into)",
                "Earnings or catalysts can invert skew direction overnight",
                "IV crush can hurt long premium positions even if direction right",
            ],
            "opportunities": [
                "Bull call spreads if call skew (bullish bias)",
                "Bull put spreads if put skew elevated (market expects downside protection)",
                "Bear call spreads if put skew (bearish bias)",
                "Bear put spreads if call skew (bullish bias but can fade)",
                "Directional spreads weighted toward skew-implied side",
            ],
            "timeframe": "1-3 weeks (until skew normalizes)",
            "next_monitoring_points": [
                "Watch skew for normalization (should reverse over time)",
                "Monitor price action to confirm/invalidate skew direction signal",
                "Track IV changes (skew valid if IV stays elevated)",
                "Watch for catalyst events (earnings, economic data)",
                "Monitor sentiment indicators (VIX, put/call ratio, option flow)",
                "Track relative performance (bullish trades if skew bullish, etc.)",
            ],
        }

        return explanation

    def _explain_regime_shift(
        self, alert: AlertCandidate, ticker: str, features: FeatureSet
    ) -> Dict[str, Any]:
        """
        Generate explanation for technical regime shift detection.

        Regime shifts (golden/death crosses, support bounces) indicate changes in
        technical momentum and direction. These suggest alignment with new trend
        direction through directional option strategies.

        Args:
            alert (AlertCandidate): The regime shift alert
            ticker (str): Stock ticker
            features (FeatureSet): Market features with technicals

        Returns:
            Explanation dict with regime shift context
        """
        rsi = self._get_metric_value(features, "technicals.rsi")
        sma_20 = self._get_metric_value(features, "technicals.sma_20")
        sma_50 = self._get_metric_value(features, "technicals.sma_50")
        sma_200 = self._get_metric_value(features, "technicals.sma_200")

        regime_type = alert.metrics.get("regime_type", "unknown")
        directional_bias = self._infer_regime_bias(alert.metrics)

        explanation = {
            "summary": (
                f"{ticker} entering new technical regime: {regime_type}. "
                f"Momentum shift detected ({directional_bias}). "
                f"Align directional trades with new trend."
            ),
            "rationale": (
                f"Technical regime shifts ({regime_type}) indicate changes in momentum "
                f"and direction. Golden crosses (fast MA > slow MA) are bullish; "
                f"death crosses are bearish. Support bounces or resistance breaks confirm "
                f"regime changes. These shifts often persist for weeks, creating opportunities "
                f"to trade directionally aligned with the new regime rather than fighting it."
            ),
            "key_metrics": [
                self._format_metric("Regime Type", regime_type, None),
                self._format_metric("Price", features.price, None),
                self._format_metric("SMA 20", sma_20, None) if sma_20 else {},
                self._format_metric("RSI(14)", rsi, None) if rsi else {},
                self._format_metric("Score", alert.score, "points"),
            ],
            "directional_bias": directional_bias,
            "risk_factors": [
                "False breakouts (initial moves can reverse before confirming trend)",
                "Whipsaw moves around key levels (support/resistance penetrations)",
                "Reversion to mean (temporary moves that fade before new trend confirms)",
                "Earnings or catalyst events can break regime before confirming",
                "Opposite regime shift can occur if momentum reverses (watch technicals)",
            ],
            "opportunities": [
                f"Long call spreads if regime bullish ({directional_bias})",
                f"Long put spreads if regime bearish ({directional_bias})",
                f"Bull call spreads aligned with {directional_bias} bias",
                f"Bear put spreads if expecting continuation of {directional_bias} trend",
                "Position sizing with trend confirmation (higher conviction in trending markets)",
            ],
            "timeframe": "3-8 weeks (typical regime persistence after shift confirmation)",
            "next_monitoring_points": [
                "Watch price action at regime support/resistance (confirmation points)",
                "Monitor MA crossovers for early reversal signals",
                f"Track RSI for overbought/oversold conditions (during {directional_bias} trend)",
                "Watch volume confirmation (volume should increase in direction of trend)",
                "Monitor for higher lows (uptrend) or lower highs (downtrend)",
                "Watch for break of previous support/resistance levels",
                "Track price relative to key MAs (20, 50, 200 day)",
            ],
        }

        return explanation

    def _explain_generic(
        self, alert: AlertCandidate, ticker: str, features: FeatureSet
    ) -> Dict[str, Any]:
        """
        Generate generic explanation when detector type is unknown.

        This fallback uses the alert explanation data to provide basic context.

        Args:
            alert (AlertCandidate): The generic alert
            ticker (str): Stock ticker
            features (FeatureSet): Market features

        Returns:
            Explanation dict with generic context from alert
        """
        explanation = {
            "summary": alert.explanation.get(
                "summary", f"{ticker}: {alert.detector_name} alert triggered"
            ),
            "rationale": (
                alert.explanation.get("reason", "Trading opportunity detected.")
            ),
            "key_metrics": [
                self._format_metric(k, v, None)
                for k, v in alert.metrics.items()
                if isinstance(v, (int, float)) and not math.isnan(float(v))
            ],
            "directional_bias": "unknown",
            "risk_factors": [
                "Unknown detector type - review detector implementation",
                "Explanation may be incomplete or generic",
                "Validate all metrics before trading",
            ],
            "opportunities": alert.strategies or ["Review detector strategies"],
            "timeframe": "Varies by detector",
            "next_monitoring_points": [
                "Monitor alert trigger conditions",
                "Watch for mean reversion or continuation",
                "Track alert persistence over time",
            ],
        }

        return explanation

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def _format_metric(
        self, name: str, value: Optional[float], unit: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format a metric for display.

        Handles None values, NaN values, and various units appropriately.

        Args:
            name (str): Metric name (e.g., "IV Percentile")
            value (Optional[float]): Metric value
            unit (Optional[str]): Unit string (e.g., "%", "days", "ratio")

        Returns:
            Dict with keys: metric, value, unit
                Returns empty dict if value is None or NaN
        """
        if value is None:
            return {}

        # Check for NaN
        if isinstance(value, float) and math.isnan(value):
            return {}

        return {
            "metric": name,
            "value": round(float(value), 4) if isinstance(value, float) else value,
            "unit": unit or "",
        }

    def _get_metric_value(
        self, features: FeatureSet, path: str
    ) -> Optional[float]:
        """
        Get nested metric value via dotted path.

        Safely traverses nested dictionaries using dot notation.
        Returns None if path invalid or value missing.

        Args:
            features (FeatureSet): Feature set to traverse
            path (str): Dotted path (e.g., "technicals.rsi", "iv_metrics.iv_percentile")

        Returns:
            float or None: The value if found, None otherwise

        Example:
            >>> gen = ExplanationGenerator(config)
            >>> rsi = gen._get_metric_value(features, "technicals.rsi")
            >>> iv_pct = gen._get_metric_value(features, "iv_metrics.iv_percentile")
        """
        try:
            parts = path.split(".")
            current = features

            # First part is attribute on FeatureSet
            if parts[0] in [
                "ticker",
                "timestamp",
                "price",
                "technicals",
                "volatility",
                "options_front",
                "options_back",
                "term_structure",
                "iv_metrics",
                "liquidity",
                "earnings",
            ]:
                current = getattr(features, parts[0])
                parts = parts[1:]
            else:
                logger.warning(f"Invalid metric path: {path} (unknown attribute)")
                return None

            # Traverse remaining path through nested dicts
            for part in parts:
                if isinstance(current, dict):
                    current = current.get(part)
                    if current is None:
                        logger.debug(f"Metric path incomplete: {path}")
                        return None
                else:
                    logger.warning(
                        f"Cannot traverse path {path}: not a dict at {part}"
                    )
                    return None

            # Validate final value is numeric
            if isinstance(current, (int, float)):
                return float(current) if not math.isnan(float(current)) else None
            else:
                logger.debug(f"Metric at {path} is not numeric: {type(current)}")
                return None

        except Exception as e:
            logger.debug(f"Error getting metric {path}: {e}")
            return None

    def _infer_regime_bias(self, metrics: Dict[str, Any]) -> str:
        """
        Infer directional bias from regime shift metrics.

        Looks for signals like "golden_cross" for bullish, "death_cross" for bearish.

        Args:
            metrics (Dict): Alert metrics dict from regime shift detector

        Returns:
            str: "bullish", "bearish", or "neutral"
        """
        regime_type = metrics.get("regime_type", "").lower()

        if "golden" in regime_type or "bullish" in regime_type or "bounce" in regime_type:
            return "bullish"
        elif "death" in regime_type or "bearish" in regime_type or "breakdown" in regime_type:
            return "bearish"
        else:
            return "neutral"
