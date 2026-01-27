"""
Unit tests for ExplanationGenerator template-based explanation engine.

Tests cover:
- Initialization and validation
- Routing to detector-specific helpers
- Low IV explanation generation
- Rich premium explanation generation
- Earnings crush explanation generation
- Term kink explanation generation
- Skew anomaly explanation generation
- Regime shift explanation generation
- Generic explanation (unknown detector)
- Metric formatting utility
- Metric path traversal utility
- Handling of missing/invalid data

Usage:
    pytest tests/tech/unit/test_template_explain.py
    pytest tests/tech/unit/test_template_explain.py -v
    pytest tests/tech/unit/test_template_explain.py -k "low_iv"
"""

import pytest
import math
from datetime import datetime, timezone, date
from unittest.mock import MagicMock

from functions.explain.template_explain import ExplanationGenerator
from functions.config.models import AppConfig
from functions.detect.base import AlertCandidate
from functions.compute.feature_engine import FeatureSet


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def config():
    """Provide test AppConfig instance."""
    return AppConfig()


@pytest.fixture
def generator(config):
    """Provide ExplanationGenerator instance."""
    return ExplanationGenerator(config)


@pytest.fixture
def base_features():
    """Provide minimal valid FeatureSet for testing."""
    return FeatureSet(
        ticker="AAPL",
        timestamp=datetime.now(timezone.utc),
        price=150.0,
        price_change_1d=1.5,
        price_change_5d=-2.0,
        technicals={
            "sma_20": 148.5,
            "sma_50": 145.0,
            "sma_200": 140.0,
            "rsi": 55.0,
            "volume_sma_20": 50000000,
        },
        volatility={
            "hv_20": 0.25,
            "vol_expanding": False,
        },
        options_front={
            "dte": 30,
            "atm_iv": 0.35,
            "volume": 100000,
            "oi": 500000,
        },
        options_back={
            "dte": 60,
            "atm_iv": 0.38,
            "volume": 80000,
            "oi": 400000,
        },
        term_structure={
            "iv_ratio": 0.92,
            "iv_diff": -0.03,
        },
        iv_metrics={
            "iv_percentile": 35.0,
            "iv_rank": 0.35,
        },
        liquidity={
            "passes_filter": True,
            "adv_usd": 5000000000,
        },
        earnings={
            "days_to_earnings": 30,
            "earnings_date": date(2026, 3, 26),
        },
        config_hash="v1_test",
    )


@pytest.fixture
def low_iv_alert():
    """Provide AlertCandidate for low IV detection."""
    return AlertCandidate(
        detector_name="LowIVDetector",
        score=75.0,
        metrics={
            "iv_percentile": 20.0,
            "iv_front": 0.25,
            "iv_vs_hv": 1.0,
            "rsi_14": 40.0,
            "vol_expanding": False,
        },
        explanation={
            "summary": "Low IV detected",
            "reason": "Premium selling opportunity",
            "trigger": "IV percentile < 25",
        },
        strategies=["Long Straddle", "Calendar Spread"],
        confidence="high",
    )


@pytest.fixture
def rich_premium_alert():
    """Provide AlertCandidate for rich premium detection."""
    return AlertCandidate(
        detector_name="RichPremiumDetector",
        score=70.0,
        metrics={
            "iv_percentile": 80.0,
            "iv_front": 0.45,
            "iv_vs_hv": 1.8,
        },
        explanation={
            "summary": "High IV detected",
            "reason": "Premium buying opportunity",
            "trigger": "IV percentile > 75",
        },
        strategies=["Bull Call Spread", "Long Call"],
        confidence="medium",
    )


@pytest.fixture
def earnings_alert():
    """Provide AlertCandidate for earnings crush detection."""
    return AlertCandidate(
        detector_name="EarningsCrushDetector",
        score=65.0,
        metrics={
            "iv_percentile": 85.0,
            "iv_front": 0.50,
            "days_to_earnings": 7,
        },
        explanation={
            "summary": "Earnings approaching",
            "reason": "IV crush opportunity",
            "trigger": "Days to earnings < 14",
        },
        strategies=["Short Straddle", "Iron Condor"],
        confidence="medium",
    )


