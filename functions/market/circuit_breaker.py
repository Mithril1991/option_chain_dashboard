"""
Circuit breaker pattern for API resilience.

Implements the circuit breaker pattern to handle API failures gracefully:
- CLOSED: Normal operation, requests pass through
- OPEN: Service failing, requests rejected immediately
- HALF_OPEN: Testing recovery, allow single request to test service health

State transitions:
- CLOSED -> OPEN: After failure_threshold consecutive failures
- OPEN -> HALF_OPEN: After recovery_timeout_seconds elapsed
- HALF_OPEN -> CLOSED: If next call succeeds
- HALF_OPEN -> OPEN: If next call fails

Usage:
    from functions.market.circuit_breaker import CircuitBreakerRegistry

    # Get a circuit breaker for an endpoint
    registry = CircuitBreakerRegistry()
    breaker = registry.get("current_price")

    # Use it to wrap API calls
    try:
        result = breaker.call(fetch_price, symbol="AAPL")
        print(f"Price: {result}")
    except CircuitBreakerOpenError:
        print("Service temporarily unavailable, using cached data")

    # Check breaker state
    if breaker.is_open():
        logger.warning(f"Circuit breaker for {breaker.name} is OPEN")

Thread-safe implementation using threading.Lock for state transitions.
All state changes are logged with timestamps and failure/success counts.
"""

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional

from functions.util.logging_setup import get_logger

logger = get_logger(__name__)


# ============================================================================
# Circuit Breaker State Enum
# ============================================================================
class CircuitBreakerState(str, Enum):
    """Circuit breaker operational states."""

    CLOSED = "CLOSED"  # Normal operation, requests pass through
    OPEN = "OPEN"  # Service failing, requests rejected
    HALF_OPEN = "HALF_OPEN"  # Testing recovery, allow single request


