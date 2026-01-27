"""Unit tests for the TTL-based cache manager.

Tests cover:
    - Basic cache operations (get, set, delete, clear)
    - TTL expiration and auto-removal
    - Memory management and LRU eviction
    - Thread safety
    - Statistics tracking
    - Singleton pattern
    - Cache decorator
"""

import time
import threading
from datetime import datetime, timezone

import pytest

from functions.market.cache import (
    CacheEntry,
    CacheManager,
    DEFAULT_TTL_SECONDS,
    cache,
    get_cache_manager,
    log_cache_stats,
)


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_cache_entry_creation(self):
        """Test creating a CacheEntry."""
        now = datetime.now(timezone.utc)
        entry = CacheEntry(
            key="test_key",
            value={"data": "test_value"},
            timestamp=now,
            ttl_seconds=60,
        )

        assert entry.key == "test_key"
        assert entry.value == {"data": "test_value"}
        assert entry.timestamp == now
        assert entry.ttl_seconds == 60

    def test_is_expired_fresh_entry(self):
        """Test that fresh entry is not expired."""
        now = datetime.now(timezone.utc)
        entry = CacheEntry(
            key="test",
            value="value",
            timestamp=now,
            ttl_seconds=60,
        )

        assert not entry.is_expired()

    def test_is_expired_after_ttl(self):
        """Test that entry expires after TTL."""
        past = datetime.now(timezone.utc)
        entry = CacheEntry(
            key="test",
            value="value",
            timestamp=past,
            ttl_seconds=1,  # 1 second TTL
        )

        assert not entry.is_expired()
        time.sleep(1.1)  # Wait for expiration
        assert entry.is_expired()

    def test_get_age_seconds(self):
        """Test age calculation."""
        past = datetime.now(timezone.utc)
        entry = CacheEntry(
            key="test",
            value="value",
            timestamp=past,
            ttl_seconds=60,
        )

        time.sleep(0.1)
        age = entry.get_age_seconds()
        assert 0.09 < age < 0.2  # Allow some timing variance

    def test_get_remaining_ttl(self):
        """Test remaining TTL calculation."""
        now = datetime.now(timezone.utc)
        entry = CacheEntry(
            key="test",
            value="value",
            timestamp=now,
            ttl_seconds=10,
        )

        remaining = entry.get_remaining_ttl()
        assert 9.9 < remaining <= 10  # Should be close to 10 seconds