@pytest.fixture
def term_kink_alert():
    """Provide AlertCandidate for term structure kink detection."""
    return AlertCandidate(
        detector_name="TermKinkDetector",
        score=68.0,
        metrics={
            "iv_ratio": 1.15,
            "iv_diff": 0.08,
            "iv_front": 0.35,
            "iv_back": 0.30,
        },
        explanation={
            "summary": "Term structure abnormal",
            "reason": "Calendar spread opportunity",
            "trigger": "IV ratio outside normal range",
        },
        strategies=["Calendar Spread", "Diagonal Spread"],
        confidence="medium",
    )


@pytest.fixture
def skew_alert():
    """Provide AlertCandidate for skew anomaly detection."""
    return AlertCandidate(
        detector_name="SkewAnomalyDetector",
        score=72.0,
        metrics={
            "put_call_iv_ratio": 1.25,
            "directional_signal": "bullish",
        },
        explanation={
            "summary": "Put/call skew imbalanced",
            "reason": "Directional sentiment signal",
            "trigger": "Put/call IV ratio elevated",
        },
        strategies=["Bull Call Spread", "Bull Put Spread"],
        confidence="high",
    )


@pytest.fixture
def regime_shift_alert():
    """Provide AlertCandidate for regime shift detection."""
    return AlertCandidate(
        detector_name="RegimeShiftDetector",
        score=80.0,
        metrics={
            "regime_type": "golden_cross",
            "sma_20_above_sma_50": True,
        },
        explanation={
            "summary": "Regime shift detected",
            "reason": "Technical momentum change",
            "trigger": "Golden cross (SMA20 > SMA50)",
        },
        strategies=["Long Call", "Bull Call Spread"],
        confidence="high",
    )


# ============================================================================
# TESTS: INITIALIZATION
# ============================================================================


class TestExplanationGeneratorInit:
    """Test ExplanationGenerator initialization."""

    def test_init_with_valid_config(self, config):
        """Should initialize with valid AppConfig."""
        gen = ExplanationGenerator(config)
        assert gen.config is config

    def test_init_with_invalid_config_type(self):
        """Should raise TypeError if config is not AppConfig."""
        with pytest.raises(TypeError):
            ExplanationGenerator({"not": "config"})

    def test_init_with_none_config(self):
        """Should raise TypeError if config is None."""
        with pytest.raises(TypeError):
            ExplanationGenerator(None)


# ============================================================================
# TESTS: MAIN GENERATE_EXPLANATION METHOD
# ============================================================================


class TestGenerateExplanation:
    """Test main generate_explanation method."""

    def test_invalid_alert_type(self, generator, base_features):
        """Should raise TypeError if alert is not AlertCandidate."""
        with pytest.raises(TypeError):
            generator.generate_explanation({"not": "alert"}, "AAPL", base_features)

    def test_invalid_ticker_type(self, generator, low_iv_alert, base_features):
        """Should raise TypeError if ticker is not string."""
        with pytest.raises(TypeError):
            generator.generate_explanation(low_iv_alert, 123, base_features)

    def test_invalid_features_type(self, generator, low_iv_alert):
        """Should raise TypeError if features is not FeatureSet."""
        with pytest.raises(TypeError):
            generator.generate_explanation(low_iv_alert, "AAPL", {"not": "features"})

    def test_explanation_has_required_keys(self, generator, low_iv_alert, base_features):
        """Generated explanation should have all required keys."""
        explanation = generator.generate_explanation(
            low_iv_alert, "AAPL", base_features
        )

        required_keys = {
            "summary",
            "rationale",
            "key_metrics",
            "directional_bias",
            "risk_factors",
            "opportunities",
            "timeframe",
            "next_monitoring_points",
            "timestamp",
        }
        assert required_keys.issubset(explanation.keys())

    def test_explanation_timestamp_is_utc(self, generator, low_iv_alert, base_features):
        """Timestamp should be in UTC ISO format with Z suffix."""
        explanation = generator.generate_explanation(
            low_iv_alert, "AAPL", base_features
        )
        timestamp = explanation["timestamp"]
        assert timestamp.endswith("Z"), "Timestamp should end with Z"
        assert "T" in timestamp, "Timestamp should be ISO format"

    def test_explanation_summary_contains_ticker(
        self, generator, low_iv_alert, base_features
    ):
        """Summary should contain ticker symbol."""
        explanation = generator.generate_explanation(
            low_iv_alert, "AAPL", base_features
        )
        assert "AAPL" in explanation["summary"]

    def test_explanation_risk_factors_is_list(
        self, generator, low_iv_alert, base_features
    ):
        """Risk factors should be a list."""
        explanation = generator.generate_explanation(
            low_iv_alert, "AAPL", base_features
        )
        assert isinstance(explanation["risk_factors"], list)
        assert len(explanation["risk_factors"]) > 0

    def test_explanation_opportunities_is_list(
        self, generator, low_iv_alert, base_features
    ):
        """Opportunities should be a list."""
        explanation = generator.generate_explanation(
            low_iv_alert, "AAPL", base_features
        )
        assert isinstance(explanation["opportunities"], list)
        assert len(explanation["opportunities"]) > 0

    def test_explanation_key_metrics_is_list(
        self, generator, low_iv_alert, base_features
    ):
        """Key metrics should be a list of dicts with metric, value, unit."""
        explanation = generator.generate_explanation(
            low_iv_alert, "AAPL", base_features
        )
        metrics = explanation["key_metrics"]
        assert isinstance(metrics, list)
        for metric in metrics:
            if metric:  # Skip empty dicts from missing values
                assert "metric" in metric
                assert "value" in metric
                assert "unit" in metric


