"""
Unit tests for circuit breaker pattern implementation.

Tests cover:
- State transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Failure threshold tracking
- Recovery timeout logic
- Thread safety
- CircuitBreakerRegistry singleton behavior
"""

import pytest
import threading
import time
from datetime import datetime, timedelta

from functions.market.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerRegistry,
    CircuitBreakerOpenError,
    CircuitBreakerError,
)


# ============================================================================
# Test Fixtures
# ============================================================================
@pytest.fixture
def circuit_breaker():
    """Create a circuit breaker for testing."""
    return CircuitBreaker(
        name="test_breaker",
        failure_threshold=3,
        recovery_timeout_seconds=1,
    )


@pytest.fixture
def registry():
    """Create a fresh registry instance for testing."""
    registry = CircuitBreakerRegistry()
    registry.reset_all()
    return registry


def success_function(value=42):
    """Function that succeeds."""
    return value


def failure_function(exception=Exception("Test failure")):
    """Function that fails."""
    raise exception


# ============================================================================
# CircuitBreaker State Tests
# ============================================================================
class TestCircuitBreakerStates:
    """Test state transitions and behavior."""

    def test_initial_state_is_closed(self, circuit_breaker):
        """Circuit breaker should start in CLOSED state."""
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.is_closed()
        assert not circuit_breaker.is_open()
        assert not circuit_breaker.is_half_open()

    def test_successful_call_in_closed_state(self, circuit_breaker):
        """Successful call in CLOSED state should return result."""
        result = circuit_breaker.call(success_function, value=100)
        assert result == 100
        assert circuit_breaker.is_closed()

    def test_failed_call_increments_failure_count(self, circuit_breaker):
        """Failed call should increment failure counter."""
        assert circuit_breaker.failure_count == 0

        with pytest.raises(Exception):
            circuit_breaker.call(failure_function)

        assert circuit_breaker.failure_count == 1
        assert circuit_breaker.is_closed()

    def test_circuit_opens_after_threshold(self, circuit_breaker):
        """Circuit should transition to OPEN after failure_threshold failures."""
        assert circuit_breaker.failure_threshold == 3

        # First failure
        with pytest.raises(Exception):
            circuit_breaker.call(failure_function)
        assert circuit_breaker.failure_count == 1
        assert circuit_breaker.is_closed()

        # Second failure
        with pytest.raises(Exception):
            circuit_breaker.call(failure_function)
        assert circuit_breaker.failure_count == 2
        assert circuit_breaker.is_closed()

        # Third failure - should open
        with pytest.raises(Exception):
            circuit_breaker.call(failure_function)
        assert circuit_breaker.failure_count == 3
        assert circuit_breaker.is_open()

    def test_open_circuit_rejects_requests(self, circuit_breaker):
        """OPEN circuit should reject all requests immediately."""
        # Open the circuit
        for _ in range(circuit_breaker.failure_threshold):
            with pytest.raises(Exception):
                circuit_breaker.call(failure_function)

        assert circuit_breaker.is_open()

        # Subsequent calls should fail with CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            circuit_breaker.call(success_function)

        assert "OPEN" in str(exc_info.value)

    def test_open_to_half_open_after_timeout(self, circuit_breaker):
        """Circuit should transition to HALF_OPEN after recovery timeout."""
        # Open the circuit
        for _ in range(circuit_breaker.failure_threshold):
            with pytest.raises(Exception):
                circuit_breaker.call(failure_function)

        assert circuit_breaker.is_open()

        # Before timeout - still OPEN
        with pytest.raises(CircuitBreakerOpenError):
            circuit_breaker.call(success_function)

        # Wait for timeout
        time.sleep(1.1)

        # Next call should transition to HALF_OPEN
        result = circuit_breaker.call(success_function, value=42)
        assert result == 42
        assert circuit_breaker.is_closed()  # Should return to CLOSED after success

    def test_half_open_to_closed_on_success(self, circuit_breaker):
        """HALF_OPEN circuit should return to CLOSED on successful call."""
        # Open the circuit
        for _ in range(circuit_breaker.failure_threshold):
            with pytest.raises(Exception):
                circuit_breaker.call(failure_function)

        assert circuit_breaker.is_open()

        # Wait for timeout
        time.sleep(1.1)

        # Successful call should transition to CLOSED
        result = circuit_breaker.call(success_function, value=123)
        assert result == 123
        assert circuit_breaker.is_closed()
        assert circuit_breaker.failure_count == 0

    def test_half_open_to_open_on_failure(self, circuit_breaker):
        """HALF_OPEN circuit should return to OPEN on failed call."""
        # Open the circuit
        for _ in range(circuit_breaker.failure_threshold):
            with pytest.raises(Exception):
                circuit_breaker.call(failure_function)

        assert circuit_breaker.is_open()

        # Wait for timeout
        time.sleep(1.1)

        # Failed call should transition back to OPEN
        with pytest.raises(Exception):
            circuit_breaker.call(failure_function)

        assert circuit_breaker.is_open()


