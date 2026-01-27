"""
TTL-based cache manager for market data with thread-safe operations.

Provides efficient in-memory caching with automatic expiration, memory management,
and comprehensive statistics tracking. Supports LRU eviction when max memory is exceeded.

Features:
    - TTL-based automatic expiration on access
    - Thread-safe with Lock synchronization
    - Memory usage tracking and limits
    - LRU eviction when max_size_mb exceeded
    - Comprehensive hit/miss statistics
    - Singleton cache manager pattern
    - Decorator support for automatic caching

Default TTL values:
    - current_price: 60 seconds
    - options_chain: 300 seconds (5 minutes)
    - price_history: 3600 seconds (1 hour)
    - ticker_info: 86400 seconds (1 day)
    - expirations: 1800 seconds (30 minutes)

Usage:
    from functions.market.cache import get_cache_manager, cache

    # Using singleton instance
    cache_mgr = get_cache_manager()
    cache_mgr.set("AAPL_price", 150.25, ttl_seconds=60)
    price = cache_mgr.get("AAPL_price")

    # Using decorator for automatic caching
    @cache(ttl_seconds=300)
    def fetch_option_chain(symbol: str):
        # Expensive operation
        return fetch_from_api(symbol)

    # Get statistics
    stats = cache_mgr.get_stats()
    print(f"Hit rate: {stats['hit_rate']:.1%}")
"""

import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Optional
from functools import lru_cache

from functions.util.logging_setup import get_logger

logger = get_logger(__name__)

# Default TTL values in seconds
DEFAULT_TTL_SECONDS = {
    "current_price": 60,
    "options_chain": 300,
    "price_history": 3600,
    "ticker_info": 86400,
    "expirations": 1800,
}


@dataclass
class CacheEntry:
    """Represents a single cache entry with TTL tracking.

    Attributes:
        key: Unique identifier for the cached value
        value: The actual cached data
        timestamp: When the entry was created (UTC)
        ttl_seconds: Time-to-live in seconds
    """

    key: str
    value: Any
    timestamp: datetime
    ttl_seconds: int

    def is_expired(self) -> bool:
        """Check if this entry has expired based on TTL.

        Returns:
            True if current time exceeds creation time + ttl_seconds
        """
        now = datetime.now(timezone.utc)
        elapsed = (now - self.timestamp).total_seconds()
        return elapsed > self.ttl_seconds

    def get_age_seconds(self) -> float:
        """Get the age of this entry in seconds.

        Returns:
            Number of seconds since this entry was created
        """
        now = datetime.now(timezone.utc)
        return (now - self.timestamp).total_seconds()

    def get_remaining_ttl(self) -> float:
        """Get remaining time-to-live in seconds.

        Returns:
            Seconds remaining before expiration (0 if expired)
        """
        remaining = self.ttl_seconds - self.get_age_seconds()
        return max(0, remaining)