# ============================================================================
# TESTS: LOW IV EXPLANATION
# ============================================================================


class TestLowIVExplanation:
    """Test _explain_low_iv method."""

    def test_low_iv_explanation_content(self, generator, low_iv_alert, base_features):
        """Low IV explanation should have specific content."""
        explanation = generator._explain_low_iv(low_iv_alert, "AAPL", base_features)

        assert "percentile" in explanation["summary"].lower()
        assert "premium-selling" in explanation["rationale"].lower()
        assert explanation["directional_bias"] == "neutral"
        assert len(explanation["risk_factors"]) >= 3
        assert any("calendar" in opp.lower() for opp in explanation["opportunities"])

    def test_low_iv_directional_bias(self, generator, low_iv_alert, base_features):
        """Low IV should have neutral directional bias."""
        explanation = generator._explain_low_iv(low_iv_alert, "AAPL", base_features)
        assert explanation["directional_bias"] == "neutral"

    def test_low_iv_includes_calendar_spread(self, generator, low_iv_alert, base_features):
        """Low IV opportunities should include calendar spreads."""
        explanation = generator._explain_low_iv(low_iv_alert, "AAPL", base_features)
        assert any("Calendar" in opp for opp in explanation["opportunities"])

    def test_low_iv_monitoring_points(self, generator, low_iv_alert, base_features):
        """Low IV should include IV expansion monitoring."""
        explanation = generator._explain_low_iv(low_iv_alert, "AAPL", base_features)
        monitoring = explanation["next_monitoring_points"]
        assert any("IV expansion" in point for point in monitoring)


# ============================================================================
# TESTS: RICH PREMIUM EXPLANATION
# ============================================================================


class TestRichPremiumExplanation:
    """Test _explain_rich_premium method."""

    def test_rich_premium_explanation_content(
        self, generator, rich_premium_alert, base_features
    ):
        """Rich premium explanation should have specific content."""
        explanation = generator._explain_rich_premium(
            rich_premium_alert, "AAPL", base_features
        )

        assert "percentile" in explanation["summary"].lower()
        assert "elevated" in explanation["rationale"].lower()
        assert len(explanation["risk_factors"]) >= 3
        assert any("spread" in opp.lower() for opp in explanation["opportunities"])

    def test_rich_premium_includes_spreads(
        self, generator, rich_premium_alert, base_features
    ):
        """Rich premium opportunities should include spreads."""
        explanation = generator._explain_rich_premium(
            rich_premium_alert, "AAPL", base_features
        )
        opportunities = explanation["opportunities"]
        assert any("spread" in opp.lower() for opp in opportunities)


# ============================================================================
# TESTS: EARNINGS CRUSH EXPLANATION
# ============================================================================


