# Circuit Breaker Pattern for API Resilience

The circuit breaker pattern is a critical component for building resilient APIs. It prevents cascading failures by automatically stopping requests to failing services and attempting recovery when the service is ready.

## Overview

The circuit breaker implementation provides three operational states:

- **CLOSED**: Normal operation - requests pass through to the service
- **OPEN**: Service failing - requests are rejected immediately to fail fast
- **HALF_OPEN**: Testing recovery - allows one request to test if service has recovered

## Module Location

```
functions/market/circuit_breaker.py
```

## Key Components

### 1. CircuitBreakerState Enum

Represents the three possible states:

```python
from functions.market.circuit_breaker import CircuitBreakerState

CircuitBreakerState.CLOSED     # Normal operation
CircuitBreakerState.OPEN       # Service failing, reject requests
CircuitBreakerState.HALF_OPEN  # Testing recovery
```

### 2. CircuitBreaker Class

Main implementation for protecting individual API endpoints.

#### Initialization

```python
from functions.market.circuit_breaker import CircuitBreaker

breaker = CircuitBreaker(
    name="my_api_endpoint",
    failure_threshold=5,           # Open after 5 consecutive failures
    recovery_timeout_seconds=60    # Try recovery after 60 seconds
)
```

#### Making API Calls Through the Breaker

```python
from functions.market.circuit_breaker import CircuitBreakerOpenError
import requests

def fetch_data(symbol):
    """Example API call."""
    response = requests.get(f"https://api.example.com/data/{symbol}")
    return response.json()

breaker = CircuitBreaker(name="data_api")

try:
    data = breaker.call(fetch_data, symbol="AAPL")
    print(f"Data: {data}")
except CircuitBreakerOpenError:
    print("Service temporarily unavailable, using cached data")
    # Use fallback/cached data
except Exception as e:
    print(f"API error: {e}")
    # Handle the actual API error
```

#### Checking Breaker State

```python
# Check if breaker is in specific state
if breaker.is_open():
    print("Circuit is OPEN - service unavailable")
elif breaker.is_half_open():
    print("Circuit is HALF_OPEN - testing recovery")
elif breaker.is_closed():
    print("Circuit is CLOSED - normal operation")

# Get current state
state = breaker.get_state()
print(f"Current state: {state}")

# Get detailed status
status = breaker.get_status()
print(f"Status: {status}")
# Output:
# {
#   'name': 'my_api_endpoint',
#   'state': 'CLOSED',
#   'failure_count': 2,
#   'success_count': 15,
#   'failure_threshold': 5,
#   'recovery_timeout_seconds': 60,
#   'last_failure_time': '2026-01-26T11:05:56.123Z',
#   'last_state_change': '2026-01-26T11:05:50.000Z',
#   'time_until_recovery_seconds': None
# }
```

#### Resetting the Breaker

```python
# Reset breaker back to CLOSED state (e.g., after manual intervention)
breaker.reset()
```

### 3. CircuitBreakerRegistry (Singleton)

Centralized management of all circuit breakers with pre-configured endpoints.

#### Getting the Registry

```python
from functions.market.circuit_breaker import CircuitBreakerRegistry

# Get the singleton instance
registry = CircuitBreakerRegistry()
```

#### Pre-configured Endpoints

The registry comes pre-configured with breakers for these endpoints:

```python
registry.get("current_price")     # Fetch current stock price
registry.get("price_history")     # Fetch historical price data
registry.get("options_chain")     # Fetch options chain data
registry.get("ticker_info")       # Fetch ticker information
registry.get("expirations")       # Fetch expiration dates
```

#### Using Registry Breakers

```python
from functions.market.circuit_breaker import CircuitBreakerRegistry

registry = CircuitBreakerRegistry()

# Get a specific breaker
breaker = registry.get("current_price")

# Use it to wrap your API calls
def fetch_current_price(symbol):
    # Real API call
    return 150.25

try:
    price = breaker.call(fetch_current_price, symbol="AAPL")
except CircuitBreakerOpenError:
    price = get_cached_price("AAPL")  # Fallback to cache
```

#### Registering Custom Breakers

```python
from functions.market.circuit_breaker import CircuitBreaker, CircuitBreakerRegistry

registry = CircuitBreakerRegistry()

# Create and register a custom breaker
custom_breaker = CircuitBreaker(
    name="my_custom_api",
    failure_threshold=10,
    recovery_timeout_seconds=120
)
registry.register("my_custom_api", custom_breaker)

# Later, retrieve it
breaker = registry.get("my_custom_api")
```

