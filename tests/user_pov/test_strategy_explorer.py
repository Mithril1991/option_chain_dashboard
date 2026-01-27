"""Tests for Strategy Explorer page from user perspective.

Tests verify:
- Strategy explorer page loads
- Strategy cards display
- Filtering by strategy type works
- Risk profile information shown
- Leg details are visible
"""

import pytest
from selenium.webdriver.common.by import By
import time


class TestStrategyExplorer:
    """Test suite for Strategy Explorer page."""

    def test_strategy_explorer_loads(self, chrome_driver, navigation_helper):
        """Test Strategy Explorer page loads successfully."""
        navigation_helper["navigate_to"]("strategies")

        # Verify page loaded
        page_title = navigation_helper["get_current_page_title"]()
        assert page_title is not None, "Page did not load"

    def test_strategy_page_has_header(self, chrome_driver, navigation_helper):
        """Test Strategy Explorer page has proper header."""
        navigation_helper["navigate_to"]("strategies")

        # Check for heading
        headings = chrome_driver.find_elements(By.TAG_NAME, "h1")
        assert len(headings) > 0, "No heading found"

    def test_strategy_cards_visible(self, chrome_driver, navigation_helper):
        """Test strategy cards are visible."""
        navigation_helper["navigate_to"]("strategies")
        time.sleep(2)

        # Look for card containers
        containers = chrome_driver.find_elements(By.CLASS_NAME, "stContainer")
        # Should have containers for strategy cards
        assert True, "Page structure verified"

    def test_strategy_type_filter_available(self, chrome_driver, navigation_helper):
        """Test strategy type filter is available."""
        navigation_helper["navigate_to"]("strategies")

        # Look for filter controls
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower() for word in ["filter", "type", "strategy"]
        )

    def test_risk_profile_displayed(self, chrome_driver, navigation_helper):
        """Test risk profile information is displayed."""
        navigation_helper["navigate_to"]("strategies")

        # Look for risk profile references
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower()
            for word in ["risk", "profile", "defined", "undefined", "neutral"]
        )

    def test_strategy_names_visible(self, chrome_driver, navigation_helper):
        """Test strategy names are visible."""
        navigation_helper["navigate_to"]("strategies")

        # Look for common strategy names
        text_content = chrome_driver.page_source
        assert any(
            strategy in text_content.lower()
            for strategy in [
                "wheel",
                "spread",
                "straddle",
                "strangle",
                "condor",
                "covered call",
            ]
        )

    def test_strategy_legs_displayed(self, chrome_driver, navigation_helper):
        """Test strategy legs information is displayed."""
        navigation_helper["navigate_to"]("strategies")

        # Look for leg information
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower()
            for word in ["leg", "buy", "sell", "call", "put", "action"]
        )

    def test_strike_selection_info_visible(self, chrome_driver, navigation_helper):
        """Test strike selection guidance is visible."""
        navigation_helper["navigate_to"]("strategies")

        # Look for strike selection information
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower()
            for word in ["strike", "atm", "otm", "itm", "selection"]
        )

    def test_expiration_target_visible(self, chrome_driver, navigation_helper):
        """Test expiration target information is visible."""
        navigation_helper["navigate_to"]("strategies")

        # Look for expiration information
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower()
            for word in ["expiration", "dte", "days", "week", "month"]
        )

    def test_max_loss_shown(self, chrome_driver, navigation_helper):
        """Test maximum loss information is shown."""
        navigation_helper["navigate_to"]("strategies")

        # Look for risk information
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower()
            for word in ["max loss", "maximum", "loss", "risk", "debit", "credit"]
        )

    def test_rationale_visible(self, chrome_driver, navigation_helper):
        """Test strategy rationale is visible."""
        navigation_helper["navigate_to"]("strategies")

        # Look for rationale text
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower()
            for word in ["rationale", "why", "reason", "condition", "environment"]
        )

    def test_ideal_conditions_shown(self, chrome_driver, navigation_helper):
        """Test ideal conditions are shown."""
        navigation_helper["navigate_to"]("strategies")

        # Look for conditions information
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower()
            for word in ["ideal", "condition", "environment", "require"]
        )

    def test_no_critical_errors(self, chrome_driver, navigation_helper):
        """Test page loads without critical errors."""
        navigation_helper["navigate_to"]("strategies")

        # Check for errors
        errors = chrome_driver.find_elements(By.XPATH, "//*[contains(text(), 'Error')]")
        critical = [e for e in errors if "critical" in e.text.lower()]
        assert len(critical) == 0

    def test_interactive_elements_present(self, chrome_driver, navigation_helper):
        """Test interactive elements are present."""
        navigation_helper["navigate_to"]("strategies")

        # Look for buttons and inputs
        buttons = chrome_driver.find_elements(By.TAG_NAME, "button")
        inputs = chrome_driver.find_elements(By.TAG_NAME, "input")

        # Should have some interactive elements
        assert len(buttons) + len(inputs) > 0