# ============================================================================
# Custom Exceptions
# ============================================================================
class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is OPEN and request is rejected."""

    pass


class CircuitBreakerError(Exception):
    """Base exception for circuit breaker errors."""

    pass


# ============================================================================
# Circuit Breaker Implementation
# ============================================================================
@dataclass
class CircuitBreaker:
    """
    Circuit breaker for protecting API calls from cascading failures.

    Tracks failures and successes, automatically transitioning between states
    to prevent repeated calls to failing services.

    Attributes:
        name: Identifier for this circuit breaker (e.g., "current_price")
        failure_threshold: Number of consecutive failures before opening
        recovery_timeout_seconds: Seconds to wait before attempting recovery
        state: Current state (CLOSED, OPEN, or HALF_OPEN)
        failure_count: Number of consecutive failures in CLOSED state
        last_failure_time: Timestamp of most recent failure
        last_state_change: Timestamp of most recent state transition
    """

    name: str
    failure_threshold: int = 5
    recovery_timeout_seconds: int = 60

    # State management
    state: CircuitBreakerState = field(default=CircuitBreakerState.CLOSED)
    failure_count: int = field(default=0)
    success_count: int = field(default=0)
    last_failure_time: Optional[datetime] = field(default=None)
    last_state_change: datetime = field(default_factory=datetime.utcnow)

    # Thread safety
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.failure_threshold < 1:
            raise ValueError(f"failure_threshold must be >= 1, got {self.failure_threshold}")
        if self.recovery_timeout_seconds < 1:
            raise ValueError(
                f"recovery_timeout_seconds must be >= 1, got {self.recovery_timeout_seconds}"
            )
        logger.info(
            f"CircuitBreaker '{self.name}' initialized: "
            f"threshold={self.failure_threshold}, "
            f"timeout={self.recovery_timeout_seconds}s"
        )

    def call(self, func: Callable, *args, **kwargs) -> Optional[Any]:
        """
        Execute a function through the circuit breaker.

        If CLOSED: Execute function normally
        If OPEN: Raise CircuitBreakerOpenError immediately
        If HALF_OPEN: Execute function to test recovery

        Args:
            func: Callable to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func execution

        Raises:
            CircuitBreakerOpenError: If breaker is OPEN
            Exception: Any exception raised by func (if breaker allows execution)
        """
        with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_recovery():
                    logger.info(
                        f"CircuitBreaker '{self.name}' transitioning to HALF_OPEN "
                        f"(recovery timeout elapsed)"
                    )
                    self.state = CircuitBreakerState.HALF_OPEN
                else:
                    remaining = self._time_until_recovery()
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Service unavailable. Retry in {remaining:.1f}s"
                    )

        # Execute the function
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Handle successful function execution."""
        with self._lock:
            self.success_count += 1
            if self.state == CircuitBreakerState.HALF_OPEN:
                logger.info(
                    f"CircuitBreaker '{self.name}' transitioning to CLOSED "
                    f"(recovery successful)"
                )
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.last_state_change = datetime.utcnow()

    def _on_failure(self) -> None:
        """Handle failed function execution."""
        with self._lock:
            self.last_failure_time = datetime.utcnow()
            self.failure_count += 1

            if self.state == CircuitBreakerState.HALF_OPEN:
                logger.warning(
                    f"CircuitBreaker '{self.name}' transitioning to OPEN "
                    f"(recovery failed)"
                )
                self.state = CircuitBreakerState.OPEN
                self.last_state_change = datetime.utcnow()
            elif self.state == CircuitBreakerState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    logger.error(
                        f"CircuitBreaker '{self.name}' transitioning to OPEN "
                        f"({self.failure_count} consecutive failures)"
                    )
                    self.state = CircuitBreakerState.OPEN
                    self.last_state_change = datetime.utcnow()
                else:
                    logger.warning(
                        f"CircuitBreaker '{self.name}' failure count: "
                        f"{self.failure_count}/{self.failure_threshold}"
                    )

    def _should_attempt_recovery(self) -> bool:
        """Check if recovery timeout has elapsed."""
        if self.last_failure_time is None:
            return False
        timeout = timedelta(seconds=self.recovery_timeout_seconds)
        return datetime.utcnow() >= self.last_failure_time + timeout

    def _time_until_recovery(self) -> float:
        """Return seconds until recovery can be attempted."""
        if self.last_failure_time is None:
            return 0.0
        timeout = timedelta(seconds=self.recovery_timeout_seconds)
        recovery_time = self.last_failure_time + timeout
        remaining = (recovery_time - datetime.utcnow()).total_seconds()
        return max(0.0, remaining)

    def is_open(self) -> bool:
        """Check if circuit breaker is OPEN."""
        with self._lock:
            return self.state == CircuitBreakerState.OPEN

    def is_half_open(self) -> bool:
        """Check if circuit breaker is HALF_OPEN."""
        with self._lock:
            return self.state == CircuitBreakerState.HALF_OPEN

    def is_closed(self) -> bool:
        """Check if circuit breaker is CLOSED (normal operation)."""
        with self._lock:
            return self.state == CircuitBreakerState.CLOSED

    def get_state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        with self._lock:
            return self.state

    def reset(self) -> None:
        """Reset circuit breaker to CLOSED state."""
        with self._lock:
            old_state = self.state
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self.last_state_change = datetime.utcnow()
            logger.info(
                f"CircuitBreaker '{self.name}' reset from {old_state} to CLOSED"
            )

    def get_status(self) -> dict[str, Any]:
        """
        Get detailed status of circuit breaker.

        Returns:
            Dictionary with state, counts, and timing information
        """
        with self._lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout_seconds": self.recovery_timeout_seconds,
                "last_failure_time": (
                    self.last_failure_time.isoformat() if self.last_failure_time else None
                ),
                "last_state_change": self.last_state_change.isoformat(),
                "time_until_recovery_seconds": (
                    self._time_until_recovery()
                    if self.state == CircuitBreakerState.OPEN
                    else None
                ),
            }