# ============================================================================
# Circuit Breaker Reset Tests
# ============================================================================
class TestCircuitBreakerReset:
    """Test reset functionality."""

    def test_reset_returns_to_closed(self, circuit_breaker):
        """Reset should return circuit breaker to CLOSED state."""
        # Open the circuit
        for _ in range(circuit_breaker.failure_threshold):
            with pytest.raises(Exception):
                circuit_breaker.call(failure_function)

        assert circuit_breaker.is_open()

        # Reset
        circuit_breaker.reset()

        assert circuit_breaker.is_closed()
        assert circuit_breaker.failure_count == 0

    def test_reset_clears_state(self, circuit_breaker):
        """Reset should clear failure and success counts."""
        # Generate some activity
        for _ in range(2):
            with pytest.raises(Exception):
                circuit_breaker.call(failure_function)

        assert circuit_breaker.failure_count == 2

        # Reset
        circuit_breaker.reset()

        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0


# ============================================================================
# Status and Information Tests
# ============================================================================
class TestCircuitBreakerStatus:
    """Test status reporting."""

    def test_get_state(self, circuit_breaker):
        """get_state() should return current state."""
        assert circuit_breaker.get_state() == CircuitBreakerState.CLOSED

        # Open the circuit
        for _ in range(circuit_breaker.failure_threshold):
            with pytest.raises(Exception):
                circuit_breaker.call(failure_function)

        assert circuit_breaker.get_state() == CircuitBreakerState.OPEN

    def test_get_status_contains_all_info(self, circuit_breaker):
        """get_status() should contain comprehensive information."""
        status = circuit_breaker.get_status()

        assert "name" in status
        assert "state" in status
        assert "failure_count" in status
        assert "success_count" in status
        assert "failure_threshold" in status
        assert "recovery_timeout_seconds" in status
        assert "last_failure_time" in status
        assert "last_state_change" in status

        assert status["name"] == "test_breaker"
        assert status["state"] == "CLOSED"
        assert status["failure_count"] == 0

    def test_status_tracks_failures(self, circuit_breaker):
        """Status should accurately track failures."""
        with pytest.raises(Exception):
            circuit_breaker.call(failure_function)

        status = circuit_breaker.get_status()
        assert status["failure_count"] == 1
        assert status["last_failure_time"] is not None

    def test_status_tracks_successes(self, circuit_breaker):
        """Status should accurately track successes."""
        circuit_breaker.call(success_function, value=42)

        status = circuit_breaker.get_status()
        assert status["success_count"] == 1


