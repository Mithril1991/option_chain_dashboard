"""
Unit tests for RiskGate portfolio risk enforcement.

Tests the RiskGate class including:
- Margin gate validation
- Cash gate validation
- Concentration gate validation
- Portfolio summary generation
- Account state management
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime
import pytz

from functions.risk.gate import (
    RiskGate,
    AccountState,
    AccountPosition,
)


# ============================================================================
# ACCOUNT POSITION TESTS
# ============================================================================


class TestAccountPosition:
    """Test suite for AccountPosition class."""

    def test_account_position_creation(self):
        """Test basic AccountPosition initialization."""
        pos = AccountPosition("AAPL", 100, 150.0, 155.0)
        assert pos.ticker == "AAPL"
        assert pos.quantity == 100
        assert pos.entry_price == 150.0
        assert pos.current_price == 155.0

    def test_position_value_calculation(self):
        """Test position_value property calculation."""
        pos = AccountPosition("AAPL", 100, 150.0, 155.0)
        assert pos.position_value == 15500.0  # 100 * 155.0

    def test_position_value_absolute_short(self):
        """Test position_value uses absolute quantity for shorts."""
        pos = AccountPosition("AAPL", -50, 150.0, 155.0)
        assert pos.position_value == 7750.0  # abs(-50) * 155.0

    def test_unrealized_pnl_long_profit(self):
        """Test unrealized P&L for profitable long position."""
        pos = AccountPosition("AAPL", 100, 150.0, 155.0)
        assert pos.unrealized_pnl == 500.0  # 100 * (155 - 150)

    def test_unrealized_pnl_long_loss(self):
        """Test unrealized P&L for losing long position."""
        pos = AccountPosition("AAPL", 100, 160.0, 155.0)
        assert pos.unrealized_pnl == -500.0  # 100 * (155 - 160)

    def test_unrealized_pnl_short_profit(self):
        """Test unrealized P&L for profitable short position."""
        pos = AccountPosition("AAPL", -100, 160.0, 155.0)
        assert pos.unrealized_pnl == 500.0  # abs(-100) * (160 - 155)

    def test_unrealized_pnl_short_loss(self):
        """Test unrealized P&L for losing short position."""
        pos = AccountPosition("AAPL", -100, 150.0, 155.0)
        assert pos.unrealized_pnl == -500.0  # abs(-100) * (150 - 155)


# ============================================================================
# ACCOUNT STATE TESTS
# ============================================================================


class TestAccountState:
    """Test suite for AccountState class."""

    def test_account_state_creation_defaults(self):
        """Test AccountState initialization with defaults."""
        account = AccountState()
        assert account.margin_available == 0.0
        assert account.cash_available == 0.0
        assert account.positions == {}

    def test_account_state_creation_with_values(self):
        """Test AccountState initialization with provided values."""
        account = AccountState(
            margin_available=50000.0,
            cash_available=100000.0,
        )
        assert account.margin_available == 50000.0
        assert account.cash_available == 100000.0

    def test_account_state_with_positions(self):
        """Test AccountState with multiple positions."""
        pos1 = AccountPosition("AAPL", 100, 150.0, 155.0)
        pos2 = AccountPosition("GOOGL", 50, 140.0, 145.0)
        positions = {"AAPL": pos1, "GOOGL": pos2}

        account = AccountState(positions=positions)
        assert len(account.positions) == 2
        assert account.positions["AAPL"] == pos1
        assert account.positions["GOOGL"] == pos2

    def test_total_portfolio_value_empty(self):
        """Test total_portfolio_value with no positions."""
        account = AccountState()
        assert account.total_portfolio_value == 0.0

    def test_total_portfolio_value_single_position(self):
        """Test total_portfolio_value with single position."""
        pos = AccountPosition("AAPL", 100, 150.0, 155.0)
        account = AccountState(positions={"AAPL": pos})
        assert account.total_portfolio_value == 15500.0

    def test_total_portfolio_value_multiple_positions(self):
        """Test total_portfolio_value with multiple positions."""
        pos1 = AccountPosition("AAPL", 100, 150.0, 155.0)  # 15500
        pos2 = AccountPosition("GOOGL", 50, 140.0, 145.0)  # 7250
        positions = {"AAPL": pos1, "GOOGL": pos2}
        account = AccountState(positions=positions)
        assert account.total_portfolio_value == 22750.0

    def test_get_position_value_exists(self):
        """Test get_position_value for existing ticker."""
        pos = AccountPosition("AAPL", 100, 150.0, 155.0)
        account = AccountState(positions={"AAPL": pos})
        assert account.get_position_value("AAPL") == 15500.0

    def test_get_position_value_not_exists(self):
        """Test get_position_value for non-existent ticker."""
        account = AccountState()
        assert account.get_position_value("AAPL") == 0.0

    def test_get_concentration_pct_zero_portfolio(self):
        """Test get_concentration_pct with zero portfolio value."""
        account = AccountState()
        assert account.get_concentration_pct("AAPL") == 0.0

    def test_get_concentration_pct_single_position(self):
        """Test get_concentration_pct with single position."""
        pos = AccountPosition("AAPL", 100, 150.0, 155.0)
        account = AccountState(positions={"AAPL": pos})
        assert account.get_concentration_pct("AAPL") == 100.0

    def test_get_concentration_pct_multiple_positions(self):
        """Test get_concentration_pct calculation with multiple positions."""
        pos1 = AccountPosition("AAPL", 100, 150.0, 155.0)  # 15500
        pos2 = AccountPosition("GOOGL", 50, 140.0, 145.0)  # 7250
        positions = {"AAPL": pos1, "GOOGL": pos2}
        account = AccountState(positions=positions)
        # AAPL: 15500 / 22750 = 68.13%
        assert abs(account.get_concentration_pct("AAPL") - 68.13) < 0.01
        # GOOGL: 7250 / 22750 = 31.87%
        assert abs(account.get_concentration_pct("GOOGL") - 31.87) < 0.01


# ============================================================================
# RISK GATE TESTS
# ============================================================================


class TestRiskGate:
    """Test suite for RiskGate class."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock AppConfig for testing."""
        config = Mock()
        config.account = AccountState(
            margin_available=50000.0,
            cash_available=100000.0,
        )
        return config

    @pytest.fixture
    def gate(self, mock_config):
        """Create a RiskGate instance with mock config."""
        return RiskGate(mock_config)

    @pytest.fixture
    def test_alert(self):
        """Create a test AlertCandidate."""
        alert = Mock()
        alert.detector_name = "TestDetector"
        alert.score = 75.0
        alert.strategies = ["Long Call Spread"]
        alert.metrics = {"premium_estimate": 1.5}
        alert.confidence = "high"
        return alert

    def test_risk_gate_initialization(self, mock_config):
        """Test RiskGate initialization with config."""
        gate = RiskGate(mock_config)
        assert gate.config == mock_config
        assert gate.account is not None

    def test_risk_gate_initialization_invalid_config(self):
        """Test RiskGate initialization with invalid config raises error."""
        with pytest.raises(ValueError):
            RiskGate("invalid config")

    def test_risk_gate_no_account_in_config(self):
        """Test RiskGate initialization when config has no account."""
        config = Mock(spec=[])  # No account attribute
        gate = RiskGate(config)
        assert gate.account is not None
        assert gate.account.margin_available == 0.0

    def test_passes_risk_gate_invalid_alert(self, gate):
        """Test passes_risk_gate with invalid alert raises error."""
        with pytest.raises(ValueError):
            gate.passes_risk_gate("invalid alert", "AAPL")

    def test_passes_risk_gate_invalid_ticker(self, gate, test_alert):
        """Test passes_risk_gate with invalid ticker raises error."""
        with pytest.raises(ValueError):
            gate.passes_risk_gate(test_alert, "")

    def test_check_margin_gate_passes(self, gate, test_alert):
        """Test margin gate passes with adequate margin."""
        passes, reason = gate._check_margin_gate(test_alert, "AAPL")
        assert passes is True
        assert "Margin gate passed" in reason

    def test_check_margin_gate_fails(self, gate, test_alert):
        """Test margin gate fails when margin exceeded."""
        # Set very low available margin
        gate.account.margin_available = 10.0
        passes, reason = gate._check_margin_gate(test_alert, "AAPL")
        assert passes is False
        assert "FAILED" in reason

    def test_check_margin_gate_no_limit(self, gate, test_alert):
        """Test margin gate passes when no limit configured."""
        gate.account.margin_available = 0.0
        passes, reason = gate._check_margin_gate(test_alert, "AAPL")
        assert passes is True
        assert "no limit" in reason

    def test_check_cash_gate_passes_no_cash_strategy(self, gate, test_alert):
        """Test cash gate passes for non-cash-requiring strategies."""
        passes, reason = gate._check_cash_gate(test_alert, "AAPL")
        assert passes is True
        assert "doesn't require cash" in reason

    def test_check_cash_gate_csp_passes(self, gate):
        """Test cash gate passes for CSP with adequate cash."""
        alert = Mock()
        alert.detector_name = "TestDetector"
        alert.strategies = ["Cash Secured Put"]
        alert.metrics = {"strike_estimate": 100.0, "quantity": 1}
        alert.confidence = "high"

        passes, reason = gate._check_cash_gate(alert, "AAPL")
        assert passes is True
        assert "Cash gate passed" in reason

    def test_check_cash_gate_csp_fails(self, gate):
        """Test cash gate fails for CSP when cash insufficient."""
        gate.account.cash_available = 1000.0  # Only 1000 available
        alert = Mock()
        alert.detector_name = "TestDetector"
        alert.strategies = ["Cash Secured Put"]
        alert.metrics = {"strike_estimate": 200.0, "quantity": 10}  # Need 200k
        alert.confidence = "high"

        passes, reason = gate._check_cash_gate(alert, "AAPL")
        assert passes is False
        assert "FAILED" in reason

    def test_check_concentration_gate_passes(self, gate):
        """Test concentration gate passes with low concentration."""
        passes, reason = gate._check_concentration_gate("AAPL")
        assert passes is True
        assert "Concentration gate passed" in reason

    def test_check_concentration_gate_fails(self, gate):
        """Test concentration gate fails with high concentration."""
        # Add a large position (over 5%)
        pos = AccountPosition("AAPL", 100, 150.0, 3000.0)  # 300k value
        gate.account.positions = {"AAPL": pos}

        passes, reason = gate._check_concentration_gate("AAPL")
        assert passes is False
        assert "FAILED" in reason

    def test_passes_risk_gate_all_gates_pass(self, gate, test_alert):
        """Test passes_risk_gate returns True when all gates pass."""
        passes, reason = gate.passes_risk_gate(test_alert, "AAPL")
        assert passes is True
        assert reason is None

    def test_passes_risk_gate_margin_gate_fails(self, gate, test_alert):
        """Test passes_risk_gate returns False when margin gate fails."""
        gate.account.margin_available = 10.0  # Very low margin
        passes, reason = gate.passes_risk_gate(test_alert, "AAPL")
        assert passes is False
        assert reason is not None
        assert "Margin gate" in reason or "MARGIN_GATE" in reason

    def test_get_portfolio_summary_empty_account(self, gate):
        """Test get_portfolio_summary with empty account."""
        summary = gate.get_portfolio_summary()
        assert summary["margin_available"] == 50000.0
        assert summary["cash_available"] == 100000.0
        assert summary["total_portfolio_value"] == 0.0
        assert summary["concentration_by_ticker"] == {}
        assert "timestamp_utc" in summary

    def test_get_portfolio_summary_with_positions(self, gate):
        """Test get_portfolio_summary with positions."""
        pos = AccountPosition("AAPL", 100, 150.0, 155.0)
        gate.account.positions = {"AAPL": pos}

        summary = gate.get_portfolio_summary()
        assert summary["total_portfolio_value"] == 15500.0
        assert "AAPL" in summary["concentration_by_ticker"]
        assert summary["concentration_by_ticker"]["AAPL"] == 100.0

    def test_get_portfolio_summary_multiple_positions(self, gate):
        """Test get_portfolio_summary with multiple positions."""
        pos1 = AccountPosition("AAPL", 100, 150.0, 155.0)
        pos2 = AccountPosition("GOOGL", 50, 140.0, 145.0)
        gate.account.positions = {"AAPL": pos1, "GOOGL": pos2}

        summary = gate.get_portfolio_summary()
        assert summary["total_portfolio_value"] == 22750.0
        assert len(summary["concentration_by_ticker"]) == 2
        # AAPL: 15500 / 22750 ≈ 68.13%
        assert 68.0 < summary["concentration_by_ticker"]["AAPL"] < 69.0
        # GOOGL: 7250 / 22750 ≈ 31.87%
        assert 31.0 < summary["concentration_by_ticker"]["GOOGL"] < 32.0

    def test_get_portfolio_summary_timestamp_utc(self, gate):
        """Test get_portfolio_summary includes UTC timestamp."""
        summary = gate.get_portfolio_summary()
        timestamp_str = summary["timestamp_utc"]
        assert "T" in timestamp_str  # ISO format
        assert "Z" in timestamp_str or "+00:00" in timestamp_str  # UTC indicator


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestRiskGateIntegration:
    """Integration tests for RiskGate with realistic scenarios."""

    def test_multi_position_portfolio_with_all_gates(self):
        """Test RiskGate with realistic multi-position portfolio."""
        # Create realistic account
        pos1 = AccountPosition("AAPL", 100, 150.0, 155.0)  # 15500
        pos2 = AccountPosition("GOOGL", 50, 140.0, 145.0)  # 7250
        pos3 = AccountPosition("MSFT", 75, 300.0, 310.0)  # 23250

        account = AccountState(
            margin_available=100000.0,
            cash_available=200000.0,
            positions={"AAPL": pos1, "GOOGL": pos2, "MSFT": pos3}
        )

        config = Mock()
        config.account = account
        gate = RiskGate(config)

        # Test concentration - MSFT is 23250 / 46000 = 50.5% (exceeds 5% limit)
        passes, reason = gate._check_concentration_gate("MSFT")
        assert passes is False

        # Test with new ticker
        passes, reason = gate._check_concentration_gate("TSLA")
        assert passes is True

    def test_margin_calculation_with_spread_strategy(self):
        """Test margin calculation for spread strategies."""
        account = AccountState(margin_available=50000.0)
        config = Mock()
        config.account = account
        gate = RiskGate(config)

        alert = Mock()
        alert.detector_name = "TestDetector"
        alert.strategies = ["Bull Call Spread"]
        alert.metrics = {"premium_estimate": 2.5}
        alert.confidence = "high"

        passes, reason = gate._check_margin_gate(alert, "AAPL")
        # Spread premium: 2.5 * 100 = 250
        # 50% rule: 250 * 0.5 = 125
        # 125 / 50000 = 0.25% (well under 50% threshold)
        assert passes is True

    def test_cash_gate_wheel_strategy(self):
        """Test cash gate for Wheel strategy."""
        account = AccountState(cash_available=50000.0)
        config = Mock()
        config.account = account
        gate = RiskGate(config)

        alert = Mock()
        alert.detector_name = "TestDetector"
        alert.strategies = ["Wheel"]
        alert.metrics = {"strike_estimate": 150.0, "quantity": 2}
        alert.confidence = "high"

        passes, reason = gate._check_cash_gate(alert, "AAPL")
        # Cash required: 150 * 100 * 2 = 30000
        # 30000 / 50000 = 60% (exceeds 50% threshold)
        assert passes is False