class TestEarningsCrushExplanation:
    """Test _explain_earnings_crush method."""

    def test_earnings_crush_explanation_content(
        self, generator, earnings_alert, base_features
    ):
        """Earnings crush explanation should reference days to earnings."""
        explanation = generator._explain_earnings_crush(
            earnings_alert, "AAPL", base_features
        )

        assert "earnings" in explanation["summary"].lower()
        assert "earnings" in explanation["rationale"].lower()
        assert explanation["directional_bias"] == "neutral (unless post-earnings direction is known)"

    def test_earnings_crush_includes_straddle(
        self, generator, earnings_alert, base_features
    ):
        """Earnings crush opportunities should include straddle strategies."""
        explanation = generator._explain_earnings_crush(
            earnings_alert, "AAPL", base_features
        )
        assert any("straddle" in opp.lower() for opp in explanation["opportunities"])


# ============================================================================
# TESTS: TERM KINK EXPLANATION
# ============================================================================


class TestTermKinkExplanation:
    """Test _explain_term_kink method."""

    def test_term_kink_explanation_content(
        self, generator, term_kink_alert, base_features
    ):
        """Term kink explanation should reference IV ratio."""
        explanation = generator._explain_term_kink(
            term_kink_alert, "AAPL", base_features
        )

        assert "term structure" in explanation["summary"].lower()
        assert "calendar spread" in explanation["rationale"].lower()
        assert explanation["directional_bias"] == "neutral (term structure agnostic to direction)"

    def test_term_kink_includes_calendar_spread(
        self, generator, term_kink_alert, base_features
    ):
        """Term kink opportunities should include calendar spread."""
        explanation = generator._explain_term_kink(
            term_kink_alert, "AAPL", base_features
        )
        assert any("Calendar" in opp for opp in explanation["opportunities"])


# ============================================================================
# TESTS: SKEW ANOMALY EXPLANATION
# ============================================================================


class TestSkewAnomalyExplanation:
    """Test _explain_skew_anomaly method."""

    def test_skew_anomaly_explanation_content(
        self, generator, skew_alert, base_features
    ):
        """Skew anomaly explanation should reference put/call skew."""
        explanation = generator._explain_skew_anomaly(
            skew_alert, "AAPL", base_features
        )

        assert "skew" in explanation["summary"].lower()
        assert "put/call" in explanation["rationale"].lower() or "put/call skew" in explanation["rationale"].lower()
        assert explanation["directional_bias"] == "bullish"

    def test_skew_anomaly_bullish_directional_bias(
        self, generator, skew_alert, base_features
    ):
        """Skew anomaly with bullish signal should have bullish bias."""
        explanation = generator._explain_skew_anomaly(
            skew_alert, "AAPL", base_features
        )
        assert explanation["directional_bias"] == "bullish"


# ============================================================================
# TESTS: REGIME SHIFT EXPLANATION
# ============================================================================


class TestRegimeShiftExplanation:
    """Test _explain_regime_shift method."""

    def test_regime_shift_explanation_content(
        self, generator, regime_shift_alert, base_features
    ):
        """Regime shift explanation should reference technical regime."""
        explanation = generator._explain_regime_shift(
            regime_shift_alert, "AAPL", base_features
        )

        assert "regime" in explanation["summary"].lower()
        assert "regime" in explanation["rationale"].lower()

    def test_regime_shift_bullish_bias(self, generator, regime_shift_alert, base_features):
        """Golden cross should result in bullish bias."""
        explanation = generator._explain_regime_shift(
            regime_shift_alert, "AAPL", base_features
        )
        assert explanation["directional_bias"] == "bullish"

    def test_regime_shift_includes_call_strategies(
        self, generator, regime_shift_alert, base_features
    ):
        """Bullish regime should include call strategies."""
        explanation = generator._explain_regime_shift(
            regime_shift_alert, "AAPL", base_features
        )
        opportunities = explanation["opportunities"]
        assert any("call" in opp.lower() for opp in opportunities)


# ============================================================================
# TESTS: GENERIC EXPLANATION (UNKNOWN DETECTOR)
# ============================================================================


