"""
Practical examples of circuit breaker usage in the Option Chain Dashboard.

These examples demonstrate how to integrate the circuit breaker pattern
with actual market data fetching and API endpoints.

Usage:
    from functions.market.circuit_breaker_examples import (
        get_stock_price_with_fallback,
        get_options_chain_with_fallback,
        monitor_api_health,
    )

    price = get_stock_price_with_fallback("AAPL")
    chain = get_options_chain_with_fallback("AAPL", "2026-02-21")
    monitor_api_health()
"""

from datetime import datetime
from typing import Optional, Dict, Any, List

from functions.market.circuit_breaker import (
    CircuitBreakerRegistry,
    CircuitBreakerOpenError,
)
from functions.util.logging_setup import get_logger

logger = get_logger(__name__)

# Get the singleton registry
registry = CircuitBreakerRegistry()


# ============================================================================
# Example 1: Fetching Stock Prices with Fallback
# ============================================================================
def get_stock_price_with_fallback(
    symbol: str,
    use_cache: bool = True,
) -> Optional[float]:
    """
    Fetch current stock price with circuit breaker protection and fallback.

    Tries to fetch fresh price from API. If API is down (circuit open),
    falls back to cached price. If no cache available, returns None.

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")
        use_cache: Whether to use cached price on API failure

    Returns:
        Current stock price or None if unavailable

    Example:
        price = get_stock_price_with_fallback("AAPL")
        if price:
            print(f"AAPL: ${price}")
        else:
            print("Price data unavailable")
    """
    breaker = registry.get("current_price")

    if breaker is None:
        logger.error(f"Circuit breaker 'current_price' not found")
        return None

    try:
        # Try to fetch from API through circuit breaker
        price = breaker.call(_fetch_price_from_api, symbol=symbol)
        logger.info(f"Fetched {symbol} price: ${price}")
        return price

    except CircuitBreakerOpenError:
        logger.warning(f"Price API down for {symbol}, attempting fallback")

        if use_cache:
            cached_price = _get_cached_price(symbol)
            if cached_price is not None:
                logger.info(f"Using cached price for {symbol}: ${cached_price}")
                return cached_price

        logger.error(f"No price available for {symbol}")
        return None

    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
        return None


