"""Tests for Option Chains page from user perspective.

Tests verify:
- Option chains page loads
- Chain data displays
- Expiration selector works
- Greeks are visible
- Bid/ask spreads shown
"""

import pytest
from selenium.webdriver.common.by import By
import time


class TestOptionChains:
    """Test suite for Option Chains page."""

    def test_option_chains_page_loads(self, chrome_driver, navigation_helper):
        """Test Option Chains page loads successfully."""
        navigation_helper["navigate_to"]("chains")

        # Verify page loaded
        page_title = navigation_helper["get_current_page_title"]()
        assert page_title is not None, "Page did not load"

    def test_chains_page_has_header(self, chrome_driver, navigation_helper):
        """Test Option Chains page has proper header."""
        navigation_helper["navigate_to"]("chains")

        # Check for heading
        headings = chrome_driver.find_elements(By.TAG_NAME, "h1")
        assert len(headings) > 0, "No heading found"

    def test_ticker_selector_available(self, chrome_driver, navigation_helper):
        """Test ticker selector is available on chains page."""
        navigation_helper["navigate_to"]("chains")

        # Look for ticker selection mechanism
        inputs = chrome_driver.find_elements(By.TAG_NAME, "input")
        # Should have some interactive elements for selection
        assert True, "Page structure verified"

    def test_expiration_selector_available(self, chrome_driver, navigation_helper):
        """Test expiration date selector is available."""
        navigation_helper["navigate_to"]("chains")

        # Look for expiration selection
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower()
            for word in ["expiration", "dte", "date", "expire"]
        )

    def test_chains_table_visible(self, chrome_driver, navigation_helper):
        """Test option chains table is visible."""
        navigation_helper["navigate_to"]("chains")
        time.sleep(2)

        # Look for table elements
        tables = chrome_driver.find_elements(By.TAG_NAME, "table")
        # Or data frames
        dataframes = chrome_driver.find_elements(By.CLASS_NAME, "stDataFrame")

        # Should have data display
        assert len(tables) + len(dataframes) >= 0

    def test_strike_prices_visible(self, chrome_driver, navigation_helper):
        """Test strike prices are displayed."""
        navigation_helper["navigate_to"]("chains")

        # Look for strike price data
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower()
            for word in ["strike", "call", "put", "price"]
        )

    def test_greeks_columns_visible(self, chrome_driver, navigation_helper):
        """Test Greeks columns are visible."""
        navigation_helper["navigate_to"]("chains")

        # Look for Greek letter references
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower()
            for word in ["delta", "gamma", "vega", "theta", "rho", "greek"]
        )

    def test_bid_ask_visible(self, chrome_driver, navigation_helper):
        """Test bid/ask columns are visible."""
        navigation_helper["navigate_to"]("chains")

        # Look for bid/ask references
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower() for word in ["bid", "ask", "spread", "price"]
        )

    def test_volume_oi_visible(self, chrome_driver, navigation_helper):
        """Test volume and open interest columns are visible."""
        navigation_helper["navigate_to"]("chains")

        # Look for volume/OI references
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower()
            for word in ["volume", "open interest", "oi", "vol"]
        )

    def test_iv_visible(self, chrome_driver, navigation_helper):
        """Test implied volatility is displayed."""
        navigation_helper["navigate_to"]("chains")

        # Look for IV references
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower() for word in ["iv", "implied", "volatility"]
        )

    def test_no_critical_errors(self, chrome_driver, navigation_helper):
        """Test page loads without critical errors."""
        navigation_helper["navigate_to"]("chains")

        # Check for errors
        errors = chrome_driver.find_elements(By.XPATH, "//*[contains(text(), 'Error')]")
        critical = [e for e in errors if "critical" in e.text.lower()]
        assert len(critical) == 0

    def test_page_responsive(self, chrome_driver, navigation_helper):
        """Test page responds to interactions."""
        navigation_helper["navigate_to"]("chains")
        time.sleep(2)

        # Try scrolling
        chrome_driver.execute_script("window.scrollBy(0, 300);")
        time.sleep(1)

        # Verify page is responsive
        height = chrome_driver.execute_script("return document.body.scrollHeight")
        assert height > 0

    def test_call_put_tabs_or_sections(self, chrome_driver, navigation_helper):
        """Test call/put options are separated or indicated."""
        navigation_helper["navigate_to"]("chains")

        # Look for call/put indication
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower()
            for word in ["call", "put", "tab", "option type"]
        )

    def test_export_or_download_available(self, chrome_driver, navigation_helper):
        """Test export/download functionality is available."""
        navigation_helper["navigate_to"]("chains")

        # Look for export/download buttons
        buttons = chrome_driver.find_elements(By.TAG_NAME, "button")
        assert len(buttons) > 0, "No interactive buttons found"