class TestCacheManager:
    """Tests for CacheManager class."""

    def setup_method(self):
        """Create fresh CacheManager for each test."""
        self.cache = CacheManager(max_size_mb=1)  # Small cache for testing

    def test_initialization(self):
        """Test cache manager initialization."""
        assert self.cache.max_size_mb == 1
        assert len(self.cache._cache) == 0
        assert self.cache._hit_count == 0
        assert self.cache._miss_count == 0

    def test_init_invalid_max_size(self):
        """Test initialization with invalid max_size_mb."""
        with pytest.raises(ValueError):
            CacheManager(max_size_mb=0)

        with pytest.raises(ValueError):
            CacheManager(max_size_mb=-1)

    def test_set_and_get(self):
        """Test basic set and get operations."""
        self.cache.set("key1", "value1", ttl_seconds=60)

        result = self.cache.get("key1")
        assert result == "value1"

    def test_get_nonexistent_key(self):
        """Test getting a key that doesn't exist."""
        result = self.cache.get("nonexistent")
        assert result is None

    def test_set_invalid_ttl(self):
        """Test setting with invalid TTL."""
        with pytest.raises(ValueError):
            self.cache.set("key", "value", ttl_seconds=0)

        with pytest.raises(ValueError):
            self.cache.set("key", "value", ttl_seconds=-1)

    def test_get_expired_entry(self):
        """Test that expired entries are automatically removed."""
        self.cache.set("key1", "value1", ttl_seconds=1)

        # Should be available immediately
        assert self.cache.get("key1") == "value1"

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired and removed
        assert self.cache.get("key1") is None

        # Should be gone from cache
        assert "key1" not in self.cache._cache

    def test_delete_existing_key(self):
        """Test deleting an existing key."""
        self.cache.set("key1", "value1", ttl_seconds=60)

        success = self.cache.delete("key1")
        assert success is True

        result = self.cache.get("key1")
        assert result is None

    def test_delete_nonexistent_key(self):
        """Test deleting a non-existent key."""
        success = self.cache.delete("nonexistent")
        assert success is False

    def test_clear(self):
        """Test clearing the cache."""
        self.cache.set("key1", "value1", ttl_seconds=60)
        self.cache.set("key2", "value2", ttl_seconds=60)

        assert len(self.cache._cache) == 2

        self.cache.clear()

        assert len(self.cache._cache) == 0
        assert self.cache._hit_count == 0
        assert self.cache._miss_count == 0

    def test_statistics_hit_miss(self):
        """Test hit/miss statistics tracking."""
        self.cache.set("key1", "value1", ttl_seconds=60)

        # Hit
        self.cache.get("key1")
        assert self.cache._hit_count == 1
        assert self.cache._miss_count == 0

        # Hit
        self.cache.get("key1")
        assert self.cache._hit_count == 2
        assert self.cache._miss_count == 0

        # Miss
        self.cache.get("nonexistent")
        assert self.cache._hit_count == 2
        assert self.cache._miss_count == 1

    def test_get_stats(self):
        """Test statistics retrieval."""
        self.cache.set("key1", "value1", ttl_seconds=60)
        self.cache.set("key2", "value2", ttl_seconds=60)
        self.cache.get("key1")  # Hit
        self.cache.get("key2")  # Hit
        self.cache.get("nonexistent")  # Miss

        stats = self.cache.get_stats()

        assert stats["hit_count"] == 2
        assert stats["miss_count"] == 1
        assert stats["hit_rate"] == pytest.approx(2 / 3)
        assert stats["entry_count"] == 2
        assert stats["current_size_mb"] > 0
        assert stats["max_size_mb"] == 1

    def test_stats_hit_rate_no_requests(self):
        """Test hit rate when no requests made."""
        stats = self.cache.get_stats()
        assert stats["hit_rate"] == 0.0

    def test_update_existing_entry(self):
        """Test updating an existing cache entry."""
        self.cache.set("key1", "value1", ttl_seconds=60)
        self.cache.set("key1", "updated_value", ttl_seconds=60)

        result = self.cache.get("key1")
        assert result == "updated_value"

    def test_different_ttl_values(self):
        """Test entries with different TTL values."""
        self.cache.set("short", "value1", ttl_seconds=1)
        self.cache.set("long", "value2", ttl_seconds=10)

        # Both available immediately
        assert self.cache.get("short") == "value1"
        assert self.cache.get("long") == "value2"

        # Wait for short to expire
        time.sleep(1.1)

        assert self.cache.get("short") is None
        assert self.cache.get("long") == "value2"

    def test_thread_safety_concurrent_sets(self):
        """Test thread-safe concurrent set operations."""
        results = []

        def set_values(start: int, count: int):
            for i in range(start, start + count):
                self.cache.set(f"key_{i}", f"value_{i}", ttl_seconds=60)

        threads = [
            threading.Thread(target=set_values, args=(0, 50)),
            threading.Thread(target=set_values, args=(50, 50)),
            threading.Thread(target=set_values, args=(100, 50)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All values should be accessible
        assert len(self.cache._cache) == 150

    def test_thread_safety_concurrent_gets(self):
        """Test thread-safe concurrent get operations."""
        # Populate cache
        for i in range(100):
            self.cache.set(f"key_{i}", f"value_{i}", ttl_seconds=60)

        results = []

        def get_values():
            for i in range(100):
                value = self.cache.get(f"key_{i}")
                results.append(value)

        threads = [
            threading.Thread(target=get_values),
            threading.Thread(target=get_values),
            threading.Thread(target=get_values),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have 300 results (100 keys x 3 threads)
        assert len(results) == 300
        assert all(v is not None for v in results)

    def test_lru_eviction_on_size_limit(self):
        """Test LRU eviction when cache exceeds max size."""
        # Small cache (1MB) should trigger eviction
        small_cache = CacheManager(max_size_mb=0.001)  # ~1KB

        # Add entries - should trigger LRU eviction
        for i in range(5):
            value = "x" * 1000  # ~1KB each
            small_cache.set(f"key_{i}", value, ttl_seconds=60)

        # Not all entries should remain due to eviction
        stats = small_cache.get_stats()
        assert stats["entry_count"] < 5

    def test_lru_eviction_order(self):
        """Test that LRU eviction removes oldest accessed entries."""
        # Small cache
        small_cache = CacheManager(max_size_mb=0.001)

        # Add and access entries in order
        for i in range(3):
            value = "x" * 1000
            small_cache.set(f"key_{i}", value, ttl_seconds=60)

        # Access key_0 multiple times to make it most recent
        small_cache.get("key_0")
        small_cache.get("key_0")

        # Add one more entry to trigger eviction
        small_cache.set("key_new", "x" * 1000, ttl_seconds=60)

        # key_0 should still exist (most recently used)
        assert small_cache.get("key_0") is not None

    def test_entries_sorted_by_ttl(self):
        """Test that stats entries are sorted by remaining TTL."""
        self.cache.set("key1", "value1", ttl_seconds=30)
        time.sleep(0.1)
        self.cache.set("key2", "value2", ttl_seconds=10)

        stats = self.cache.get_stats()
        entries = stats["entries"]

        # key2 should have less remaining TTL
        assert entries[0]["key"] == "key2"
        assert entries[1]["key"] == "key1"

    def test_size_calculation(self):
        """Test that cache size is calculated correctly."""
        self.cache.set("key1", {"data": "test"}, ttl_seconds=60)

        stats = self.cache.get_stats()
        assert stats["current_size_bytes"] > 0
        assert stats["current_size_mb"] > 0

    def test_size_utilization_percentage(self):
        """Test size utilization percentage calculation."""
        small_cache = CacheManager(max_size_mb=10)
        small_cache.set("key1", "value1" * 100, ttl_seconds=60)

        stats = small_cache.get_stats()
        assert 0 <= stats["size_utilization"] <= 100


class TestCacheDecorator:
    """Tests for the @cache decorator."""

    def setup_method(self):
        """Reset cache before each test."""
        from functions.market import cache as cache_module

        if hasattr(cache_module, "_cache_manager"):
            cache_module._cache_manager = None

    def test_cache_decorator_basic(self):
        """Test basic caching with decorator."""
        call_count = 0

        @cache(ttl_seconds=60)
        def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call should execute function
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call should use cache
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Function not called again

    def test_cache_decorator_different_args(self):
        """Test decorator caching with different arguments."""
        call_count = 0

        @cache(ttl_seconds=60)
        def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # Different arguments should not use cache
        result1 = expensive_function(5)
        result2 = expensive_function(10)

        assert result1 == 10
        assert result2 == 20
        assert call_count == 2

    def test_cache_decorator_with_kwargs(self):
        """Test decorator caching with keyword arguments."""
        call_count = 0

        @cache(ttl_seconds=60)
        def expensive_function(x: int, multiplier: int = 2) -> int:
            nonlocal call_count
            call_count += 1
            return x * multiplier

        # Call with same args
        result1 = expensive_function(5, multiplier=2)
        result2 = expensive_function(5, multiplier=2)

        assert result1 == 10
        assert result2 == 10
        assert call_count == 1

        # Call with different kwargs
        result3 = expensive_function(5, multiplier=3)
        assert result3 == 15
        assert call_count == 2

    def test_cache_decorator_expiration(self):
        """Test decorator cache expiration."""
        call_count = 0

        @cache(ttl_seconds=1)
        def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call
        result1 = expensive_function(5)
        assert call_count == 1

        # Second call within TTL (should use cache)
        result2 = expensive_function(5)
        assert call_count == 1

        # Wait for expiration
        time.sleep(1.1)

        # Third call after expiration (should execute function)
        result3 = expensive_function(5)
        assert call_count == 2

    def test_cache_decorator_invalid_ttl(self):
        """Test decorator with invalid TTL."""
        with pytest.raises(ValueError):
            @cache(ttl_seconds=0)
            def func():
                pass

    def test_cache_decorator_return_value(self):
        """Test that decorator preserves return values."""
        @cache(ttl_seconds=60)
        def get_complex_object():
            return {"key": "value", "nested": {"data": [1, 2, 3]}}

        result = get_complex_object()
        assert result == {"key": "value", "nested": {"data": [1, 2, 3]}}


class TestSingletonPattern:
    """Tests for singleton cache manager pattern."""

    def test_singleton_creation(self):
        """Test that get_cache_manager returns singleton."""
        from functions.market import cache as cache_module

        # Reset singleton
        cache_module._cache_manager = None

        cache1 = get_cache_manager(max_size_mb=100)
        cache2 = get_cache_manager(max_size_mb=200)  # Max_size ignored

        assert cache1 is cache2
        assert cache1.max_size_mb == 100  # First initialization

    def test_singleton_persistence(self):
        """Test that singleton persists across calls."""
        from functions.market import cache as cache_module

        # Reset singleton
        cache_module._cache_manager = None

        cache1 = get_cache_manager()
        cache1.set("key1", "value1", ttl_seconds=60)

        cache2 = get_cache_manager()
        result = cache2.get("key1")

        assert result == "value1"


class TestDefaultTTLValues:
    """Tests for default TTL constants."""

    def test_default_ttl_constants(self):
        """Test that default TTL values are set."""
        assert DEFAULT_TTL_SECONDS["current_price"] == 60
        assert DEFAULT_TTL_SECONDS["options_chain"] == 300
        assert DEFAULT_TTL_SECONDS["price_history"] == 3600
        assert DEFAULT_TTL_SECONDS["ticker_info"] == 86400
        assert DEFAULT_TTL_SECONDS["expirations"] == 1800


class TestLoggingFunction:
    """Tests for cache statistics logging."""

    def test_log_cache_stats_runs(self):
        """Test that log_cache_stats runs without error."""
        cache_mgr = get_cache_manager()
        cache_mgr.set("key1", "value1", ttl_seconds=60)

        # Should not raise any exception
        log_cache_stats()


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def setup_method(self):
        """Create fresh CacheManager for each test."""
        self.cache = CacheManager(max_size_mb=1)

    def test_cache_none_value(self):
        """Test caching None values."""
        self.cache.set("key1", None, ttl_seconds=60)
        result = self.cache.get("key1")
        assert result is None

    def test_cache_empty_dict(self):
        """Test caching empty dictionary."""
        self.cache.set("key1", {}, ttl_seconds=60)
        result = self.cache.get("key1")
        assert result == {}

    def test_cache_empty_list(self):
        """Test caching empty list."""
        self.cache.set("key1", [], ttl_seconds=60)
        result = self.cache.get("key1")
        assert result == []

    def test_cache_large_object(self):
        """Test caching large objects."""
        large_obj = {f"key_{i}": f"value_{i}" for i in range(1000)}
        self.cache.set("large", large_obj, ttl_seconds=60)
        result = self.cache.get("large")
        assert len(result) == 1000

    def test_cache_special_characters_in_key(self):
        """Test keys with special characters."""
        special_key = "key-with-special_chars.123"
        self.cache.set(special_key, "value", ttl_seconds=60)
        result = self.cache.get(special_key)
        assert result == "value"

    def test_very_short_ttl(self):
        """Test with very short TTL."""
        self.cache.set("key1", "value1", ttl_seconds=1)
        time.sleep(0.5)
        assert self.cache.get("key1") == "value1"

        time.sleep(0.6)
        assert self.cache.get("key1") is None

    def test_very_long_ttl(self):
        """Test with very long TTL."""
        self.cache.set("key1", "value1", ttl_seconds=86400)
        result = self.cache.get("key1")
        assert result == "value1"
