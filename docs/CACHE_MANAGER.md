# Cache Manager Documentation

## Overview

The Cache Manager (`functions/market/cache.py`) provides a thread-safe, TTL-based in-memory cache for market data with automatic expiration, memory management, and comprehensive statistics tracking.

**Key Features:**
- ✅ TTL-based automatic expiration on access
- ✅ Thread-safe with Lock synchronization
- ✅ Memory usage tracking and limits
- ✅ LRU (Least Recently Used) eviction when max size exceeded
- ✅ Hit/Miss statistics and performance metrics
- ✅ Singleton pattern for global cache access
- ✅ Decorator support for automatic function result caching
- ✅ Comprehensive logging at DEBUG level

## Architecture

### Components

#### CacheEntry Dataclass
Represents a single cached value with expiration tracking.

```python
@dataclass
class CacheEntry:
    key: str                    # Unique cache key
    value: Any                  # Cached value (any type)
    timestamp: datetime         # UTC creation timestamp
    ttl_seconds: int           # Time-to-live in seconds
```

**Methods:**
- `is_expired() -> bool` - Check if entry has expired
- `get_age_seconds() -> float` - Age since creation
- `get_remaining_ttl() -> float` - Seconds until expiration (min 0)

#### CacheManager Class
Main cache management class with thread-safe operations.

```python
class CacheManager:
    def __init__(self, max_size_mb: int = 100)
    def get(key: str) -> Optional[Any]
    def set(key: str, value: Any, ttl_seconds: int) -> None
    def delete(key: str) -> bool
    def clear() -> None
    def get_stats() -> dict[str, Any]
```

### Thread Safety

All operations use a reentrant `threading.RLock()`:
- Prevents race conditions in concurrent access
- Allows nested lock acquisition
- Safe for multi-threaded applications

### Memory Management

**Tracking:**
- Uses `sys.getsizeof()` to calculate cache entry sizes
- Includes entry object overhead + value size
- Tracks total cache size in bytes and MB

**Eviction Strategy:**
- LRU (Least Recently Used) when cache exceeds max_size_mb
- Removes oldest accessed entries first
- Maintains `_access_order` list for LRU tracking
- Updates on every successful `get()` and `set()`

## Usage Examples

### Basic Operations

#### Set and Get Values
```python
from functions.market.cache import get_cache_manager

cache = get_cache_manager()

# Set a value with 60 second TTL
cache.set("AAPL_price", 150.25, ttl_seconds=60)

# Get the value
price = cache.get("AAPL_price")
print(price)  # 150.25

# After 60 seconds (auto-removed on next access)
time.sleep(61)
price = cache.get("AAPL_price")
print(price)  # None (expired and removed)
```

#### Delete and Clear
```python
# Delete specific entry
success = cache.delete("AAPL_price")
print(success)  # True if existed

# Clear all entries and reset stats
cache.clear()
```

### Using Default TTL Constants

```python
from functions.market.cache import DEFAULT_TTL_SECONDS, get_cache_manager

cache = get_cache_manager()

# Use predefined TTL values
cache.set("current_AAPL", price, ttl_seconds=DEFAULT_TTL_SECONDS["current_price"])
cache.set("options_AAPL", data, ttl_seconds=DEFAULT_TTL_SECONDS["options_chain"])
cache.set("history_AAPL", history, ttl_seconds=DEFAULT_TTL_SECONDS["price_history"])
```

**Available Constants:**
- `current_price`: 60 seconds
- `options_chain`: 300 seconds (5 minutes)
- `price_history`: 3600 seconds (1 hour)
- `ticker_info`: 86400 seconds (1 day)
- `expirations`: 1800 seconds (30 minutes)

### Using the Decorator

```python
from functions.market.cache import cache

@cache(ttl_seconds=300)
def fetch_option_chain(symbol: str):
    """Fetch options chain - result cached for 5 minutes."""
    # Expensive API call
    return fetch_from_yahoo_finance(symbol)

# First call: executes function and caches result
chain1 = fetch_option_chain("AAPL")

# Second call (within 5 min): returns cached result
chain2 = fetch_option_chain("AAPL")  # No API call

# Third call (after 5 min): cache expired, executes function
chain3 = fetch_option_chain("AAPL")  # API call again
```