class TestGenericExplanation:
    """Test _explain_generic fallback method."""

    def test_generic_explanation_uses_alert_data(
        self, generator, low_iv_alert, base_features
    ):
        """Generic explanation should use alert explanation data."""
        explanation = generator._explain_generic(
            low_iv_alert, "AAPL", base_features
        )

        assert explanation["summary"] == low_iv_alert.explanation["summary"]
        assert explanation["rationale"] == low_iv_alert.explanation["reason"]

    def test_unknown_detector_uses_generic(
        self, generator, base_features
    ):
        """Unknown detector should fall back to generic explanation."""
        unknown_alert = AlertCandidate(
            detector_name="UnknownDetector",
            score=65.0,
            metrics={"some_metric": 1.5},
            explanation={
                "summary": "Unknown detection",
                "reason": "Unknown opportunity",
                "trigger": "Unknown trigger",
            },
            strategies=["Some Strategy"],
            confidence="low",
        )

        explanation = generator.generate_explanation(
            unknown_alert, "AAPL", base_features
        )
        assert explanation["summary"] == "Unknown detection"


# ============================================================================
# TESTS: UTILITY METHODS
# ============================================================================


class TestFormatMetric:
    """Test _format_metric utility method."""

    def test_format_metric_with_value(self, generator):
        """Should format metric with value and unit."""
        result = generator._format_metric("IV Percentile", 35.5, "%")
        assert result["metric"] == "IV Percentile"
        assert result["value"] == 35.5
        assert result["unit"] == "%"

    def test_format_metric_none_value(self, generator):
        """Should return empty dict for None value."""
        result = generator._format_metric("Missing Metric", None)
        assert result == {}

    def test_format_metric_nan_value(self, generator):
        """Should return empty dict for NaN value."""
        result = generator._format_metric("NaN Metric", float("nan"))
        assert result == {}

    def test_format_metric_no_unit(self, generator):
        """Should handle metric with no unit."""
        result = generator._format_metric("Some Metric", 42.5)
        assert result["metric"] == "Some Metric"
        assert result["value"] == 42.5
        assert result["unit"] == ""

    def test_format_metric_rounds_floats(self, generator):
        """Should round float values to 4 decimal places."""
        result = generator._format_metric("Precise", 3.141592653589793)
        assert result["value"] == 3.1416


# ============================================================================
# TESTS: GET_METRIC_VALUE UTILITY
# ============================================================================


class TestGetMetricValue:
    """Test _get_metric_value utility method."""

    def test_get_metric_from_technicals(self, generator, base_features):
        """Should retrieve metric from technicals dict."""
        rsi = generator._get_metric_value(base_features, "technicals.rsi")
        assert rsi == 55.0

    def test_get_metric_from_iv_metrics(self, generator, base_features):
        """Should retrieve metric from iv_metrics dict."""
        iv_pct = generator._get_metric_value(base_features, "iv_metrics.iv_percentile")
        assert iv_pct == 35.0

    def test_get_metric_from_options_front(self, generator, base_features):
        """Should retrieve metric from options_front dict."""
        iv = generator._get_metric_value(base_features, "options_front.atm_iv")
        assert iv == 0.35

    def test_get_metric_from_earnings(self, generator, base_features):
        """Should retrieve metric from earnings dict."""
        dte = generator._get_metric_value(base_features, "earnings.days_to_earnings")
        assert dte == 30.0

    def test_get_metric_invalid_path(self, generator, base_features):
        """Should return None for invalid path."""
        result = generator._get_metric_value(base_features, "invalid.path")
        assert result is None

    def test_get_metric_missing_nested_key(self, generator, base_features):
        """Should return None for missing nested key."""
        result = generator._get_metric_value(base_features, "technicals.missing_key")
        assert result is None

    def test_get_metric_non_numeric_value(self, generator, base_features):
        """Should return None for non-numeric values."""
        # Note: boolean values (True/False) get converted to 1.0/0.0 when coerced to float
        # The _get_metric_value returns None only if the final value is not numeric type
        # Test with a string value instead
        base_features.liquidity["string_val"] = "not_a_number"
        result = generator._get_metric_value(base_features, "liquidity.string_val")
        assert result is None

    def test_get_metric_nan_value_in_dict(self, generator):
        """Should return None for NaN values in dict."""
        features = FeatureSet(
            ticker="TEST",
            timestamp=datetime.now(timezone.utc),
            price=100.0,
            technicals={"rsi": float("nan")},
            config_hash="test",
        )
        result = generator._get_metric_value(features, "technicals.rsi")
        assert result is None


