"""Pytest configuration and fixtures for user perspective tests.

These fixtures provide browser instances and utility functions for
user-perspective (Selenium) testing of the Streamlit dashboard.
"""

import pytest
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service


@pytest.fixture(scope="session")
def selenium_config():
    """Provide Selenium configuration."""
    return {
        "dashboard_url": "http://192.168.1.16:8060",
        "api_url": "http://192.168.1.16:8061",
        "headless": True,  # Run tests in headless mode
        "implicit_wait": 10,  # seconds
        "page_load_timeout": 20,  # seconds
    }


@pytest.fixture
def chrome_driver(selenium_config):
    """Create and configure Chrome WebDriver for each test.

    Yields:
        WebDriver: Configured Chrome WebDriver instance

    Note:
        Chrome/Chromium must be installed on the system for these tests to run.
        Install with: sudo apt-get install chromium-browser
    """
    import subprocess

    options = ChromeOptions()

    if selenium_config["headless"]:
        options.add_argument("--headless")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")

    # Check if Chrome is available
    try:
        result = subprocess.run(
            ["which", "chromium-browser"],
            capture_output=True,
            timeout=5
        )
        chrome_path = result.stdout.decode().strip()
        if chrome_path:
            options.binary_location = chrome_path
    except Exception:
        pass  # Will use default Chrome path

    try:
        # Create driver with proper service
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        driver.implicitly_wait(selenium_config["implicit_wait"])
        driver.set_page_load_timeout(selenium_config["page_load_timeout"])

        yield driver

        # Cleanup
        driver.quit()
    except Exception as e:
        if "cannot find Chrome binary" in str(e):
            pytest.skip(
                "Chrome/Chromium not installed. "
                "Install with: sudo apt-get install chromium-browser"
            )
        raise


@pytest.fixture
def dashboard_url(selenium_config):
    """Provide dashboard base URL."""
    return selenium_config["dashboard_url"]


@pytest.fixture
def wait_helper(chrome_driver, selenium_config):
    """Provide helper for explicit waits.

    Returns:
        WebDriverWait: Wait instance for explicit waits
    """
    return WebDriverWait(chrome_driver, selenium_config["implicit_wait"])


@pytest.fixture
def navigation_helper(chrome_driver, dashboard_url):
    """Provide navigation helper for common page navigation tasks.

    Returns:
        dict: Navigation helper functions
    """
    def navigate_to(page_name):
        """Navigate to a specific page."""
        pages = {
            "home": f"{dashboard_url}",
            "alerts": f"{dashboard_url}/?page=Alert+Feed",
            "ticker": f"{dashboard_url}/?page=Ticker+Detail",
            "chains": f"{dashboard_url}/?page=Option+Chains",
            "strategies": f"{dashboard_url}/?page=Strategy+Explorer",
            "config": f"{dashboard_url}/?page=Config+Status",
            "trades": f"{dashboard_url}/?page=Trade+Management",
            "portfolio": f"{dashboard_url}/?page=Portfolio+Overview",
        }
        url = pages.get(page_name, f"{dashboard_url}")
        chrome_driver.get(url)
        time.sleep(2)  # Allow page to load

    def get_current_page_title():
        """Get current page title."""
        try:
            return chrome_driver.find_element(By.TAG_NAME, "h1").text
        except:
            return None

    return {
        "navigate_to": navigate_to,
        "get_current_page_title": get_current_page_title,
    }


@pytest.fixture
def element_helper(chrome_driver, wait_helper):
    """Provide helper for finding and interacting with elements.

    Returns:
        dict: Element helper functions
    """
    def find_element_by_text(text, tag="button"):
        """Find element by text content."""
        xpath = f"//{tag}[contains(text(), '{text}')]"
        return chrome_driver.find_element(By.XPATH, xpath)

    def wait_for_element(by, value, timeout=10):
        """Wait for element to be present."""
        return WebDriverWait(chrome_driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )

    def wait_for_text(by, value, text, timeout=10):
        """Wait for element to contain specific text."""
        element = wait_for_element(by, value, timeout)
        WebDriverWait(chrome_driver, timeout).until(
            lambda driver: text in element.text
        )
        return element

    def click_element(element):
        """Click element with scroll into view."""
        chrome_driver.execute_script("arguments[0].scrollIntoView();", element)
        element.click()

    def get_element_text(by, value):
        """Get text from element."""
        element = chrome_driver.find_element(by, value)
        return element.text

    def is_element_visible(by, value):
        """Check if element is visible."""
        try:
            element = chrome_driver.find_element(by, value)
            return element.is_displayed()
        except:
            return False

    return {
        "find_element_by_text": find_element_by_text,
        "wait_for_element": wait_for_element,
        "wait_for_text": wait_for_text,
        "click_element": click_element,
        "get_element_text": get_element_text,
        "is_element_visible": is_element_visible,
    }


@pytest.fixture
def assertion_helper(chrome_driver, element_helper):
    """Provide helper for common assertions.

    Returns:
        dict: Assertion helper functions
    """
    def assert_page_loaded():
        """Assert page has loaded (basic check)."""
        assert chrome_driver.execute_script("return document.readyState") == "complete"

    def assert_element_visible(by, value):
        """Assert element is visible."""
        assert element_helper["is_element_visible"](by, value), f"Element {value} not visible"

    def assert_element_contains_text(by, value, text):
        """Assert element contains specific text."""
        element = chrome_driver.find_element(by, value)
        assert text in element.text, f"'{text}' not found in '{element.text}'"

    def assert_no_errors():
        """Assert no error messages visible."""
        error_elements = chrome_driver.find_elements(By.XPATH, "//*[contains(text(), 'Error')]")
        assert len(error_elements) == 0, f"Found {len(error_elements)} error messages"

    def assert_multiple_elements_exist(by, value, min_count=1):
        """Assert multiple elements exist."""
        elements = chrome_driver.find_elements(by, value)
        assert len(elements) >= min_count, f"Expected >={min_count} elements, found {len(elements)}"

    return {
        "assert_page_loaded": assert_page_loaded,
        "assert_element_visible": assert_element_visible,
        "assert_element_contains_text": assert_element_contains_text,
        "assert_no_errors": assert_no_errors,
        "assert_multiple_elements_exist": assert_multiple_elements_exist,
    }
