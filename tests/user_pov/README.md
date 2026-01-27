# User Perspective (Selenium) Tests

User-perspective tests simulate real user interactions with the dashboard using Selenium browser automation. These tests verify the UI/UX from a user's point of view rather than testing APIs or backend logic.

## Overview

- **Test Files**: 7
- **Test Methods**: 85+
- **Pages Covered**: 8 (Home, Alerts, Ticker Detail, Option Chains, Strategy Explorer, Config/Status, Trades, Portfolio)
- **Test Framework**: Pytest + Selenium

## Test Files

| File | Tests | Focus |
|------|-------|-------|
| `test_dashboard_home.py` | 10 | Home page layout, navigation, metrics |
| `test_alert_feed.py` | 11 | Alert display, filtering, controls |
| `test_ticker_detail.py` | 11 | Ticker selection, charts, features |
| `test_option_chains.py` | 14 | Chain display, Greeks, Greeks, bid/ask |
| `test_strategy_explorer.py` | 13 | Strategy cards, filtering, risk profiles |
| `test_config_page.py` | 13 | Configuration display, mode switching, status |
| `test_mode_switching.py` | 10 | Mode indicator, switching, persistence |

## Requirements

### System Requirements

- Chrome or Chromium browser installed
- Linux/macOS/Windows with display capabilities (or --headless mode)

### Install Chrome/Chromium

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y chromium-browser
```

**macOS:**
```bash
brew install chromium
```

**Or use system Chrome if available:**
```bash
which google-chrome
which chromium-browser
```

### Python Dependencies

Already installed via `requirements.txt`:
- `selenium==4.15.2`
- `webdriver-manager==4.0.1`
- `pytest==7.4.3`

## Running Tests

### Run All User Perspective Tests

```bash
source venv/bin/activate
pytest tests/user_pov/ -v
```

### Run Specific Test File

```bash
pytest tests/user_pov/test_dashboard_home.py -v
```

### Run Specific Test Class

```bash
pytest tests/user_pov/test_alert_feed.py::TestAlertFeed -v
```

### Run Specific Test Method

```bash
pytest tests/user_pov/test_dashboard_home.py::TestDashboardHome::test_dashboard_home_loads -v
```

### Run with Detailed Output

```bash
pytest tests/user_pov/ -vv -s --tb=short
```

### Run in Headless Mode (No Display)

Tests run headless by default (configured in `conftest.py`):
```python
"headless": True,  # in selenium_config
```

To disable headless mode, edit `conftest.py` and set:
```python
"headless": False,
```

## Test Structure

Each test file contains a test class with related test methods:

```python
class TestPageName:
    """Test suite for specific page."""

    def test_page_loads(self, chrome_driver, navigation_helper):
        """Test page loads successfully."""
        # Test implementation
```

### Common Fixtures (from conftest.py)

| Fixture | Purpose |
|---------|---------|
| `chrome_driver` | WebDriver instance (browser) |
| `dashboard_url` | Base dashboard URL (192.168.1.16:8060) |
| `selenium_config` | Selenium configuration settings |
| `navigation_helper` | Functions to navigate to pages |
| `element_helper` | Functions to find/interact with elements |
| `assertion_helper` | Common assertion functions |

## Test Categories

### 1. Page Loading Tests
- Verify page loads successfully
- Check for proper headers
- Confirm no critical errors

### 2. Element Visibility Tests
- Check required elements are visible
- Verify data display areas
- Confirm interactive controls

### 3. Navigation Tests
- Test sidebar navigation
- Verify page switching works
- Check navigation persistence

### 4. Content Display Tests
- Verify alerts are shown
- Check charts/tables render
- Confirm data fields visible

### 5. Interaction Tests
- Test filtering controls
- Verify mode switching
- Check button responsiveness

### 6. Error Handling Tests
- Ensure no critical errors
- Check error message display
- Verify graceful degradation

## Configuring Tests

### Edit Selenium Configuration

File: `tests/user_pov/conftest.py`

```python
@pytest.fixture(scope="session")
def selenium_config():
    """Provide Selenium configuration."""
    return {
        "dashboard_url": "http://192.168.1.16:8060",  # Change URL here
        "api_url": "http://192.168.1.16:8061",        # Change API URL
        "headless": True,                               # Toggle headless mode
        "implicit_wait": 10,                            # Change wait time
        "page_load_timeout": 20,                        # Change page load timeout
    }