# ============================================================================
# Example 2: Fetching Options Chain with Resilience
# ============================================================================
def get_options_chain_with_fallback(
    symbol: str,
    expiration: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetch options chain with circuit breaker protection and graceful degradation.

    Attempts to fetch full options chain. If the API is down, returns empty
    chain with status flag. This allows the dashboard to display partial data
    rather than failing completely.

    Args:
        symbol: Stock ticker symbol
        expiration: Option expiration date (e.g., "2026-02-21") or None for all

    Returns:
        Dictionary with chain data and status information:
        {
            "calls": [...],
            "puts": [...],
            "status": "success" | "degraded" | "unavailable",
            "fetched_at": datetime,
            "cached": bool
        }

    Example:
        chain = get_options_chain_with_fallback("AAPL", "2026-02-21")
        if chain["status"] == "success":
            print(f"Got {len(chain['calls'])} calls")
        elif chain["status"] == "degraded":
            print("Using partial/cached data")
    """
    breaker = registry.get("options_chain")

    if breaker is None:
        logger.error("Circuit breaker 'options_chain' not found")
        return {
            "calls": [],
            "puts": [],
            "status": "unavailable",
            "fetched_at": datetime.utcnow().isoformat(),
            "cached": False,
        }

    try:
        logger.info(f"Fetching options chain for {symbol} exp={expiration}")

        # Try to fetch through circuit breaker
        chain = breaker.call(
            _fetch_options_chain_from_api,
            symbol=symbol,
            expiration=expiration,
        )

        logger.info(
            f"Got options chain for {symbol}: "
            f"{len(chain.get('calls', []))} calls, "
            f"{len(chain.get('puts', []))} puts"
        )

        return {
            "calls": chain.get("calls", []),
            "puts": chain.get("puts", []),
            "status": "success",
            "fetched_at": datetime.utcnow().isoformat(),
            "cached": False,
        }

    except CircuitBreakerOpenError:
        logger.warning(f"Options chain API down for {symbol}, checking cache")

        # Try to use cached chain
        cached_chain = _get_cached_options_chain(symbol, expiration)
        if cached_chain:
            logger.info(f"Using cached options chain for {symbol}")
            return {
                "calls": cached_chain.get("calls", []),
                "puts": cached_chain.get("puts", []),
                "status": "degraded",  # Using cached data
                "fetched_at": datetime.utcnow().isoformat(),
                "cached": True,
            }

        # No cache available
        logger.error(f"No data available for {symbol}")
        return {
            "calls": [],
            "puts": [],
            "status": "unavailable",
            "fetched_at": datetime.utcnow().isoformat(),
            "cached": False,
        }

    except Exception as e:
        logger.error(f"Error fetching options chain for {symbol}: {e}")
        return {
            "calls": [],
            "puts": [],
            "status": "unavailable",
            "fetched_at": datetime.utcnow().isoformat(),
            "cached": False,
        }


# ============================================================================
# Example 3: Fetching Price History with Retry Logic
# ============================================================================
def get_price_history_with_fallback(
    symbol: str,
    days: int = 90,
) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch historical price data with circuit breaker protection.

    Args:
        symbol: Stock ticker symbol
        days: Number of historical days to fetch

    Returns:
        List of price points or None if unavailable

    Example:
        history = get_price_history_with_fallback("AAPL", days=30)
        if history:
            print(f"Got {len(history)} days of price history")
    """
    breaker = registry.get("price_history")

    if breaker is None:
        logger.error("Circuit breaker 'price_history' not found")
        return None

    try:
        logger.info(f"Fetching {days}-day history for {symbol}")

        history = breaker.call(
            _fetch_price_history_from_api,
            symbol=symbol,
            days=days,
        )

        logger.info(f"Got {len(history)} price points for {symbol}")
        return history

    except CircuitBreakerOpenError:
        logger.warning(f"Price history API down for {symbol}")
        return _get_cached_price_history(symbol, days)

    except Exception as e:
        logger.error(f"Error fetching price history for {symbol}: {e}")
        return None


# ============================================================================
# Example 4: Monitoring API Health
# ============================================================================
def monitor_api_health() -> Dict[str, Any]:
    """
    Monitor health of all API endpoints protected by circuit breakers.

    Useful for dashboards, health checks, and alerting systems.

    Returns:
        Health status summary:
        {
            "healthy": True/False,
            "open_breakers": ["endpoint1", "endpoint2"],
            "half_open_breakers": ["endpoint3"],
            "all_status": { "endpoint": {...}, ... },
            "timestamp": "2026-01-26T..."
        }

    Example:
        health = monitor_api_health()
        if not health["healthy"]:
            alert_ops(f"APIs down: {health['open_breakers']}")

        for endpoint, status in health["all_status"].items():
            if status["state"] == "OPEN":
                logger.error(f"{endpoint} is DOWN")
    """
    open_breakers = registry.get_open_breakers()
    half_open_breakers = registry.get_half_open_breakers()
    all_status = registry.get_status_all()

    is_healthy = len(open_breakers) == 0

    summary = {
        "healthy": is_healthy,
        "open_breakers": open_breakers,
        "half_open_breakers": half_open_breakers,
        "total_endpoints": len(all_status),
        "endpoints_degraded": len(open_breakers) + len(half_open_breakers),
        "all_status": all_status,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Log health status
    if is_healthy:
        logger.info("All APIs healthy")
    else:
        logger.error(f"API health issues: {open_breakers} are down")

    if half_open_breakers:
        logger.warning(f"APIs recovering: {half_open_breakers}")

    return summary


# ============================================================================
# Example 5: Dashboard Data Loading with Multi-Step Resilience
# ============================================================================
async def load_dashboard_data(symbol: str) -> Dict[str, Any]:
    """
    Load complete dashboard data with stepped fallback strategy.

    Attempts to fetch all data. Falls back gracefully at each step:
    1. Try live data
    2. Try cache
    3. Return partial/empty data with status

    Args:
        symbol: Stock ticker symbol

    Returns:
        Dashboard data dictionary with status flags for each section

    Example:
        dashboard = await load_dashboard_data("AAPL")

        # Display what we have
        if dashboard["price"]["status"] == "success":
            print(f"Price: ${dashboard['price']['value']}")
        else:
            print(f"Price: {dashboard['price']['status']}")
    """
    logger.info(f"Loading dashboard data for {symbol}")

    dashboard = {
        "symbol": symbol,
        "timestamp": datetime.utcnow().isoformat(),
        "price": {},
        "history": {},
        "options": {},
        "info": {},
        "overall_status": "unknown",
    }

    # Load price
    price = get_stock_price_with_fallback(symbol)
    dashboard["price"] = {
        "value": price,
        "status": "success" if price else "unavailable",
    }

    # Load price history
    history = get_price_history_with_fallback(symbol, days=90)
    dashboard["history"] = {
        "count": len(history) if history else 0,
        "data": history,
        "status": "success" if history else "unavailable",
    }

    # Load options chain
    options = get_options_chain_with_fallback(symbol)
    dashboard["options"] = {
        "calls_count": len(options.get("calls", [])),
        "puts_count": len(options.get("puts", [])),
        "data": options,
        "status": options.get("status", "unavailable"),
    }

    # Load ticker info
    info = _fetch_ticker_info_with_fallback(symbol)
    dashboard["info"] = {
        "data": info,
        "status": "success" if info else "unavailable",
    }

    # Determine overall status
    statuses = [
        dashboard["price"]["status"],
        dashboard["history"]["status"],
        dashboard["options"]["status"],
        dashboard["info"]["status"],
    ]

    if all(s == "success" for s in statuses):
        dashboard["overall_status"] = "healthy"
    elif any(s == "success" for s in statuses):
        dashboard["overall_status"] = "degraded"
    else:
        dashboard["overall_status"] = "unavailable"

    logger.info(f"Dashboard data loaded: {dashboard['overall_status']}")

    return dashboard


# ============================================================================
# Helper Functions (Placeholder Implementations)
# ============================================================================
def _fetch_price_from_api(symbol: str) -> float:
    """Placeholder: Actual API call to fetch current price."""
    # This would call yfinance or another API
    raise NotImplementedError("Implement with real API call")


def _fetch_options_chain_from_api(
    symbol: str,
    expiration: Optional[str] = None,
) -> Dict[str, Any]:
    """Placeholder: Actual API call to fetch options chain."""
    raise NotImplementedError("Implement with real API call")


def _fetch_price_history_from_api(symbol: str, days: int) -> List[Dict[str, Any]]:
    """Placeholder: Actual API call to fetch price history."""
    raise NotImplementedError("Implement with real API call")


def _fetch_ticker_info_with_fallback(symbol: str) -> Optional[Dict[str, Any]]:
    """Placeholder: Fetch ticker info with fallback."""
    breaker = registry.get("ticker_info")
    if not breaker:
        return None

    try:
        return breaker.call(_fetch_ticker_info_from_api, symbol=symbol)
    except CircuitBreakerOpenError:
        logger.warning(f"Ticker info API down for {symbol}")
        return _get_cached_ticker_info(symbol)
    except Exception as e:
        logger.error(f"Error fetching ticker info for {symbol}: {e}")
        return None


def _fetch_ticker_info_from_api(symbol: str) -> Dict[str, Any]:
    """Placeholder: Actual API call to fetch ticker info."""
    raise NotImplementedError("Implement with real API call")


# ============================================================================
# Cache Functions (Placeholder Implementations)
# ============================================================================
def _get_cached_price(symbol: str) -> Optional[float]:
    """Placeholder: Get cached price from database."""
    # This would query DuckDB cache
    return None


def _get_cached_options_chain(
    symbol: str,
    expiration: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Placeholder: Get cached options chain from database."""
    return None


def _get_cached_price_history(
    symbol: str,
    days: int,
) -> Optional[List[Dict[str, Any]]]:
    """Placeholder: Get cached price history from database."""
    return None


def _get_cached_ticker_info(symbol: str) -> Optional[Dict[str, Any]]:
    """Placeholder: Get cached ticker info from database."""
    return None
