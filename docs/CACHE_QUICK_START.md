# Cache Manager - Quick Start Guide

## One-Minute Overview

The cache manager provides fast, thread-safe in-memory caching with automatic expiration (TTL).

```python
from functions.market.cache import get_cache_manager

cache = get_cache_manager()

# Store a value for 5 minutes
cache.set("AAPL_price", 150.25, ttl_seconds=300)

# Retrieve value (returns None if expired)
price = cache.get("AAPL_price")  # 150.25
```

## Most Common Patterns

### Pattern 1: Using the Decorator (Recommended)

Cache function results automatically:

```python
from functions.market.cache import cache

@cache(ttl_seconds=300)
def fetch_options_chain(symbol: str):
    # Expensive operation
    return fetch_from_api(symbol)

# Usage
data = fetch_options_chain("AAPL")  # API call + cache
data = fetch_options_chain("AAPL")  # Returns cached result
```

**Pros:** Clean, automatic, no manual cache management
**Cons:** Can't customize per-call behavior

### Pattern 2: Manual Cache Management

Direct cache control:

```python
from functions.market.cache import get_cache_manager, DEFAULT_TTL_SECONDS

cache = get_cache_manager()

# Set value
cache.set("AAPL_chain", data,
          ttl_seconds=DEFAULT_TTL_SECONDS["options_chain"])

# Get value
result = cache.get("AAPL_chain")
if result is not None:
    process(result)
else:
    fetch_new_data()
```

**Pros:** Full control, can handle cache misses explicitly
**Cons:** More verbose

## Default TTL Values

Use these for consistency:

```python
from functions.market.cache import DEFAULT_TTL_SECONDS

DEFAULT_TTL_SECONDS = {
    "current_price": 60,          # 1 minute
    "options_chain": 300,         # 5 minutes
    "price_history": 3600,        # 1 hour
    "ticker_info": 86400,         # 1 day
    "expirations": 1800,          # 30 minutes
}
```

Choose based on data volatility:
- **current_price:** Stock prices change every second
- **options_chain:** Options don't change intra-minute
- **price_history:** Historical data stable for days
- **ticker_info:** Company info stable for months
- **expirations:** Expiration dates change daily

## Common Tasks

### Check if Value is Cached

```python
value = cache.get("key")
if value is not None:
    print("Found in cache!")
else:
    print("Not in cache or expired")
```

### Delete a Value

```python
success = cache.delete("key")
print(f"Deleted: {success}")  # True/False
```

### Clear All Cached Data

```python
cache.clear()  # Removes all entries and resets stats
```

### View Cache Statistics

```python
stats = cache.get_stats()

print(f"Hit rate: {stats['hit_rate']:.1%}")  # 85.2%
print(f"Size: {stats['current_size_mb']:.1f}MB")  # 12.3MB
print(f"Entries: {stats['entry_count']}")  # 42
```

### Log Cache Health

```python
from functions.market.cache import log_cache_stats

log_cache_stats()  # Prints formatted stats
```

## Complete Example

Real-world usage combining multiple features:

```python
from functions.market.cache import (
    cache,
    get_cache_manager,
    DEFAULT_TTL_SECONDS,
    log_cache_stats
)
import yfinance

# Cached function for price
@cache(ttl_seconds=DEFAULT_TTL_SECONDS["current_price"])
def get_price(symbol: str) -> float:
    return yfinance.Ticker(symbol).info['currentPrice']

# Cached function for options
@cache(ttl_seconds=DEFAULT_TTL_SECONDS["options_chain"])
def get_chain(symbol: str) -> dict:
    return yfinance.Ticker(symbol).option_chain()

# Usage
price = get_price("AAPL")  # API call
price = get_price("AAPL")  # Cached
price = get_price("AAPL")  # Cached

chain = get_chain("AAPL")  # API call
chain = get_chain("AAPL")  # Cached

# Check performance
log_cache_stats()
# Output:
# ============================================================
# CACHE STATISTICS
# ============================================================
# Hits: 4 | Misses: 2 | Hit Rate: 66.7%
# Entries: 2 | Size: 0.05MB / 100MB (0.1%)
# ============================================================
```

## Troubleshooting

### Values Not Being Cached

**Problem:** Get calls always return None
**Solution:** Check TTL hasn't expired
```python
# Debug: Check cache entry
stats = cache.get_stats()
for entry in stats['entries']:
    print(f"{entry['key']}: {entry['remaining_ttl']:.1f}s left")
```

### Cache Getting Full

**Problem:** Error messages about memory
**Solution:** Increase max_size_mb
```python
# In your code
cache = CacheManager(max_size_mb=500)  # Increased from 100
```

### Same Function Called Multiple Times

**Problem:** Decorator not caching
**Solution:** Check arguments are identical
```python
# Different args = different cache entries
result1 = fetch("AAPL")  # Cached as "fetch|AAPL"
result2 = fetch("TSLA")  # Cached as "fetch|TSLA"
result3 = fetch("AAPL")  # Uses "fetch|AAPL" cache
```

## Performance Notes

- **Lookup:** <1ms for any operation
- **Hit Rate:** Expect 70-85% with good TTL settings
- **Memory:** ~100-200 bytes per entry (+ value size)
- **Thread Safety:** All operations are thread-safe

## Files to Know

- **Implementation:** `functions/market/cache.py` (504 lines)
- **Tests:** `tests/tech/unit/test_cache_manager.py` (many tests)
- **Documentation:** `docs/CACHE_MANAGER.md` (detailed reference)
- **Module init:** `functions/market/__init__.py` (exports)

## What's Next?

1. See `docs/CACHE_MANAGER.md` for full API reference
2. Run `pytest tests/tech/unit/test_cache_manager.py` to see tests
3. Check `functions/market/cache.py` docstrings for details
4. Use in your functions with `@cache()` decorator

## Need Help?

- **Quick question?** Check docstrings in the code
- **Usage example?** See CACHE_MANAGER.md examples section
- **Debug issue?** Enable DEBUG logging to see cache operations
- **Modify behavior?** Update DEFAULT_TTL_SECONDS or cache config