#### Bulk Operations

```python
registry = CircuitBreakerRegistry()

# Get all breakers
all_breakers = registry.get_all()

# Get status of all breakers
statuses = registry.get_status_all()
print(statuses)

# Get only OPEN breakers (those that are failing)
open_breakers = registry.get_open_breakers()
if open_breakers:
    print(f"Warning: {open_breakers} are currently unavailable")

# Get only HALF_OPEN breakers (those attempting recovery)
half_open = registry.get_half_open_breakers()

# Get only CLOSED breakers (those operating normally)
closed_breakers = registry.get_closed_breakers()

# Reset all breakers (e.g., after maintenance)
registry.reset_all()
```

## State Transitions

The circuit breaker follows a predictable state machine:

```
    Failure count >= threshold
                  ↓
    CLOSED ─────────────→ OPEN
      ↑                     ↓
      │            recovery_timeout elapsed
      │                     ↓
      │               HALF_OPEN
      │            /           \
      │     Success          Failure
      │         /               \
      └─────────                 → OPEN
```

### Transition Rules

1. **CLOSED → OPEN**: When failure_count reaches failure_threshold
   - Example: 5 consecutive failures with threshold=5

2. **OPEN → HALF_OPEN**: When recovery_timeout_seconds has elapsed since last failure
   - Example: 60 seconds after the 5th failure

3. **HALF_OPEN → CLOSED**: When the next request succeeds
   - Circuit returns to normal operation
   - Failure count resets to 0

4. **HALF_OPEN → OPEN**: When the next request fails
   - Service still not healthy
   - Restart the timeout period

## Real-World Usage Examples

### Example 1: Protecting Market Data Fetching

```python
from functions.market.circuit_breaker import CircuitBreakerRegistry
import yfinance as yf

registry = CircuitBreakerRegistry()
price_breaker = registry.get("current_price")

def get_stock_price(symbol):
    """Fetch stock price with circuit breaker protection."""
    try:
        price = price_breaker.call(_fetch_price, symbol)
        return price
    except CircuitBreakerOpenError:
        # Service is down, use cached or default value
        return get_cached_price(symbol)
    except Exception as e:
        logger.error(f"Failed to fetch price for {symbol}: {e}")
        return None

def _fetch_price(symbol):
    ticker = yf.Ticker(symbol)
    return ticker.info['currentPrice']
```

### Example 2: Building a Resilient Dashboard Data Loader

```python
from functions.market.circuit_breaker import CircuitBreakerRegistry

registry = CircuitBreakerRegistry()

async def load_dashboard_data(symbol):
    """Load all dashboard data with fallbacks for failing endpoints."""

    # Try to fetch each piece of data through its circuit breaker
    price_breaker = registry.get("current_price")
    history_breaker = registry.get("price_history")
    chain_breaker = registry.get("options_chain")

    dashboard_data = {}

    # Current price
    try:
        dashboard_data['price'] = price_breaker.call(fetch_price, symbol)
    except CircuitBreakerOpenError:
        dashboard_data['price'] = get_cached_price(symbol)
        dashboard_data['price_status'] = 'cached'

    # Price history
    try:
        dashboard_data['history'] = history_breaker.call(fetch_history, symbol)
    except CircuitBreakerOpenError:
        dashboard_data['history'] = []
        dashboard_data['history_status'] = 'unavailable'

    # Options chain
    try:
        dashboard_data['chain'] = chain_breaker.call(fetch_options, symbol)
    except CircuitBreakerOpenError:
        dashboard_data['chain'] = {}
        dashboard_data['chain_status'] = 'unavailable'

    return dashboard_data
```

### Example 3: Monitoring Circuit Breaker Health

```python
from functions.market.circuit_breaker import CircuitBreakerRegistry
from functions.util.logging_setup import get_logger

logger = get_logger(__name__)

def check_api_health():
    """Monitor the health of all API endpoints."""
    registry = CircuitBreakerRegistry()

    open_breakers = registry.get_open_breakers()
    half_open = registry.get_half_open_breakers()

    if open_breakers:
        logger.error(f"ALERT: Circuit breakers OPEN: {open_breakers}")
        # Send alert to monitoring system
        alert_monitoring_system(f"APIs down: {open_breakers}")

    if half_open:
        logger.warning(f"Circuit breakers recovering: {half_open}")

    # Log overall status
    all_status = registry.get_status_all()
    for name, status in all_status.items():
        logger.info(f"{name}: {status['state']} "
                   f"(failures: {status['failure_count']}/{status['failure_threshold']})")
```

## Configuration

