"""Market data fetching and caching module.

Provides functionality for fetching market data from external sources (Yahoo Finance)
and caching it efficiently with TTL-based expiration.

Main exports:
    - CacheManager: TTL-based cache with memory management
    - CacheEntry: Individual cache entry with expiration tracking
    - get_cache_manager(): Get singleton cache manager instance
    - cache: Decorator for automatic result caching
    - DEFAULT_TTL_SECONDS: Default TTL values for different data types
    - log_cache_stats(): Log cache performance statistics
"""

from functions.market.cache import (
    CacheEntry,
    CacheManager,
    DEFAULT_TTL_SECONDS,
    cache,
    get_cache_manager,
    log_cache_stats,
)

__all__ = [
    "CacheEntry",
    "CacheManager",
    "DEFAULT_TTL_SECONDS",
    "cache",
    "get_cache_manager",
    "log_cache_stats",
]