class CacheManager:
    """Thread-safe TTL-based cache manager with memory management.

    Provides efficient in-memory caching with automatic expiration, memory tracking,
    and LRU eviction. All operations are thread-safe using a reentrant lock.

    Attributes:
        max_size_mb: Maximum cache size in megabytes
        _cache: Dictionary storing cache entries
        _access_order: List tracking access order for LRU eviction
        _lock: Threading lock for thread safety
        _hit_count: Number of cache hits
        _miss_count: Number of cache misses
    """

    def __init__(self, max_size_mb: int = 100):
        """Initialize the cache manager.

        Args:
            max_size_mb: Maximum cache size in megabytes. Defaults to 100MB.

        Raises:
            ValueError: If max_size_mb is not positive
        """
        if max_size_mb <= 0:
            raise ValueError(f"max_size_mb must be positive, got {max_size_mb}")

        self.max_size_mb = max_size_mb
        self._cache: dict[str, CacheEntry] = {}
        self._access_order: list[str] = []  # Track LRU access order
        self._lock = threading.RLock()  # Reentrant lock for nested calls
        self._hit_count = 0
        self._miss_count = 0

        logger.info(f"Cache manager initialized with max size {max_size_mb}MB")

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache if it exists and hasn't expired.

        Automatically removes expired entries. Updates access order for LRU tracking.
        Increments hit/miss statistics.

        Args:
            key: The cache key to retrieve

        Returns:
            The cached value if found and not expired, None otherwise

        Example:
            value = cache_mgr.get("AAPL_price")
            if value is not None:
                print(f"Price: {value}")
        """
        with self._lock:
            if key not in self._cache:
                self._miss_count += 1
                logger.debug(f"Cache miss for key: {key}")
                return None

            entry = self._cache[key]

            # Check if expired
            if entry.is_expired():
                self._miss_count += 1
                logger.debug(f"Cache expired for key: {key} (age: {entry.get_age_seconds():.1f}s, ttl: {entry.ttl_seconds}s)")
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                return None

            # Update access order for LRU
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

            self._hit_count += 1
            logger.debug(f"Cache hit for key: {key} (age: {entry.get_age_seconds():.1f}s)")
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Store value in cache with specified TTL.

        Automatically evicts oldest entries (LRU) if cache exceeds max_size_mb.
        Updates access order for LRU tracking.

        Args:
            key: The cache key
            value: The value to cache
            ttl_seconds: Time-to-live in seconds

        Raises:
            ValueError: If ttl_seconds is not positive

        Example:
            cache_mgr.set("AAPL_price", 150.25, ttl_seconds=60)
        """
        if ttl_seconds <= 0:
            raise ValueError(f"ttl_seconds must be positive, got {ttl_seconds}")

        with self._lock:
            # Create new entry
            entry = CacheEntry(
                key=key,
                value=value,
                timestamp=datetime.now(timezone.utc),
                ttl_seconds=ttl_seconds,
            )

            # Remove old entry if exists
            if key in self._cache:
                logger.debug(f"Updating cache entry: {key}")
                if key in self._access_order:
                    self._access_order.remove(key)
            else:
                logger.debug(f"Creating new cache entry: {key}")

            self._cache[key] = entry
            self._access_order.append(key)

            # Evict if size exceeded
            self._evict_if_needed()

    def delete(self, key: str) -> bool:
        """Remove entry from cache.

        Args:
            key: The cache key to delete

        Returns:
            True if entry was deleted, False if not found

        Example:
            if cache_mgr.delete("AAPL_price"):
                print("Entry deleted")
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                logger.debug(f"Cache entry deleted: {key}")
                return True
            logger.debug(f"Cache entry not found for deletion: {key}")
            return False

    def clear(self) -> None:
        """Clear all entries from cache.

        Resets statistics counters.

        Example:
            cache_mgr.clear()
        """
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self._hit_count = 0
            self._miss_count = 0
            logger.info("Cache cleared completely (all entries and stats reset)")

    def get_stats(self) -> dict[str, Any]:
        """Get comprehensive cache statistics.

        Returns:
            Dictionary containing:
                - hit_count: Total cache hits
                - miss_count: Total cache misses
                - hit_rate: Hit rate as decimal (0.0-1.0)
                - entry_count: Number of entries in cache
                - current_size_bytes: Current memory usage
                - current_size_mb: Current memory usage in MB
                - max_size_mb: Maximum allowed cache size
                - size_utilization: Percentage of max size used (0-100)
                - entries: List of entry metadata sorted by expiration time

        Example:
            stats = cache_mgr.get_stats()
            print(f"Hit rate: {stats['hit_rate']:.1%}")
            print(f"Size: {stats['current_size_mb']:.1f}MB of {stats['max_size_mb']}MB")
        """
        with self._lock:
            total_requests = self._hit_count + self._miss_count
            hit_rate = (
                self._hit_count / total_requests if total_requests > 0 else 0.0
            )

            current_size_bytes = self._calculate_cache_size()
            current_size_mb = current_size_bytes / (1024 * 1024)
            size_utilization = (current_size_mb / self.max_size_mb) * 100 if self.max_size_mb > 0 else 0

            # Get entry details sorted by remaining TTL
            entries = []
            for key, entry in self._cache.items():
                entries.append({
                    "key": key,
                    "size_bytes": sys.getsizeof(entry.value),
                    "age_seconds": entry.get_age_seconds(),
                    "remaining_ttl": entry.get_remaining_ttl(),
                    "expired": entry.is_expired(),
                })
            entries.sort(key=lambda x: x["remaining_ttl"])

            stats = {
                "hit_count": self._hit_count,
                "miss_count": self._miss_count,
                "hit_rate": hit_rate,
                "entry_count": len(self._cache),
                "current_size_bytes": current_size_bytes,
                "current_size_mb": round(current_size_mb, 2),
                "max_size_mb": self.max_size_mb,
                "size_utilization": round(size_utilization, 1),
                "entries": entries,
            }

            return stats

    def _calculate_cache_size(self) -> int:
        """Calculate total memory used by cache in bytes.

        Uses sys.getsizeof() for each entry. Called within lock context.

        Returns:
            Total size in bytes
        """
        total_size = 0
        for entry in self._cache.values():
            # Size of entry object + size of the cached value
            total_size += sys.getsizeof(entry)
            total_size += sys.getsizeof(entry.value)
        return total_size

    def _evict_if_needed(self) -> None:
        """Evict least recently used entries if cache exceeds max size.

        Called within lock context after setting new entries.
        """
        max_size_bytes = self.max_size_mb * 1024 * 1024
        current_size = self._calculate_cache_size()

        if current_size <= max_size_bytes:
            return

        logger.warning(
            f"Cache size ({current_size / (1024*1024):.1f}MB) exceeds limit "
            f"({self.max_size_mb}MB). Starting LRU eviction."
        )

        # Evict oldest entries until we're under limit
        evicted_count = 0
        while current_size > max_size_bytes and self._access_order:
            lru_key = self._access_order.pop(0)
            if lru_key in self._cache:
                evicted_size = sys.getsizeof(self._cache[lru_key].value)
                del self._cache[lru_key]
                current_size -= evicted_size
                evicted_count += 1
                logger.debug(f"Evicted cache entry (LRU): {lru_key}")

        logger.info(f"LRU eviction completed: {evicted_count} entries removed")


# Global singleton instance
_cache_manager: Optional[CacheManager] = None
_cache_manager_lock = threading.Lock()


def get_cache_manager(max_size_mb: int = 100) -> CacheManager:
    """Get or create the singleton cache manager instance.

    Thread-safe creation of singleton. If called multiple times with different
    max_size_mb values, the first initialization is used.

    Args:
        max_size_mb: Maximum cache size in MB (only used on first call)

    Returns:
        The singleton CacheManager instance

    Example:
        cache_mgr = get_cache_manager()
        cache_mgr.set("key", "value", ttl_seconds=60)
    """
    global _cache_manager

    if _cache_manager is None:
        with _cache_manager_lock:
            if _cache_manager is None:
                logger.info(f"Creating singleton cache manager (max_size: {max_size_mb}MB)")
                _cache_manager = CacheManager(max_size_mb=max_size_mb)

    return _cache_manager


def cache(ttl_seconds: int = 300) -> Callable:
    """Decorator for automatic result caching with TTL.

    Caches function results based on function name and arguments.
    Cache key is generated from function name and stringified arguments.

    Args:
        ttl_seconds: Time-to-live for cached results in seconds

    Returns:
        Decorator function

    Example:
        @cache(ttl_seconds=300)
        def fetch_option_chain(symbol: str):
            # Expensive operation
            return fetch_from_api(symbol)

        # First call: executes function and caches result
        result1 = fetch_option_chain("AAPL")

        # Second call (within 5 min): returns cached result
        result2 = fetch_option_chain("AAPL")  # Same result, no API call

        # Third call (after 5 min): cache expired, executes function again
        result3 = fetch_option_chain("AAPL")

    Note:
        - Function must have deterministic arguments (no mutable defaults)
        - Cache key includes function name, so different functions won't collide
        - Cannot cache async functions (use manual caching instead)
    """
    if ttl_seconds <= 0:
        raise ValueError(f"ttl_seconds must be positive, got {ttl_seconds}")

    def decorator(func: Callable) -> Callable:
        cache_mgr = get_cache_manager()

        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Generate cache key from function and arguments
            arg_str = "_".join(str(arg) for arg in args)
            kwarg_str = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
            parts = [func.__name__]
            if arg_str:
                parts.append(arg_str)
            if kwarg_str:
                parts.append(kwarg_str)
            cache_key = "|".join(parts)

            # Try to get from cache
            cached_result = cache_mgr.get(cache_key)
            if cached_result is not None:
                logger.debug(
                    f"Cache hit for decorated function: {func.__name__}"
                )
                return cached_result

            # Cache miss: execute function and cache result
            logger.debug(
                f"Cache miss for decorated function: {func.__name__}"
            )
            result = func(*args, **kwargs)
            cache_mgr.set(cache_key, result, ttl_seconds=ttl_seconds)

            return result

        return wrapper

    return decorator


# Statistics logging helper
def log_cache_stats() -> None:
    """Log current cache statistics to info level.

    Useful for debugging and monitoring cache performance.

    Example:
        from functions.market.cache import log_cache_stats
        log_cache_stats()  # Prints cache stats
    """
    cache_mgr = get_cache_manager()
    stats = cache_mgr.get_stats()

    logger.info("=" * 60)
    logger.info("CACHE STATISTICS")
    logger.info("=" * 60)
    logger.info(f"Hits: {stats['hit_count']} | Misses: {stats['miss_count']} | "
                f"Hit Rate: {stats['hit_rate']:.1%}")
    logger.info(f"Entries: {stats['entry_count']} | "
                f"Size: {stats['current_size_mb']:.1f}MB / {stats['max_size_mb']}MB "
                f"({stats['size_utilization']:.1f}%)")
    logger.info("=" * 60)

    # Log expiring entries
    if stats['entries']:
        logger.info("Next 3 entries to expire:")
        for entry in stats['entries'][:3]:
            status = "EXPIRED" if entry['expired'] else "active"
            logger.info(
                f"  - {entry['key']}: {entry['remaining_ttl']:.1f}s remaining [{status}]"
            )