Circuit breaker settings are configured per endpoint in the registry. Edit the defaults in `CircuitBreakerRegistry._default_breakers`:

```python
_default_breakers: dict[str, dict[str, Any]] = {
    "current_price": {
        "failure_threshold": 5,
        "recovery_timeout_seconds": 60,
    },
    "options_chain": {
        "failure_threshold": 3,      # More conservative for complex operation
        "recovery_timeout_seconds": 90,  # Longer timeout
    },
    # ... more endpoints
}
```

### Tuning Parameters

- **failure_threshold**: How many failures trigger OPEN state
  - Higher = more tolerant, slower to open
  - Lower = faster failure detection, more frequent circuit breaks
  - Typical: 3-5 for latency-sensitive operations, 5-10 for normal APIs

- **recovery_timeout_seconds**: How long before attempting recovery
  - Higher = longer wait before retry, more conservative
  - Lower = faster recovery attempts
  - Typical: 30-60 seconds for normal operations, 90+ for degraded services

## Thread Safety

The implementation is fully thread-safe:

- All state transitions are protected by `threading.Lock`
- Multiple threads can safely call the same breaker simultaneously
- Safe to use in async/await contexts with FastAPI

## Exceptions

### CircuitBreakerOpenError

Raised when the circuit breaker is OPEN and the request is rejected.

```python
from functions.market.circuit_breaker import CircuitBreakerOpenError

breaker = registry.get("current_price")

try:
    data = breaker.call(fetch_data, symbol="AAPL")
except CircuitBreakerOpenError as e:
    print(f"Circuit breaker open: {e}")
    # This means: Stop trying this API now, use fallback data
```

### CircuitBreakerError

Base exception for other circuit breaker errors (for future use).

```python
from functions.market.circuit_breaker import CircuitBreakerError
```

## Logging

All state transitions are logged with timestamps and details:

```
2026-01-26T11:05:56.123Z [ERROR] CircuitBreaker 'options_chain'
    transitioning to OPEN (3 consecutive failures)

2026-01-26T11:05:56.000Z [INFO] CircuitBreaker 'options_chain'
    transitioning to HALF_OPEN (recovery timeout elapsed)

2026-01-26T11:05:56.500Z [INFO] CircuitBreaker 'options_chain'
    transitioning to CLOSED (recovery successful)
```

## Testing

See `tests/tech/unit/test_circuit_breaker.py` for comprehensive tests covering:

- State transitions
- Failure threshold tracking
- Recovery timeout logic
- Thread safety
- Registry singleton behavior

Run tests:

```bash
source venv/bin/activate
pytest tests/tech/unit/test_circuit_breaker.py -v
```

## Performance Impact

The circuit breaker has minimal performance overhead:

- **CLOSED state**: Single lock acquisition/release per call (~microseconds)
- **OPEN state**: No lock needed, immediate rejection (nanoseconds)
- **HALF_OPEN state**: Single lock acquisition/release (microseconds)

Memory usage is negligible - one CircuitBreaker instance per endpoint.

## Best Practices

1. **Use pre-configured registry breakers** for standard endpoints
2. **Always handle CircuitBreakerOpenError** with a fallback strategy
3. **Monitor open circuit breakers** and alert on issues
4. **Tune thresholds** based on expected API behavior
5. **Log state transitions** for debugging
6. **Reset manually** only after confirming service recovery
7. **Test failure scenarios** in development/staging

## Integration with API Endpoints

Example integration in FastAPI:

```python
from fastapi import FastAPI, HTTPException
from functions.market.circuit_breaker import CircuitBreakerRegistry, CircuitBreakerOpenError

app = FastAPI()
registry = CircuitBreakerRegistry()

@app.get("/api/options/{symbol}")
async def get_options(symbol: str):
    """Fetch options chain with circuit breaker protection."""
    breaker = registry.get("options_chain")

    try:
        data = breaker.call(fetch_options_from_api, symbol)
        return data
    except CircuitBreakerOpenError:
        raise HTTPException(
            status_code=503,
            detail="Options service temporarily unavailable. Try again later."
        )
    except Exception as e:
        logger.error(f"Failed to fetch options: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch options data"
        )
```

## References

- [Circuit Breaker Pattern - Martin Fowler](https://martinfowler.com/bliki/CircuitBreaker.html)
- [Resilience4j Documentation](https://resilience4j.readme.io/docs/circuitbreaker)
- [AWS Well-Architected Framework - Resilience](https://docs.aws.amazon.com/wellarchitected/latest/userguide/workload-resilience.html)