# ============================================================================
# Circuit Breaker Registry (Singleton)
# ============================================================================
class CircuitBreakerRegistry:
    """
    Singleton registry for managing circuit breakers.

    Provides centralized management of multiple circuit breakers for
    different endpoints/services. Ensures only one instance exists.

    Example:
        registry = CircuitBreakerRegistry()
        breaker = registry.get("current_price")
        registry.reset_all()
    """

    _instance: Optional["CircuitBreakerRegistry"] = None
    _lock: threading.Lock = threading.Lock()

    # Default per-endpoint circuit breaker configurations
    _default_breakers: dict[str, dict[str, Any]] = {
        "current_price": {
            "failure_threshold": 5,
            "recovery_timeout_seconds": 60,
        },
        "price_history": {
            "failure_threshold": 5,
            "recovery_timeout_seconds": 60,
        },
        "options_chain": {
            "failure_threshold": 3,
            "recovery_timeout_seconds": 90,
        },
        "ticker_info": {
            "failure_threshold": 5,
            "recovery_timeout_seconds": 60,
        },
        "expirations": {
            "failure_threshold": 4,
            "recovery_timeout_seconds": 75,
        },
    }

    def __new__(cls) -> "CircuitBreakerRegistry":
        """Ensure only one instance of registry exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize registry with default circuit breakers."""
        if self._initialized:
            return

        self._breakers: dict[str, CircuitBreaker] = {}
        self._registry_lock: threading.Lock = threading.Lock()

        # Initialize default circuit breakers
        for endpoint_name, config in self._default_breakers.items():
            self.register(
                endpoint_name,
                CircuitBreaker(
                    name=endpoint_name,
                    failure_threshold=config["failure_threshold"],
                    recovery_timeout_seconds=config["recovery_timeout_seconds"],
                ),
            )

        self._initialized = True
        logger.info(
            f"CircuitBreakerRegistry initialized with {len(self._breakers)} breakers"
        )

    def register(self, name: str, breaker: CircuitBreaker) -> None:
        """
        Register a circuit breaker.

        Args:
            name: Identifier for the breaker
            breaker: CircuitBreaker instance to register

        Raises:
            ValueError: If breaker name is empty or already registered
        """
        if not name:
            raise ValueError("Breaker name cannot be empty")
        if not isinstance(breaker, CircuitBreaker):
            raise ValueError(f"Expected CircuitBreaker, got {type(breaker)}")

        with self._registry_lock:
            if name in self._breakers:
                logger.warning(f"Overwriting existing circuit breaker: {name}")
            self._breakers[name] = breaker
            logger.debug(f"Registered circuit breaker: {name}")

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """
        Get a circuit breaker by name.

        Args:
            name: Identifier of the breaker

        Returns:
            CircuitBreaker instance or None if not found
        """
        with self._registry_lock:
            return self._breakers.get(name)

    def get_all(self) -> dict[str, CircuitBreaker]:
        """
        Get all registered circuit breakers.

        Returns:
            Dictionary mapping names to CircuitBreaker instances
        """
        with self._registry_lock:
            return dict(self._breakers)

    def reset_all(self) -> None:
        """Reset all circuit breakers to CLOSED state."""
        with self._registry_lock:
            for breaker in self._breakers.values():
                breaker.reset()
            logger.info("Reset all circuit breakers to CLOSED state")

    def get_status_all(self) -> dict[str, dict[str, Any]]:
        """
        Get status of all circuit breakers.

        Returns:
            Dictionary mapping breaker names to their status dicts
        """
        with self._registry_lock:
            return {name: breaker.get_status() for name, breaker in self._breakers.items()}

    def get_open_breakers(self) -> list[str]:
        """
        Get names of all OPEN circuit breakers.

        Returns:
            List of names of OPEN breakers
        """
        with self._registry_lock:
            return [
                name for name, breaker in self._breakers.items() if breaker.is_open()
            ]

    def get_half_open_breakers(self) -> list[str]:
        """
        Get names of all HALF_OPEN circuit breakers.

        Returns:
            List of names of HALF_OPEN breakers
        """
        with self._registry_lock:
            return [
                name for name, breaker in self._breakers.items() if breaker.is_half_open()
            ]

    def get_closed_breakers(self) -> list[str]:
        """
        Get names of all CLOSED circuit breakers.

        Returns:
            List of names of CLOSED breakers (normal operation)
        """
        with self._registry_lock:
            return [
                name for name, breaker in self._breakers.items() if breaker.is_closed()
            ]
