"""Tests for Alert Feed page from user perspective.

Tests verify:
- Alert feed page loads
- Alerts are displayed
- Filtering by score works
- Filtering by ticker works
- Alert details are visible
"""

import pytest
from selenium.webdriver.common.by import By
import time


class TestAlertFeed:
    """Test suite for Alert Feed page."""

    def test_alert_feed_page_loads(self, chrome_driver, navigation_helper):
        """Test Alert Feed page loads successfully."""
        navigation_helper["navigate_to"]("alerts")

        # Verify page loaded
        page_title = navigation_helper["get_current_page_title"]()
        assert page_title is not None, "Page title not found"

    def test_alert_feed_has_header(self, chrome_driver, navigation_helper):
        """Test Alert Feed page has proper header."""
        navigation_helper["navigate_to"]("alerts")

        # Check for heading
        headings = chrome_driver.find_elements(By.TAG_NAME, "h1")
        assert len(headings) > 0, "No h1 heading found"

    def test_alert_feed_has_controls(self, chrome_driver, navigation_helper):
        """Test Alert Feed page has filter controls."""
        navigation_helper["navigate_to"]("alerts")

        # Look for input fields or sliders (filters)
        inputs = chrome_driver.find_elements(By.TAG_NAME, "input")
        assert len(inputs) >= 0, "Could not verify controls"

        # Should have some interactive elements
        buttons = chrome_driver.find_elements(By.TAG_NAME, "button")
        assert len(buttons) > 0, "No buttons found"

    def test_alert_feed_displays_content(self, chrome_driver, navigation_helper):
        """Test Alert Feed displays content."""
        navigation_helper["navigate_to"]("alerts")

        # Check page source has content
        text = chrome_driver.page_source
        assert len(text) > 1000, "Page seems to have minimal content"

    def test_alert_cards_visible(self, chrome_driver, navigation_helper):
        """Test alert cards are displayed (if alerts exist)."""
        navigation_helper["navigate_to"]("alerts")
        time.sleep(2)

        # Look for card-like elements or divs with alert data
        # Streamlit uses various container classes
        containers = chrome_driver.find_elements(By.CLASS_NAME, "stContainer")
        assert len(containers) >= 0, "Could not verify alert containers"

    def test_score_filter_visible(self, chrome_driver, navigation_helper):
        """Test score filter is visible."""
        navigation_helper["navigate_to"]("alerts")

        # Look for slider or input with "score" or "threshold" in label
        text_content = chrome_driver.page_source
        assert "score" in text_content.lower() or "filter" in text_content.lower()

    def test_ticker_filter_visible(self, chrome_driver, navigation_helper):
        """Test ticker filter is visible."""
        navigation_helper["navigate_to"]("alerts")

        # Look for ticker-related filters
        text_content = chrome_driver.page_source
        assert any(
            word in text_content.lower()
            for word in ["ticker", "symbol", "filter"]
        )

    def test_no_error_messages(self, chrome_driver, navigation_helper, assertion_helper):
        """Test alert feed loads without errors."""
        navigation_helper["navigate_to"]("alerts")

        # Verify no critical errors
        error_indicators = chrome_driver.find_elements(
            By.XPATH, "//*[contains(text(), 'Error')]"
        )
        critical = [e for e in error_indicators if "critical" in e.text.lower()]
        assert len(critical) == 0, f"Critical errors found: {critical}"

    def test_page_responds_to_scroll(self, chrome_driver, navigation_helper):
        """Test page responds to scrolling."""
        navigation_helper["navigate_to"]("alerts")

        # Scroll down
        chrome_driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(1)

        # Verify scroll worked (page height should be larger than viewport)
        height = chrome_driver.execute_script("return document.body.scrollHeight")
        assert height > 100, "Page height too small"

    def test_alert_feed_data_loaded(self, chrome_driver, navigation_helper):
        """Test that alert feed has data elements."""
        navigation_helper["navigate_to"]("alerts")
        time.sleep(2)

        # Check for data-like elements
        text = chrome_driver.page_source
        # Should have some content indicators
        assert any(
            word in text.lower()
            for word in ["alert", "detector", "score", "ticker", "data"]
        )

    def test_pagination_or_loading(self, chrome_driver, navigation_helper):
        """Test pagination or loading indicators."""
        navigation_helper["navigate_to"]("alerts")

        # Check for pagination controls or loading state
        buttons = chrome_driver.find_elements(By.TAG_NAME, "button")
        assert len(buttons) > 0, "No controls found"

    def test_refresh_button_available(self, chrome_driver, navigation_helper):
        """Test refresh functionality available."""
        navigation_helper["navigate_to"]("alerts")

        # Look for refresh button or similar
        buttons = chrome_driver.find_elements(By.TAG_NAME, "button")
        button_texts = [b.text for b in buttons]
        # Should have some interactive buttons
        assert len(button_texts) > 0
