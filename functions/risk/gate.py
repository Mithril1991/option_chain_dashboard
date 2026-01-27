"""
Portfolio-level risk enforcement through configurable risk gates.

This module implements the RiskGate class, which enforces portfolio-level
risk constraints on trading opportunities. It validates opportunities against
three primary gates:

1. MARGIN_GATE: Ensures required margin is < 50% of available margin
2. CASH_GATE: Ensures required cash is < 50% of available cash (for CSP/Wheel)
3. CONCENTRATION_GATE: Ensures position size doesn't exceed 5% of portfolio

Risk Gate Architecture:
    - AlertCandidate flows through RiskGate.passes_risk_gate()
    - Each gate is a separate check with its own logic and messaging
    - If ANY gate fails, the opportunity is rejected
    - Log all gate decisions at INFO level for trading audit trail
    - Account state (margin, cash, positions) loaded from AppConfig

Configuration:
    Key: "risk" in config
    Fields:
        max_concentration_pct (float): Max position as % of portfolio (default: 5.0)
        margin_gate_threshold_pct (float): Margin gate trigger at % of available (default: 50.0)
        cash_gate_threshold_pct (float): Cash gate trigger at % of available (default: 50.0)

Usage:
    from functions.config.settings import get_settings
    from functions.risk.gate import RiskGate
    from functions.detect.base import AlertCandidate

    config = get_settings()
    gate = RiskGate(config)

    alert = AlertCandidate(
        detector_name="VolumeSpikeDetector",
        score=75.0,
        strategies=["Long Call Spread"],
        metrics={...},
        explanation={...},
        confidence="high"
    )

    passes, reason = gate.passes_risk_gate(alert, ticker="AAPL")
    if passes:
        print("Opportunity approved for trading")
    else:
        print(f"Opportunity rejected: {reason}")

    # Get portfolio summary for dashboard
    summary = gate.get_portfolio_summary()
    print(f"Portfolio: {summary['margin_pct_used']}% margin used")
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
import pytz

from functions.config.models import AppConfig
from functions.detect.base import AlertCandidate
from functions.util.logging_setup import get_logger

logger = get_logger(__name__)


# ============================================================================
# ACCOUNT STATE MODELS
# ============================================================================


class AccountPosition:
    """Represents a single position in the trading account."""

    def __init__(self, ticker: str, quantity: float, entry_price: float, current_price: float):
        """
        Initialize a position.

        Args:
            ticker: Stock ticker symbol
            quantity: Number of shares (positive for long, negative for short)
            entry_price: Price at which position was entered
            current_price: Current market price
        """
        self.ticker = ticker
        self.quantity = quantity
        self.entry_price = entry_price
        self.current_price = current_price

    @property
    def position_value(self) -> float:
        """Get current market value of the position."""
        return abs(self.quantity) * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        """Get unrealized profit/loss."""
        if self.quantity > 0:  # Long position
            return self.quantity * (self.current_price - self.entry_price)
        else:  # Short position
            return abs(self.quantity) * (self.entry_price - self.current_price)


class AccountState:
    """Represents the current state of a trading account."""

    def __init__(
        self,
        margin_available: float = 0.0,
        cash_available: float = 0.0,
        positions: Optional[Dict[str, AccountPosition]] = None,
    ):
        """
        Initialize account state.

        Args:
            margin_available: Available buying power for margin (in dollars)
            cash_available: Available cash not tied up in positions (in dollars)
            positions: Dictionary mapping ticker -> AccountPosition
        """
        self.margin_available = float(margin_available)
        self.cash_available = float(cash_available)
        self.positions = positions or {}

    @property
    def total_portfolio_value(self) -> float:
        """Calculate total portfolio value from all positions."""
        return sum(pos.position_value for pos in self.positions.values())

    def get_position_value(self, ticker: str) -> float:
        """Get the current market value of a position by ticker."""
        if ticker not in self.positions:
            return 0.0
        return self.positions[ticker].position_value

    def get_concentration_pct(self, ticker: str) -> float:
        """Get the concentration of a ticker as % of total portfolio."""
        total = self.total_portfolio_value
        if total == 0:
            return 0.0
        position_value = self.get_position_value(ticker)
        return (position_value / total) * 100.0


# ============================================================================
# RISK GATE CLASS
# ============================================================================


class RiskGate:
    """
    Portfolio-level risk enforcement through configurable risk gates.

    Enforces three primary risk gates to ensure trading opportunities
    don't exceed portfolio risk limits:

    1. MARGIN_GATE: Validates margin requirement against available margin
    2. CASH_GATE: Validates cash requirement for secured strategies (CSP, Wheel)
    3. CONCENTRATION_GATE: Validates position size against portfolio limits

    All gates must pass for an opportunity to be approved. If any gate
    fails, the opportunity is rejected with a descriptive reason.

    Attributes:
        config: AppConfig containing portfolio limits and account state
        account: Current account state (margin, cash, positions)
        logger: Logger instance for gate decisions

    Example:
        >>> gate = RiskGate(config)
        >>> passes, reason = gate.passes_risk_gate(alert, ticker="AAPL")
        >>> if not passes:
        ...     print(f"Gate failed: {reason}")
    """

    def __init__(self, config: AppConfig):
        """
        Initialize RiskGate with configuration.

        Loads account state from config and prepares risk gates for validation.

        Args:
            config: AppConfig with portfolio limits and account information

        Raises:
            ValueError: If config is invalid or missing required fields
        """
        if not isinstance(config, AppConfig):
            raise ValueError(
                f"config must be AppConfig instance, got {type(config).__name__}"
            )

        self.config = config
        logger.info("Initializing RiskGate")

        # Load account state from config
        # If config doesn't have account field, create default (no limits enforced)
        if hasattr(config, "account") and config.account:
            self.account = config.account
            logger.info(
                f"Loaded account state: margin=${self.account.margin_available:.2f}, "
                f"cash=${self.account.cash_available:.2f}, "
                f"positions={len(self.account.positions)}"
            )
        else:
            # Create default account with no limits
            self.account = AccountState()
            logger.warning(
                "No account state configured. Risk gates will use default values "
                "(unlimited margin/cash). This is likely a development/test environment."
            )

    def passes_risk_gate(
        self, alert: AlertCandidate, ticker: str
    ) -> tuple[bool, Optional[str]]:
        """
        Check if an opportunity passes all portfolio risk gates.

        Enforces three gates in sequence:
        1. MARGIN_GATE: Check if margin required < 50% of available margin
        2. CASH_GATE: Check if cash required < 50% of available cash
        3. CONCENTRATION_GATE: Check if position doesn't exceed 5% of portfolio

        If ANY gate fails, returns immediately with failure reason.
        If ALL gates pass, returns (True, None).

        Args:
            alert: AlertCandidate opportunity to validate
            ticker: Stock ticker symbol for the position

        Returns:
            tuple[bool, Optional[str]]: (passes, reason)
                - (True, None) if all gates pass
                - (False, reason_string) if any gate fails

        Raises:
            ValueError: If alert or ticker are invalid

        Example:
            >>> passes, reason = gate.passes_risk_gate(alert, "AAPL")
            >>> if not passes:
            ...     logger.error(f"Risk gate failed: {reason}")
        """
        # Validate inputs
        if not isinstance(alert, AlertCandidate):
            raise ValueError(
                f"alert must be AlertCandidate, got {type(alert).__name__}"
            )
        if not isinstance(ticker, str) or not ticker.strip():
            raise ValueError(f"ticker must be non-empty string, got {ticker}")

        logger.info(
            f"Checking risk gates for {ticker} - {alert.detector_name} "
            f"(score={alert.score}, strategies={alert.strategies})"
        )

        # Gate 1: Margin Gate
        margin_passes, margin_reason = self._check_margin_gate(alert, ticker)
        if not margin_passes:
            logger.info(f"MARGIN_GATE FAILED: {margin_reason}")
            return (False, margin_reason)

        # Gate 2: Cash Gate
        cash_passes, cash_reason = self._check_cash_gate(alert, ticker)
        if not cash_passes:
            logger.info(f"CASH_GATE FAILED: {cash_reason}")
            return (False, cash_reason)

        # Gate 3: Concentration Gate
        conc_passes, conc_reason = self._check_concentration_gate(ticker)
        if not conc_passes:
            logger.info(f"CONCENTRATION_GATE FAILED: {conc_reason}")
            return (False, conc_reason)

        # All gates passed
        logger.info(f"All risk gates PASSED for {ticker}")
        return (True, None)

    def _check_margin_gate(self, alert: AlertCandidate, ticker: str) -> tuple[bool, str]:
        """
        Validate margin requirement against available margin.

        Extracts strategy from alert and estimates margin requirement:
        - For spreads (identified by "Spread" in strategy name):
          Margin = debit amount / position size
        - For other strategies:
          Margin = estimated_premium * 100 * 0.5 (conservative 50% rule)

        Position size estimated as 1 contract (100 shares) by default.
        Validates margin requirement < 50% of available margin.

        Args:
            alert: AlertCandidate with strategy information
            ticker: Stock ticker (for logging)

        Returns:
            tuple[bool, str]: (passes, reason)
                - (True, reason_string) if margin requirement OK
                - (False, reason_string) if margin requirement exceeds limit

        Example:
            >>> passes, reason = gate._check_margin_gate(alert, "AAPL")
        """
        # Extract strategy name
        if not alert.strategies or len(alert.strategies) == 0:
            logger.warning(f"No strategies in alert for {ticker}, assuming conservative margin")
            estimated_margin = 5000.0  # Conservative default
            strategy_name = "Unknown"
        else:
            strategy_name = alert.strategies[0]

            # Estimate margin based on strategy type
            if "Spread" in strategy_name:
                # For spreads, estimate debit as premium * 100
                estimated_premium = alert.metrics.get("premium_estimate", 0.5)
                debit_amount = estimated_premium * 100
                position_size = 1  # 1 contract
                estimated_margin = debit_amount / position_size if position_size > 0 else debit_amount
            else:
                # For other strategies, use conservative 50% rule
                estimated_premium = alert.metrics.get("premium_estimate", 1.0)
                estimated_margin = estimated_premium * 100 * 0.5

        # Get configuration thresholds
        margin_threshold_pct = self._get_config_value(
            "risk.margin_gate_threshold_pct", default=50.0
        )

        # Check against available margin
        if self.account.margin_available <= 0:
            # No limit configured, gate passes
            logger.debug(f"Margin check: No limit configured, gate passes")
            return (True, f"Margin gate passed (no limit configured)")

        margin_pct_used = (estimated_margin / self.account.margin_available) * 100.0

        if margin_pct_used < margin_threshold_pct:
            reason = (
                f"Margin gate passed: {strategy_name} requires ${estimated_margin:.2f} "
                f"({margin_pct_used:.1f}% of ${self.account.margin_available:.2f} available)"
            )
            return (True, reason)
        else:
            reason = (
                f"Margin gate FAILED for {ticker}: {strategy_name} requires ${estimated_margin:.2f} "
                f"({margin_pct_used:.1f}% of available), exceeds {margin_threshold_pct}% threshold"
            )
            return (False, reason)

    def _check_cash_gate(self, alert: AlertCandidate, ticker: str) -> tuple[bool, str]:
        """
        Validate cash requirement for strategies that require capital.

        Checks if strategy requires cash (CSP, Wheel) and estimates
        cash requirement:
        - CSP (Cash Secured Put): strike * 100 * qty (100 shares per contract)
        - Wheel: strike * 100 * qty
        - Other strategies: 0 (don't require cash gate check)

        Uses estimated strike from metrics or default 100.

        Args:
            alert: AlertCandidate with strategy information
            ticker: Stock ticker (for logging)

        Returns:
            tuple[bool, str]: (passes, reason)
                - (True, reason_string) if cash requirement OK
                - (False, reason_string) if cash requirement exceeds limit

        Example:
            >>> passes, reason = gate._check_cash_gate(alert, "AAPL")
        """
        # Extract strategy name
        if not alert.strategies or len(alert.strategies) == 0:
            strategy_name = "Unknown"
        else:
            strategy_name = alert.strategies[0]

        # Check if strategy requires cash
        cash_requiring_strategies = ["Cash Secured Put", "CSP", "Wheel"]
        strategy_requires_cash = any(
            strat in strategy_name for strat in cash_requiring_strategies
        )

        if not strategy_requires_cash:
            # Strategy doesn't require cash gate check
            return (True, f"Cash gate passed ({strategy_name} doesn't require cash)")

        # Estimate cash requirement
        estimated_strike = alert.metrics.get("strike_estimate", 100.0)
        quantity = alert.metrics.get("quantity", 1)  # Contracts
        estimated_cash = estimated_strike * 100 * quantity

        # Get configuration thresholds
        cash_threshold_pct = self._get_config_value(
            "risk.cash_gate_threshold_pct", default=50.0
        )

        # Check against available cash
        if self.account.cash_available <= 0:
            # No limit configured, gate passes
            logger.debug(f"Cash check: No limit configured, gate passes")
            return (True, f"Cash gate passed (no limit configured)")

        cash_pct_used = (estimated_cash / self.account.cash_available) * 100.0

        if cash_pct_used < cash_threshold_pct:
            reason = (
                f"Cash gate passed: {strategy_name} requires ${estimated_cash:.2f} "
                f"({cash_pct_used:.1f}% of ${self.account.cash_available:.2f} available)"
            )
            return (True, reason)
        else:
            reason = (
                f"Cash gate FAILED for {ticker}: {strategy_name} requires ${estimated_cash:.2f} "
                f"({cash_pct_used:.1f}% of available), exceeds {cash_threshold_pct}% threshold"
            )
            return (False, reason)

    def _check_concentration_gate(self, ticker: str) -> tuple[bool, str]:
        """
        Validate position doesn't exceed concentration limits.

        Calculates current position value for ticker as a percentage of
        total portfolio value. Fails if concentration > max_concentration_pct
        (default 5%).

        Note: This checks EXISTING position concentration, not NEW position
        to be taken. Implementations may want to estimate NEW position size.

        Args:
            ticker: Stock ticker symbol

        Returns:
            tuple[bool, str]: (passes, reason)
                - (True, reason_string) if concentration OK
                - (False, reason_string) if concentration exceeds limit

        Example:
            >>> passes, reason = gate._check_concentration_gate("AAPL")
        """
        # Get configuration threshold
        max_concentration_pct = self._get_config_value(
            "risk.max_concentration_pct", default=5.0
        )

        # Get current concentration for ticker
        concentration_pct = self.account.get_concentration_pct(ticker)

        if concentration_pct <= max_concentration_pct:
            reason = (
                f"Concentration gate passed: {ticker} is {concentration_pct:.2f}% "
                f"of portfolio (limit: {max_concentration_pct}%)"
            )
            return (True, reason)
        else:
            reason = (
                f"Concentration gate FAILED for {ticker}: {concentration_pct:.2f}% "
                f"of portfolio exceeds {max_concentration_pct}% limit"
            )
            return (False, reason)

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Generate a comprehensive portfolio summary for dashboard display.

        Returns account metrics including margin usage, cash usage, and
        concentration by ticker. Handles missing account data gracefully.

        Returns:
            Dict[str, Any]: Portfolio summary with keys:
                - margin_available (float): Available buying power
                - cash_available (float): Available cash
                - margin_pct_used (float): % of margin in use
                - cash_pct_used (float): % of cash in use
                - total_portfolio_value (float): Sum of all positions
                - concentration_by_ticker (Dict[str, float]): % of portfolio by ticker
                - timestamp_utc (str): ISO 8601 timestamp of summary generation

        Example:
            >>> summary = gate.get_portfolio_summary()
            >>> print(f"Margin used: {summary['margin_pct_used']}%")
            >>> print(f"Portfolio value: ${summary['total_portfolio_value']:.2f}")
        """
        # Calculate portfolio value
        total_portfolio_value = self.account.total_portfolio_value

        # Calculate margin usage (if available margin is set)
        margin_pct_used = 0.0
        if self.account.margin_available > 0:
            margin_total = self.account.margin_available + (total_portfolio_value * 0.2)  # Rough estimate
            if margin_total > 0:
                margin_pct_used = ((margin_total - self.account.margin_available) / margin_total) * 100

        # Calculate cash usage (if available cash is set)
        cash_pct_used = 0.0
        if self.account.cash_available > 0:
            total_capital = self.account.cash_available + total_portfolio_value
            if total_capital > 0:
                cash_pct_used = ((total_capital - self.account.cash_available) / total_capital) * 100

        # Build concentration by ticker
        concentration_by_ticker = {}
        if total_portfolio_value > 0:
            for ticker, position in self.account.positions.items():
                concentration_by_ticker[ticker] = (
                    (position.position_value / total_portfolio_value) * 100.0
                )

        # Generate timestamp
        timestamp_utc = datetime.now(pytz.UTC).isoformat()

        return {
            "margin_available": float(self.account.margin_available),
            "cash_available": float(self.account.cash_available),
            "margin_pct_used": float(margin_pct_used),
            "cash_pct_used": float(cash_pct_used),
            "total_portfolio_value": float(total_portfolio_value),
            "concentration_by_ticker": concentration_by_ticker,
            "timestamp_utc": timestamp_utc,
        }

    def _get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with dot notation and fallback to default.

        Safely navigates nested configuration dictionaries using dot notation.
        Returns default if key not found or config is missing.

        Args:
            key: Configuration key using dot notation (e.g., "risk.max_concentration_pct")
            default: Default value if key not found

        Returns:
            Configuration value or default if not found

        Example:
            >>> val = gate._get_config_value("risk.max_concentration_pct", default=5.0)
        """
        try:
            # Handle direct attribute access for known config paths
            if key == "risk.max_concentration_pct":
                return getattr(self.config, "max_concentration_pct", default)
            elif key == "risk.margin_gate_threshold_pct":
                return getattr(self.config, "margin_gate_threshold_pct", default)
            elif key == "risk.cash_gate_threshold_pct":
                return getattr(self.config, "cash_gate_threshold_pct", default)
            else:
                # Fallback for other keys
                keys = key.split(".")
                value = self.config
                for k in keys:
                    value = getattr(value, k, None)
                    if value is None:
                        return default
                return value
        except (AttributeError, KeyError, TypeError):
            return default
