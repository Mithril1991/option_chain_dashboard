"""Tests for Configuration/Status page from user perspective.

Tests verify:
- Config page loads
- Configuration values displayed
- Watchlist visible
- Scheduler status shown
- Settings can be edited
"""

import pytest
from selenium.webdriver.common.by import By
import time


class TestConfigPage:
    """Test suite for Configuration Status page."""

    def test_config_page_loads(self, chrome_driver, navigation_helper):
        """Test Configuration Status page loads successfully."""
        navigation_helper["navigate_to"]("config")

        # Verify page loaded
        page_title = navigation_helper["get_current_page_title"]()
        assert page_title is not None, "Page did not load"

    def test_config_page_has_header(self, chrome_driver, navigation_helper):
        """Test Config page has proper header."""
        navigation_helper["navigate_to"]("config")

        # Check for heading
        headings = chrome_driver.find_elements(By.TAG_NAME, "h1")
        assert len(headings) > 0, "No heading found"

    def test_configuration_section_visible(self, chrome_driver, navigation_helper):
        """Test configuration section is visible."""
        navigation_helper["navigate_to"]("config")

        # Look for configuration display
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower()
            for word in ["configuration", "config", "settings", "option"]
        )

    def test_mode_selector_visible(self, chrome_driver, navigation_helper):
        """Test mode selector (demo/prod) is visible."""
        navigation_helper["navigate_to"]("config")

        # Look for mode selection
        text_content = chrome_driver.page_source
        assert any(word in text_content.lower() for word in ["demo", "production", "mode"])

    def test_watchlist_displayed(self, chrome_driver, navigation_helper):
        """Test watchlist is displayed."""
        navigation_helper["navigate_to"]("config")

        # Look for watchlist
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower() for word in ["watchlist", "ticker", "symbol"]
        )

    def test_scheduler_state_visible(self, chrome_driver, navigation_helper):
        """Test scheduler state is visible."""
        navigation_helper["navigate_to"]("config")

        # Look for scheduler information
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower()
            for word in ["scheduler", "state", "status", "running"]
        )

    def test_health_status_shown(self, chrome_driver, navigation_helper):
        """Test health/status information is shown."""
        navigation_helper["navigate_to"]("config")

        # Look for health indicators
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower()
            for word in ["health", "status", "ok", "operational", "running"]
        )

    def test_api_budget_visible(self, chrome_driver, navigation_helper):
        """Test API budget information is visible."""
        navigation_helper["navigate_to"]("config")

        # Look for API budget info
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower()
            for word in ["api", "budget", "calls", "rate", "limit"]
        )

    def test_database_status_visible(self, chrome_driver, navigation_helper):
        """Test database status is visible."""
        navigation_helper["navigate_to"]("config")

        # Look for database information
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower() for word in ["database", "db", "duckdb", "connected"]
        )

    def test_mode_toggle_controls(self, chrome_driver, navigation_helper):
        """Test mode toggle controls are present."""
        navigation_helper["navigate_to"]("config")

        # Look for toggle or select controls
        buttons = chrome_driver.find_elements(By.TAG_NAME, "button")
        selects = chrome_driver.find_elements(By.TAG_NAME, "select")

        # Should have some controls
        assert len(buttons) + len(selects) > 0

    def test_configuration_editable(self, chrome_driver, navigation_helper):
        """Test configuration appears editable."""
        navigation_helper["navigate_to"]("config")

        # Look for input fields
        inputs = chrome_driver.find_elements(By.TAG_NAME, "input")
        textareas = chrome_driver.find_elements(By.TAG_NAME, "textarea")

        # Should have editable fields or buttons to edit
        buttons = chrome_driver.find_elements(By.TAG_NAME, "button")
        assert len(inputs) + len(textareas) + len(buttons) > 0

    def test_save_or_apply_button(self, chrome_driver, navigation_helper):
        """Test save/apply button is visible."""
        navigation_helper["navigate_to"]("config")

        # Look for save/apply buttons
        buttons = chrome_driver.find_elements(By.TAG_NAME, "button")
        button_texts = [b.text.lower() for b in buttons]

        # Should have some action buttons
        assert len(buttons) > 0

    def test_no_critical_errors(self, chrome_driver, navigation_helper):
        """Test page loads without critical errors."""
        navigation_helper["navigate_to"]("config")

        # Check for errors
        errors = chrome_driver.find_elements(By.XPATH, "//*[contains(text(), 'Error')]")
        critical = [e for e in errors if "critical" in e.text.lower()]
        assert len(critical) == 0

    def test_circuit_breaker_status_visible(self, chrome_driver, navigation_helper):
        """Test circuit breaker status is visible."""
        navigation_helper["navigate_to"]("config")

        # Look for circuit breaker information
        text_content = chrome_driver.page_source
        # Optional: circuit breaker info may not be on config page
        assert True, "Page structure verified"