**Decorator Notes:**
- Cache key includes function name and arguments
- Different arguments create different cache entries
- Works with positional and keyword arguments
- Cannot cache async functions (use manual caching)

### Getting Statistics

```python
stats = cache.get_stats()

print(f"Hit rate: {stats['hit_rate']:.1%}")
print(f"Size: {stats['current_size_mb']:.1f}MB / {stats['max_size_mb']}MB")
print(f"Entries: {stats['entry_count']}")
print(f"Utilization: {stats['size_utilization']:.1f}%")

# Detailed entry information
for entry in stats['entries'][:3]:
    print(f"{entry['key']}: {entry['remaining_ttl']:.1f}s remaining")
```

**Statistics Dictionary:**
```python
{
    'hit_count': int,              # Total cache hits
    'miss_count': int,             # Total cache misses
    'hit_rate': float,             # Hit rate (0.0-1.0)
    'entry_count': int,            # Number of entries
    'current_size_bytes': int,     # Size in bytes
    'current_size_mb': float,      # Size in MB
    'max_size_mb': int,            # Max allowed size
    'size_utilization': float,     # Percentage (0-100)
    'entries': [                   # List of entry metadata
        {
            'key': str,
            'size_bytes': int,
            'age_seconds': float,
            'remaining_ttl': float,
            'expired': bool,
        },
        ...
    ]
}
```

### Logging Cache Statistics

```python
from functions.market.cache import log_cache_stats

# Print formatted cache statistics to info level
log_cache_stats()

# Output:
# ============================================================
# CACHE STATISTICS
# ============================================================
# Hits: 42 | Misses: 8 | Hit Rate: 84.0%
# Entries: 15 | Size: 2.34MB / 100MB (2.3%)
# ============================================================
# Next 3 entries to expire:
#   - key1: 45.2s remaining [active]
#   - key2: 120.5s remaining [active]
#   - key3: 298.1s remaining [active]
```

## Default TTL Configuration

The cache includes sensible defaults for common data types:

| Data Type | TTL | Seconds | Use Case |
|-----------|-----|---------|----------|
| current_price | 60s | 60 | Real-time stock prices (refreshed every minute) |
| options_chain | 5m | 300 | Options chain data (not changing intra-minute) |
| price_history | 1h | 3600 | Historical price data (changes daily) |
| ticker_info | 1d | 86400 | Company information (rarely changes) |
| expirations | 30m | 1800 | Options expiration dates |

These values can be overridden as needed for specific use cases.

## Performance Characteristics

### Time Complexity
- **get(key)**: O(n) for access order update, O(1) for dictionary lookup
- **set(key, value, ttl)**: O(n) for eviction in worst case, O(1) for insertion
- **delete(key)**: O(n) for access order removal
- **get_stats()**: O(n) for calculating size and sorting entries

### Space Complexity
- **Memory tracking**: O(n) where n = number of entries
- **LRU tracking**: O(n) for access order list
- **Cache overhead**: Minimal (dataclass + dict/list structures)

### Example Metrics (typical use)
- **1000 entries**: ~10-50MB (depending on value size)
- **Hit rate**: 70-90% for market data (good locality)
- **Lookup time**: <1ms for all operations
- **Memory per entry**: ~100-200 bytes overhead + value size

## Singleton Pattern

The cache manager uses a singleton pattern to ensure a single shared cache instance:

```python
from functions.market.cache import get_cache_manager

# First call creates instance
cache1 = get_cache_manager(max_size_mb=100)

# Subsequent calls return same instance
cache2 = get_cache_manager(max_size_mb=200)  # max_size_mb ignored

assert cache1 is cache2  # True
```

**Benefits:**
- Single cache for entire application
- Consistent state across modules
- Thread-safe instance creation
- No duplicate cache instances

## Best Practices

