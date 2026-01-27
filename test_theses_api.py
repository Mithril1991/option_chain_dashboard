#!/usr/bin/env python
"""
Test script to verify thesis API endpoints are working correctly.

This script:
1. Verifies the API server can load thesis endpoints
2. Tests GET /tickers/list endpoint
3. Tests GET /tickers/{ticker}/thesis endpoint
4. Tests GET /tickers/{ticker}/risks endpoint
5. Tests GET /tickers/{ticker}/notes endpoint
6. Tests 404 handling for missing tickers
7. Prints test results

Run with:
    source venv/bin/activate
    python test_theses_api.py

Note: Requires the API server to be running on port 8061
"""

import sys
import requests
import json
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8061"
TICKERS = ["SOFI", "AMD", "NVDA", "TSLA", "AAPL"]
TEST_ENDPOINTS = ["thesis", "risks", "notes"]

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def test_endpoint(method, url, expected_status=200):
    """Test an API endpoint and return result."""
    try:
        response = requests.request(method, url, timeout=5)
        success = response.status_code == expected_status
        return {
            "success": success,
            "status_code": response.status_code,
            "response": response.json() if response.headers.get("content-type") == "application/json" else response.text,
        }
    except Exception as e:
        return {
            "success": False,
            "status_code": None,
            "response": str(e),
        }


def print_test_result(test_name, result, expected_status=200):
    """Print formatted test result."""
    if result["success"]:
        print(f"{GREEN}✓ PASS{RESET}: {test_name} (Status: {result['status_code']})")
        return True
    else:
        print(f"{RED}✗ FAIL{RESET}: {test_name} (Status: {result['status_code']}, Expected: {expected_status})")
        if isinstance(result["response"], dict):
            print(f"       Response: {json.dumps(result['response'], indent=2)[:100]}")
        else:
            print(f"       Response: {str(result['response'])[:100]}")
        return False


def main():
    """Run all tests."""
    print(f"\n{YELLOW}Testing Thesis API Endpoints{RESET}")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Tickers: {', '.join(TICKERS)}\n")

    passed = 0
    failed = 0

    # Test 1: GET /tickers/list
    print(f"\n{YELLOW}Test 1: List Tickers{RESET}")
    result = test_endpoint("GET", f"{API_BASE_URL}/tickers/list")
    if print_test_result("GET /tickers/list", result):
        passed += 1
        # Verify response structure
        if isinstance(result["response"], dict) and "tickers" in result["response"]:
            print(f"       Found {result['response']['total_count']} tickers")
            for ticker_info in result["response"]["tickers"]:
                print(
                    f"       - {ticker_info['ticker']}: "
                    f"thesis={ticker_info['has_thesis']}, "
                    f"risks={ticker_info['has_risks']}, "
                    f"notes={ticker_info['has_notes']}"
                )
    else:
        failed += 1

    # Test 2-4: Get thesis, risks, notes for each ticker
    print(f"\n{YELLOW}Test 2-4: Get Thesis/Risks/Notes for Each Ticker{RESET}")
    for ticker in TICKERS:
        for endpoint in TEST_ENDPOINTS:
            url = f"{API_BASE_URL}/tickers/{ticker}/{endpoint}"
            result = test_endpoint("GET", url)
            if print_test_result(f"GET /tickers/{ticker}/{endpoint}", result):
                passed += 1
                # Verify response structure
                if isinstance(result["response"], dict):
                    content_len = len(result["response"].get("content", ""))
                    print(f"       Content length: {content_len} bytes, Ticker: {result['response'].get('ticker')}")
            else:
                failed += 1

    # Test 5: 404 handling for missing ticker
    print(f"\n{YELLOW}Test 5: 404 Handling for Missing Ticker{RESET}")
    result = test_endpoint("GET", f"{API_BASE_URL}/tickers/NONEXISTENT/thesis", expected_status=404)
    if print_test_result("GET /tickers/NONEXISTENT/thesis (404 expected)", result, 404):
        passed += 1
    else:
        failed += 1

    # Test 6: Case-insensitive ticker lookup
    print(f"\n{YELLOW}Test 6: Case-Insensitive Ticker Lookup{RESET}")
    result = test_endpoint("GET", f"{API_BASE_URL}/tickers/sofi/thesis")
    if print_test_result("GET /tickers/sofi/thesis (lowercase)", result):
        passed += 1
        if isinstance(result["response"], dict) and result["response"].get("ticker") == "SOFI":
            print(f"       Correctly normalized to uppercase ticker: SOFI")
    else:
        failed += 1

    # Test 7: Verify markdown content structure
    print(f"\n{YELLOW}Test 7: Verify Markdown Content Structure{RESET}")
    result = test_endpoint("GET", f"{API_BASE_URL}/tickers/SOFI/thesis")
    if result["success"] and isinstance(result["response"], dict):
        content = result["response"].get("content", "")
        has_headers = "# " in content
        has_sections = "##" in content
        if has_headers and has_sections:
            print(f"{GREEN}✓ PASS{RESET}: Markdown structure validated for SOFI thesis")
            print(f"       Found {content.count('#')} markdown headers")
            passed += 1
        else:
            print(f"{RED}✗ FAIL{RESET}: Markdown structure missing headers/sections")
            failed += 1
    else:
        print(f"{RED}✗ FAIL{RESET}: Could not verify markdown structure")
        failed += 1

    # Summary
    print(f"\n{YELLOW}Test Summary{RESET}")
    total = passed + failed
    print(f"Passed: {GREEN}{passed}/{total}{RESET}")
    print(f"Failed: {RED}{failed}/{total}{RESET}")

    if failed == 0:
        print(f"\n{GREEN}All tests passed!{RESET}")
        return 0
    else:
        print(f"\n{RED}Some tests failed. Check output above.{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