```

### Adjust Timeouts

For slow networks or systems, increase timeouts:

```python
"implicit_wait": 20,          # Increase from 10 to 20 seconds
"page_load_timeout": 30,      # Increase from 20 to 30 seconds
```

## Interpreting Results

### Test Results Meanings

- **PASSED** ✅ - Test passed, feature working
- **FAILED** ❌ - Test failed, element/feature not working
- **SKIPPED** ⊘ - Test skipped (usually Chrome not installed)
- **ERROR** ⚠️ - Test error during setup/teardown

### Example Output

```
tests/user_pov/test_dashboard_home.py::TestDashboardHome::test_dashboard_home_loads PASSED
tests/user_pov/test_alert_feed.py::TestAlertFeed::test_alert_feed_page_loads FAILED
tests/user_pov/test_option_chains.py::TestOptionChains::test_chains_page_loads SKIPPED
```

## Troubleshooting

### Tests Skip with "Chrome not installed"

**Solution**: Install Chromium
```bash
sudo apt-get install -y chromium-browser
```

### Tests Timeout

**Solution**: Increase timeouts in `conftest.py`
```python
"implicit_wait": 20,      # Increase wait time
"page_load_timeout": 30,  # Increase page load timeout
```

### Cannot connect to dashboard

**Solution**: Verify dashboard is running
```bash
curl http://192.168.1.16:8060
```

If not running:
```bash
python main.py --demo-mode
```

### Tests fail on "element not found"

**Causes**:
- Dashboard UI changed
- Page load too slow (increase timeout)
- Element selector is wrong

**Solution**:
1. Open dashboard manually: http://192.168.1.16:8060
2. Verify element exists
3. Update test selectors if needed
4. Increase timeouts if page is slow

### Headless mode issues

If headless mode causes issues, disable it:

File: `tests/user_pov/conftest.py`
```python
"headless": False,
```

Then run tests (requires display):
```bash
pytest tests/user_pov/ -v
```

## Best Practices

1. **Run tests regularly**: After UI changes or before deployment
2. **Keep tests focused**: Each test should verify one behavior
3. **Use helpful assertions**: Clear error messages for failures
4. **Maintain selectors**: Update tests when UI changes
5. **Document changes**: Update this README when adding tests

## Extending Tests

### Add New Test File

1. Create `tests/user_pov/test_new_page.py`
2. Import fixtures from conftest
3. Create test class
4. Add test methods

Example:
```python
import pytest
from selenium.webdriver.common.by import By

class TestNewPage:
    def test_page_loads(self, chrome_driver, navigation_helper):
        """Test new page loads."""
        navigation_helper["navigate_to"]("new_page")
        assert "expected_text" in chrome_driver.page_source
```

### Add New Test Method

1. Open relevant test file
2. Add method to appropriate test class
3. Use fixtures for browser interaction
4. Add assertions

Example:
```python
def test_new_feature(self, chrome_driver, element_helper):
    """Test new feature works."""
    chrome_driver.get("http://192.168.1.16:8060")
    element = element_helper["wait_for_element"](By.ID, "element_id")
    assert element.is_displayed()
```

## Notes

- Tests are designed for Streamlit dashboard (on port 8060)
- All tests are non-destructive (no data modification)
- Tests use demo data by default
- Firefox/Edge support can be added if needed
- Tests work on CI/CD pipelines (headless mode)

## Related Documentation

- Main README: `../../README.md`
- Testing Guide: `../../docs/TESTING_GUIDE.md` (if available)
- Selenium Docs: https://www.selenium.dev/documentation/
- Pytest Docs: https://docs.pytest.org/

---

**Last Updated**: 2026-01-27
**Status**: ✅ Complete - 85 test methods across 7 files