# ============================================================================
# TESTS: INFER_REGIME_BIAS UTILITY
# ============================================================================


class TestInferRegimeBias:
    """Test _infer_regime_bias utility method."""

    def test_golden_cross_is_bullish(self, generator):
        """Golden cross should be bullish."""
        bias = generator._infer_regime_bias({"regime_type": "golden_cross"})
        assert bias == "bullish"

    def test_death_cross_is_bearish(self, generator):
        """Death cross should be bearish."""
        bias = generator._infer_regime_bias({"regime_type": "death_cross"})
        assert bias == "bearish"

    def test_bullish_keyword_is_bullish(self, generator):
        """Bullish regime type should be bullish."""
        bias = generator._infer_regime_bias({"regime_type": "bullish_breakout"})
        assert bias == "bullish"

    def test_bearish_keyword_is_bearish(self, generator):
        """Bearish regime type should be bearish."""
        bias = generator._infer_regime_bias({"regime_type": "bearish_breakdown"})
        assert bias == "bearish"

    def test_support_bounce_is_bullish(self, generator):
        """Support bounce should be bullish."""
        bias = generator._infer_regime_bias({"regime_type": "support_bounce"})
        assert bias == "bullish"

    def test_unknown_regime_is_neutral(self, generator):
        """Unknown regime type should be neutral."""
        bias = generator._infer_regime_bias({"regime_type": "unknown_pattern"})
        assert bias == "neutral"


# ============================================================================
# TESTS: INTEGRATION / FULL WORKFLOW
# ============================================================================


class TestFullWorkflow:
    """Test complete workflows with all detector types."""

    def test_low_iv_workflow(self, config, base_features):
        """Complete low IV detection -> explanation workflow."""
        gen = ExplanationGenerator(config)

        alert = AlertCandidate(
            detector_name="LowIVDetector",
            score=78.0,
            metrics={"iv_percentile": 18.0, "iv_front": 0.22},
            explanation={
                "summary": "Low IV",
                "reason": "Selling opportunity",
                "trigger": "IV < 25th percentile",
            },
            strategies=["Calendar Spread"],
            confidence="high",
        )

        explanation = gen.generate_explanation(alert, "AAPL", base_features)

        assert explanation["directional_bias"] == "neutral"
        assert len(explanation["risk_factors"]) > 0
        assert len(explanation["opportunities"]) > 0
        assert explanation["timestamp"].endswith("Z")

    def test_earnings_workflow(self, config, base_features):
        """Complete earnings crush detection -> explanation workflow."""
        gen = ExplanationGenerator(config)

        alert = AlertCandidate(
            detector_name="EarningsCrushDetector",
            score=70.0,
            metrics={"iv_percentile": 85.0, "days_to_earnings": 5},
            explanation={
                "summary": "Earnings approaching",
                "reason": "IV crush",
                "trigger": "Days < 14",
            },
            strategies=["Straddle"],
            confidence="medium",
        )

        explanation = gen.generate_explanation(alert, "TSLA", base_features)

        assert "earnings" in explanation["summary"].lower()
        assert "TSLA" in explanation["summary"]
        assert len(explanation["opportunities"]) > 0

    def test_regime_shift_workflow(self, config, base_features):
        """Complete regime shift detection -> explanation workflow."""
        gen = ExplanationGenerator(config)

        alert = AlertCandidate(
            detector_name="RegimeShiftDetector",
            score=82.0,
            metrics={"regime_type": "golden_cross"},
            explanation={
                "summary": "Golden cross",
                "reason": "Bullish momentum",
                "trigger": "SMA20 > SMA50",
            },
            strategies=["Long Call"],
            confidence="high",
        )

        explanation = gen.generate_explanation(alert, "SPY", base_features)

        assert explanation["directional_bias"] == "bullish"
        assert "call" in str(explanation["opportunities"]).lower()