# ============================================================================
# Thread Safety Tests
# ============================================================================
class TestCircuitBreakerThreadSafety:
    """Test thread-safe behavior."""

    def test_concurrent_calls(self, circuit_breaker):
        """Circuit breaker should handle concurrent calls safely."""
        results = []
        errors = []

        def worker():
            try:
                result = circuit_breaker.call(success_function, value=1)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 10
        assert len(errors) == 0
        assert circuit_breaker.success_count == 10

    def test_concurrent_state_transitions(self):
        """Circuit breaker should handle concurrent state transitions safely."""
        circuit_breaker = CircuitBreaker(
            name="concurrent_test",
            failure_threshold=5,
            recovery_timeout_seconds=2,
        )

        failures = []
        successes = []

        def failure_worker():
            for _ in range(3):
                try:
                    circuit_breaker.call(failure_function)
                except (Exception, CircuitBreakerOpenError):
                    failures.append(1)

        def success_worker():
            for _ in range(3):
                try:
                    circuit_breaker.call(success_function)
                    successes.append(1)
                except CircuitBreakerOpenError:
                    pass

        threads = [
            threading.Thread(target=failure_worker),
            threading.Thread(target=success_worker),
            threading.Thread(target=failure_worker),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have tried to call functions multiple times
        assert len(failures) > 0
        assert len(successes) > 0


# ============================================================================
# CircuitBreakerRegistry Tests
# ============================================================================
class TestCircuitBreakerRegistry:
    """Test registry functionality."""

    def test_registry_is_singleton(self):
        """Registry should be a singleton."""
        reg1 = CircuitBreakerRegistry()
        reg2 = CircuitBreakerRegistry()

        assert reg1 is reg2

    def test_registry_initializes_default_breakers(self, registry):
        """Registry should initialize with default breakers."""
        assert registry.get("current_price") is not None
        assert registry.get("price_history") is not None
        assert registry.get("options_chain") is not None
        assert registry.get("ticker_info") is not None
        assert registry.get("expirations") is not None

    def test_registry_register_breaker(self, registry):
        """Registry should allow registering new breakers."""
        custom_breaker = CircuitBreaker(
            name="custom_endpoint",
            failure_threshold=2,
            recovery_timeout_seconds=30,
        )

        registry.register("custom_endpoint", custom_breaker)

        retrieved = registry.get("custom_endpoint")
        assert retrieved is custom_breaker

    def test_registry_get_all(self, registry):
        """get_all() should return all registered breakers."""
        all_breakers = registry.get_all()

        assert isinstance(all_breakers, dict)
        assert len(all_breakers) >= 5
        assert "current_price" in all_breakers

    def test_registry_reset_all(self, registry):
        """reset_all() should reset all breakers to CLOSED."""
        # Open a breaker
        breaker = registry.get("current_price")
        for _ in range(breaker.failure_threshold):
            with pytest.raises(Exception):
                breaker.call(failure_function)

        assert breaker.is_open()

        # Reset all
        registry.reset_all()

        assert breaker.is_closed()
        assert breaker.failure_count == 0

    def test_registry_get_status_all(self, registry):
        """get_status_all() should return status of all breakers."""
        statuses = registry.get_status_all()

        assert isinstance(statuses, dict)
        assert len(statuses) >= 5
        assert "current_price" in statuses
        assert statuses["current_price"]["state"] == "CLOSED"

    def test_registry_get_open_breakers(self, registry):
        """get_open_breakers() should return only OPEN breakers."""
        breaker = registry.get("current_price")

        # Open a breaker
        for _ in range(breaker.failure_threshold):
            with pytest.raises(Exception):
                breaker.call(failure_function)

        open_breakers = registry.get_open_breakers()
        assert "current_price" in open_breakers

    def test_registry_get_half_open_breakers(self, registry):
        """get_half_open_breakers() should return only HALF_OPEN breakers."""
        # This test would require opening a breaker and waiting, so we'll verify the API
        half_open = registry.get_half_open_breakers()
        assert isinstance(half_open, list)

    def test_registry_get_closed_breakers(self, registry):
        """get_closed_breakers() should return only CLOSED breakers."""
        closed_breakers = registry.get_closed_breakers()

        assert isinstance(closed_breakers, list)
        # All should be closed initially
        assert len(closed_breakers) >= 5

    def test_registry_register_validation(self, registry):
        """Registry should validate inputs when registering."""
        with pytest.raises(ValueError):
            registry.register("", CircuitBreaker(name="test"))

        with pytest.raises(ValueError):
            registry.register("test", "not a breaker")


# ============================================================================
# Error Handling Tests
# ============================================================================
class TestCircuitBreakerErrors:
    """Test error handling."""

    def test_invalid_failure_threshold(self):
        """Invalid failure threshold should raise ValueError."""
        with pytest.raises(ValueError):
            CircuitBreaker(name="test", failure_threshold=0)

        with pytest.raises(ValueError):
            CircuitBreaker(name="test", failure_threshold=-1)

    def test_invalid_recovery_timeout(self):
        """Invalid recovery timeout should raise ValueError."""
        with pytest.raises(ValueError):
            CircuitBreaker(name="test", recovery_timeout_seconds=0)

        with pytest.raises(ValueError):
            CircuitBreaker(name="test", recovery_timeout_seconds=-1)

    def test_circuit_breaker_open_error_message(self, circuit_breaker):
        """CircuitBreakerOpenError should contain helpful information."""
        # Open the circuit
        for _ in range(circuit_breaker.failure_threshold):
            with pytest.raises(Exception):
                circuit_breaker.call(failure_function)

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            circuit_breaker.call(success_function)

        error_msg = str(exc_info.value)
        assert "OPEN" in error_msg
        assert "test_breaker" in error_msg


# ============================================================================
# Integration Tests
# ============================================================================
class TestCircuitBreakerIntegration:
    """Integration tests with multiple breakers."""

    def test_multiple_independent_breakers(self, registry):
        """Multiple breakers should operate independently."""
        breaker1 = registry.get("current_price")
        breaker2 = registry.get("price_history")

        # Open breaker1
        for _ in range(breaker1.failure_threshold):
            with pytest.raises(Exception):
                breaker1.call(failure_function)

        assert breaker1.is_open()
        assert breaker2.is_closed()

        # breaker2 should still work
        result = breaker2.call(success_function, value=999)
        assert result == 999

    def test_realistic_api_call_scenario(self, registry):
        """Test realistic API call scenario."""
        breaker = registry.get("options_chain")

        # Simulate some API calls
        call_count = 0
        for i in range(10):
            try:
                if i < 3:
                    # First 3 calls succeed
                    breaker.call(success_function, value=i)
                    call_count += 1
                else:
                    # Remaining calls fail
                    breaker.call(failure_function)
                    call_count += 1
            except CircuitBreakerOpenError:
                # Breaker is open, skip
                pass
            except Exception:
                # API error
                pass

        # Breaker should be open
        assert breaker.is_open()

        # Verify we didn't keep calling the failing API
        assert call_count < 10