### 1. Use Appropriate TTL Values
```python
# Good: Different TTL for different data types
cache.set("price", 150.25, ttl_seconds=60)  # Volatile data
cache.set("ticker_info", data, ttl_seconds=86400)  # Static data

# Avoid: Same TTL for all data
cache.set("key1", value1, ttl_seconds=300)  # Maybe too long?
cache.set("key2", value2, ttl_seconds=300)  # Maybe too short?
```

### 2. Use Decorator for Functions
```python
# Good: Automatic caching for expensive functions
@cache(ttl_seconds=300)
def fetch_options_chain(symbol):
    return expensive_api_call(symbol)

# Avoid: Manual caching for simple functions
def fetch_options_chain(symbol):
    result = cache.get(f"options_{symbol}")
    if result is None:
        result = expensive_api_call(symbol)
        cache.set(f"options_{symbol}", result, ttl_seconds=300)
    return result
```

### 3. Monitor Cache Performance
```python
# In periodic tasks (every minute)
from functions.market.cache import log_cache_stats

log_cache_stats()

# Check hit rate
stats = cache.get_stats()
if stats['hit_rate'] < 0.5:
    logger.warning(f"Low cache hit rate: {stats['hit_rate']:.1%}")
```

### 4. Handle Cache Misses Gracefully
```python
# Good: Check for None explicitly
data = cache.get("key")
if data is not None:
    process(data)
else:
    fetch_and_cache(data)

# Avoid: Assuming value exists
data = cache.get("key")  # Might be None!
process(data)  # Could crash
```

### 5. Size Cache Appropriately
```python
# Good: Match max_size_mb to expected usage
# For market data: 100-500MB typical
cache = CacheManager(max_size_mb=200)

# Avoid: Too small (constant eviction)
cache = CacheManager(max_size_mb=1)  # Too small

# Avoid: Too large (memory issues)
cache = CacheManager(max_size_mb=10000)  # Too large
```

## Logging

The cache manager logs at DEBUG level by default. Set `LOG_LEVEL=DEBUG` in `.env` to see:

```python
# Set logging level
from functions.util.logging_setup import setup_logging
setup_logging(log_level="DEBUG")

# Now see cache operations:
# Cache manager initialized with max size 100MB
# Cache hit for key: AAPL_price (age: 5.2s)
# Cache miss for key: TSLA_chain
# Cache expired for key: BTC_history (age: 3601.2s, ttl: 3600s)
# Evicted cache entry (LRU): OLD_KEY
# LRU eviction completed: 5 entries removed
```

## Troubleshooting

### Issue: Cache Hit Rate Very Low
**Symptom:** `hit_rate < 0.3` even with decorator

**Causes:**
- TTL too short for data stability
- Cache keys not matching (arguments differ)
- Cache cleared too frequently

**Solutions:**
```python
# Increase TTL
@cache(ttl_seconds=600)  # Increased from 300

# Debug cache keys
@cache(ttl_seconds=300)
def my_func(symbol):
    logger.debug(f"Called with: {symbol}")
    return fetch(symbol)

# Don't clear cache unnecessarily
# cache.clear()  # Only if needed!
```

### Issue: Memory Usage Growing
**Symptom:** Cache size exceeds max_size_mb frequently

**Causes:**
- max_size_mb too small
- Caching large objects
- LRU eviction ineffective

**Solutions:**
```python
# Increase max_size_mb
cache = CacheManager(max_size_mb=500)

# Cache smaller representations
cache.set("key", json.dumps(obj), ttl_seconds=300)

# Monitor statistics
stats = cache.get_stats()
logger.info(f"Cache utilization: {stats['size_utilization']:.1f}%")
```

### Issue: Expired Entries Still Returned
**Symptom:** Getting None for keys that should exist

**Note:** This is correct behavior! Expired entries return None and are automatically removed.

**Expected behavior:**
```python
cache.set("key", "value", ttl_seconds=1)
time.sleep(0.5)
assert cache.get("key") == "value"  # Still available

time.sleep(0.6)
assert cache.get("key") is None  # Expired
```

## Integration Example

Complete example showing cache in market data fetching:

```python
from functions.market.cache import cache, DEFAULT_TTL_SECONDS, log_cache_stats
import yfinance

# Cache market data fetch
@cache(ttl_seconds=DEFAULT_TTL_SECONDS["current_price"])
def get_current_price(symbol: str) -> float:
    """Fetch and cache current stock price."""
    ticker = yfinance.Ticker(symbol)
    return ticker.info['currentPrice']

# Cache options chain
@cache(ttl_seconds=DEFAULT_TTL_SECONDS["options_chain"])
def get_options_chain(symbol: str) -> dict:
    """Fetch and cache options chain for symbol."""
    ticker = yfinance.Ticker(symbol)
    return ticker.option_chain()

# Cache ticker info
@cache(ttl_seconds=DEFAULT_TTL_SECONDS["ticker_info"])
def get_ticker_info(symbol: str) -> dict:
    """Fetch and cache ticker information."""
    ticker = yfinance.Ticker(symbol)
    return ticker.info

# Usage
price = get_current_price("AAPL")  # API call
price = get_current_price("AAPL")  # Cached (60s)

chain = get_options_chain("AAPL")  # API call
chain = get_options_chain("AAPL")  # Cached (5m)

# Monitor cache health
log_cache_stats()
```

## API Reference

### CacheEntry

**Dataclass:**
```python
@dataclass
class CacheEntry:
    key: str
    value: Any
    timestamp: datetime
    ttl_seconds: int
```

**Methods:**
- `is_expired() -> bool` - Check expiration status
- `get_age_seconds() -> float` - Age in seconds
- `get_remaining_ttl() -> float` - TTL remaining

### CacheManager

**Constructor:**
```python
CacheManager(max_size_mb: int = 100)
```

**Methods:**
```python
def get(key: str) -> Optional[Any]
def set(key: str, value: Any, ttl_seconds: int) -> None
def delete(key: str) -> bool
def clear() -> None
def get_stats() -> dict[str, Any]
```

**Properties:**
```python
max_size_mb: int              # Maximum cache size in MB
_cache: dict[str, CacheEntry]  # Internal cache dictionary
_hit_count: int               # Number of cache hits
_miss_count: int              # Number of cache misses
```

### Functions

**get_cache_manager:**
```python
def get_cache_manager(max_size_mb: int = 100) -> CacheManager
```
Get singleton cache manager instance.

**cache:**
```python
def cache(ttl_seconds: int = 300) -> Callable
```
Decorator for automatic result caching.

**log_cache_stats:**
```python
def log_cache_stats() -> None
```
Log formatted cache statistics to info level.

## Constants

**DEFAULT_TTL_SECONDS:**
```python
{
    "current_price": 60,          # 1 minute
    "options_chain": 300,         # 5 minutes
    "price_history": 3600,        # 1 hour
    "ticker_info": 86400,         # 1 day
    "expirations": 1800,          # 30 minutes
}
```

## Testing

The cache manager includes comprehensive unit tests in `/tests/tech/unit/test_cache_manager.py`:

```bash
# Run cache tests
pytest tests/tech/unit/test_cache_manager.py -v

# Run with coverage
pytest tests/tech/unit/test_cache_manager.py --cov=functions.market.cache

# Run specific test
pytest tests/tech/unit/test_cache_manager.py::TestCacheManager::test_set_and_get -v
```

Test coverage includes:
- Basic operations (set, get, delete, clear)
- TTL expiration and auto-removal
- Memory management and LRU eviction
- Thread safety with concurrent operations
- Statistics tracking and calculation
- Singleton pattern
- Decorator functionality
- Edge cases and special scenarios

## Performance Tips

1. **Batch operations** when possible to reduce lock contention
2. **Use appropriate TTL values** to balance freshness vs. API calls
3. **Monitor cache statistics** regularly in production
4. **Size cache appropriately** for expected data volume
5. **Prefer decorator** over manual caching for cleaner code

## Related Files

- **Source:** `/functions/market/cache.py`
- **Tests:** `/tests/tech/unit/test_cache_manager.py`
- **Module init:** `/functions/market/__init__.py`
- **Logging:** `/functions/util/logging_setup.py`
- **Configuration:** `.env` (set LOG_LEVEL for verbosity)

