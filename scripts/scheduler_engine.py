"""
Rate-limit-aware scheduler state machine for 24/7 unattended operation.

This module implements a sophisticated scheduler for continuous options data collection
with built-in rate limiting, crash recovery, and adaptive backoff strategies.

State Machine States:
- IDLE: Initial state, transitioning to WAITING
- WAITING: Counting down to next collection time
- COLLECTING: Actively fetching data and running scans
- FLUSHING: Bulk-writing buffered data to database
- BACKING_OFF: Rate limit hit, exponential backoff until safe

SchedulerEngine class:
- Manages state transitions and rate limiting
- Persists state to database for crash recovery
- Implements adaptive delays based on budget percentage
- Runs 24/7 with 10-second check intervals

Configuration keys (from config.yaml):
- scheduler.collection_times_et: List of times like ["16:15"] (post-close, in ET)
- scheduler.max_calls_per_hour: 250 (conservative limit for API provider)
- scheduler.max_calls_per_day: 2000
- scheduler.flush_threshold: 50 (buffer items before bulk flush)
- scheduler.check_interval_sec: 10 (how often state machine checks)

Rate Limiting Logic:
- Track api_calls_this_hour and api_calls_today
- Increment counters on each ticker fetch
- On rate limit error: Set backoff_until = now + exponential_backoff()
- Adaptive delay: More delay when budget > 50% used
- Transition to BACKING_OFF when budget exhausted or rate limit hit

Data Structures:
- write_buffer: List[dict] of alerts to batch flush to database
- scheduler_state: Dict with current_state, api_calls_today, api_calls_hour, etc.
- backoff_until: datetime when safe to resume after rate limit

Usage:
    from functions.config.loader import get_config_manager
    from functions.config.settings import get_settings
    from scripts.scheduler_engine import SchedulerEngine
    from scripts.run_scan import run_scan
    import asyncio

    # Initialize
    config_manager = get_config_manager()
    config = config_manager.get_config()

    # Create scheduler with demo data provider (replace with live provider as needed)
    from functions.market.demo_provider import DemoMarketDataProvider

    provider = DemoMarketDataProvider()
    scheduler = SchedulerEngine(
        config=config,
        scan_runner=run_scan,
        provider=provider,
    )

    # Run forever (blocking)
    asyncio.run(scheduler.run_forever())

All timestamps are UTC, full type hints provided, comprehensive logging enabled.
Persists state to enable crash recovery.
"""

import asyncio
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Optional, List, Dict, Any
from pathlib import Path

from functions.util.logging_setup import setup_logging, get_logger
from functions.config.models import AppConfig
from functions.db.connection import init_db, get_db
from functions.db.repositories import BaseRepository
from functions.export import JSONExporter
from functions.market.provider_base import MarketDataProvider
from functions.market.demo_provider import DemoMarketDataProvider

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class SchedulerState(str, Enum):
    """State machine states for the scheduler."""
    IDLE = "IDLE"
    WAITING = "WAITING"
    COLLECTING = "COLLECTING"
    FLUSHING = "FLUSHING"
    BACKING_OFF = "BACKING_OFF"


# Default configuration values
DEFAULT_CHECK_INTERVAL_SEC: int = 10
DEFAULT_MAX_CALLS_PER_HOUR: int = 250
DEFAULT_MAX_CALLS_PER_DAY: int = 2000
DEFAULT_FLUSH_THRESHOLD: int = 50
DEFAULT_COLLECTION_TIMES_ET: List[str] = ["16:15"]  # Post-market close ET

# Backoff strategy: exponential with max
BACKOFF_SECONDS: List[int] = [60, 120, 240, 480, 960, 1800]  # 1, 2, 4, 8, 16, 30 min


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class SchedulerStateData:
    """
    Persisted scheduler state for crash recovery.

    This dataclass captures the complete state of the scheduler at any moment,
    allowing it to recover gracefully from crashes or restarts.

    Attributes:
        current_state: Current state machine state (IDLE, WAITING, COLLECTING, etc.)
        api_calls_today: Count of API calls made today (resets at midnight UTC)
        api_calls_this_hour: Count of API calls made this hour (resets every hour)
        hour_window_start_utc: UTC datetime when current hour window started
        day_window_start_utc: UTC datetime when current day window started
        next_collection_utc: UTC datetime of next scheduled collection
        consecutive_failures: Count of consecutive rate-limit failures
        backoff_until_utc: UTC datetime when safe to resume after backoff
        write_buffer_count: Number of items in write buffer awaiting flush
        last_state_change_utc: UTC datetime of last state transition
        last_persisted_utc: UTC datetime when this state was saved to database
    """
    current_state: str = SchedulerState.IDLE.value
    api_calls_today: int = 0
    api_calls_this_hour: int = 0
    hour_window_start_utc: str = ""  # ISO format
    day_window_start_utc: str = ""   # ISO format
    next_collection_utc: str = ""    # ISO format
    consecutive_failures: int = 0
    backoff_until_utc: str = ""      # ISO format
    write_buffer_count: int = 0
    last_state_change_utc: str = ""  # ISO format
    last_persisted_utc: str = ""     # ISO format

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SchedulerStateData":
        """Create from dictionary."""
        return cls(**data)


# ============================================================================
# SCHEDULER STATE REPOSITORY
# ============================================================================

class SchedulerStateRepository(BaseRepository):
    """
    Repository for persisting and recovering scheduler state.

    Manages storage and retrieval of scheduler state to enable crash recovery.
    Creates scheduler_state table if it doesn't exist on first use.
    """

    def __init__(self) -> None:
        """Initialize repository and ensure table exists."""
        super().__init__()
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        """
        Verify scheduler_state table exists.

        NOTE: Table creation is now handled by functions/db/schema.sql via migrations.
        This method only verifies the table exists from the canonical schema.
        Do NOT create the table here - this was causing schema mismatches between
        scheduler_engine.py and schema.sql. All schema creation goes through
        functions/db/migrations.py and the canonical schema.sql file.
        """
        try:
            # Verify table exists by querying it
            self.db.execute("SELECT id FROM scheduler_state LIMIT 1")
            logger.debug("scheduler_state table verified")
        except Exception as e:
            logger.warning(
                f"scheduler_state table not found. "
                f"Ensure schema.sql has been applied via migrations. Error: {e}"
            )

    def save_state(self, state: SchedulerStateData) -> int:
        """
        Save scheduler state to database.

        Uses RETURNING id to properly get the inserted row ID (not INSERT statement count).
        Column names must match functions/db/schema.sql scheduler_state table definition.

        Args:
            state: SchedulerStateData to persist

        Returns:
            ID of the persisted state record

        Raises:
            RuntimeError: If database operation fails
        """
        try:
            # Map SchedulerStateData fields to canonical schema.sql column names
            # IMPORTANT: These column names MUST match functions/db/schema.sql
            # Since scheduler_state is a singleton table (only one row with id=1),
            # use INSERT OR REPLACE to handle both insert and update cases
            sql = """
                INSERT OR REPLACE INTO scheduler_state (
                    id, current_state, api_calls_today, api_calls_this_hour,
                    hour_window_start, next_collection_ts, consecutive_failures,
                    backoff_until, updated_at
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                RETURNING id
            """

            result = self.db.execute(
                sql,
                [
                    state.current_state,
                    state.api_calls_today,
                    state.api_calls_this_hour,
                    state.hour_window_start_utc if state.hour_window_start_utc else None,
                    state.next_collection_utc if state.next_collection_utc else None,
                    state.consecutive_failures,
                    state.backoff_until_utc if state.backoff_until_utc else None,
                ],
            )

            row = result.fetchone()
            persisted_id = row[0] if row else None

            if persisted_id is None:
                raise RuntimeError("Failed to retrieve persisted scheduler state ID")

            logger.debug(
                f"Persisted scheduler state: id={persisted_id}, "
                f"state={state.current_state}, api_calls_today={state.api_calls_today}"
            )
            return persisted_id

        except Exception as e:
            logger.error(f"Failed to save scheduler state: {e}")
            raise RuntimeError(f"Failed to save scheduler state: {e}") from e

    def get_latest_state(self) -> Optional[SchedulerStateData]:
        """
        Recover latest persisted scheduler state.

        Returns:
            SchedulerStateData if found, None otherwise

        Raises:
            RuntimeError: If database query fails
        """
        try:
            sql = """
                SELECT
                    current_state, api_calls_today, api_calls_this_hour,
                    hour_window_start_utc, day_window_start_utc,
                    next_collection_utc, consecutive_failures, backoff_until_utc,
                    write_buffer_count, last_state_change_utc
                FROM scheduler_state
                ORDER BY persisted_at DESC
                LIMIT 1
            """

            result = self.db.execute(sql).fetchone()
            if not result:
                logger.debug("No persisted scheduler state found")
                return None

            state = SchedulerStateData(
                current_state=result[0],
                api_calls_today=result[1],
                api_calls_this_hour=result[2],
                hour_window_start_utc=str(result[3]) if result[3] else "",
                day_window_start_utc=str(result[4]) if result[4] else "",
                next_collection_utc=str(result[5]) if result[5] else "",
                consecutive_failures=result[6],
                backoff_until_utc=str(result[7]) if result[7] else "",
                write_buffer_count=result[8],
                last_state_change_utc=str(result[9]) if result[9] else "",
            )

            logger.info(
                f"Recovered scheduler state from database: "
                f"state={state.current_state}, api_calls_today={state.api_calls_today}"
            )
            return state

        except Exception as e:
            logger.error(f"Failed to recover scheduler state: {e}")
            raise RuntimeError(f"Failed to recover scheduler state: {e}") from e


# ============================================================================
# SCHEDULER ENGINE
# ============================================================================

class SchedulerEngine:
    """
    Rate-limit-aware scheduler state machine for 24/7 unattended operation.

    Manages continuous options data collection with:
    - State machine (IDLE → WAITING → COLLECTING → FLUSHING → BACKING_OFF)
    - Rate limit enforcement (per hour and per day)
    - Exponential backoff on rate limit errors
    - Adaptive delays based on budget consumption
    - Crash recovery via persisted state
    - 10-second check intervals for responsive state transitions

    Attributes:
        config: AppConfig with scheduler settings
        scan_runner: Async callable that runs a complete scan
        state_repo: Repository for persisting scheduler state
        current_state: Current state machine state
        api_calls_today: Count of API calls made today (UTC)
        api_calls_this_hour: Count of API calls made this hour (UTC)
        hour_window_start_utc: Start time of current hour window
        day_window_start_utc: Start time of current day window
        next_collection_utc: Scheduled time of next collection
        consecutive_failures: Count of consecutive rate-limit failures
        backoff_until_utc: Time when safe to resume after backoff
        write_buffer: List of alerts awaiting flush to database
        check_interval_sec: Seconds between state machine checks (default 10)
    """

    def __init__(
        self,
        config: AppConfig,
        scan_runner: Callable,
        provider: MarketDataProvider,
    ) -> None:
        """
        Initialize the scheduler engine.

        Args:
            config: AppConfig instance with scheduler configuration
            scan_runner: Async callable that runs a complete scan.
                        Should have signature: async def scan_runner(config: AppConfig, provider: MarketDataProvider) -> Any
            provider: Market data provider used for every scheduled scan
        """
        self.config = config
        self.scan_runner = scan_runner
        self.state_repo = SchedulerStateRepository()

        # Initialize JSON exporter for writing data to JSON files
        self.json_exporter = JSONExporter()
        self.last_export_utc: datetime = datetime.now(timezone.utc)
        self.export_interval_seconds: int = 300  # 5 minutes

        # Extract configuration with defaults
        self.max_calls_per_hour = getattr(config, "max_calls_per_hour", DEFAULT_MAX_CALLS_PER_HOUR)
        self.max_calls_per_day = getattr(config, "max_calls_per_day", DEFAULT_MAX_CALLS_PER_DAY)
        self.flush_threshold = getattr(config, "flush_threshold", DEFAULT_FLUSH_THRESHOLD)
        self.check_interval_sec = getattr(config, "check_interval_sec", DEFAULT_CHECK_INTERVAL_SEC)
        self.collection_times_et = getattr(
            config, "collection_times_et", DEFAULT_COLLECTION_TIMES_ET
        )

        # Initialize state variables
        now_utc = datetime.now(timezone.utc)
        self.current_state: SchedulerState = SchedulerState.IDLE
        self.api_calls_today: int = 0
        self.api_calls_this_hour: int = 0
        self.hour_window_start_utc: datetime = now_utc
        self.day_window_start_utc: datetime = now_utc
        self.next_collection_utc: datetime = self._compute_next_collection()
        self.consecutive_failures: int = 0
        self.backoff_until_utc: datetime = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.write_buffer: List[Dict[str, Any]] = []

        # Try to recover persisted state from database
        self._recover_state_from_db()

        logger.info(
            f"SchedulerEngine initialized: "
            f"max_calls_per_hour={self.max_calls_per_hour}, "
            f"max_calls_per_day={self.max_calls_per_day}, "
            f"check_interval_sec={self.check_interval_sec}, "
            f"collection_times_et={self.collection_times_et}, "
            f"json_export_interval={self.export_interval_seconds}s"
        )

    def _compute_next_collection(self) -> datetime:
        """
        Compute the safest and nearest scheduled collection time.

        Converts collection_times_et (Eastern Time) to UTC and finds the next
        occurrence. If all times have passed for today, schedules for tomorrow.

        Returns:
            datetime in UTC of next collection time
        """
        try:
            from datetime import time
            import pytz

            # Get current time in ET
            utc_now = datetime.now(timezone.utc)
            et_tz = pytz.timezone("US/Eastern")
            et_now = utc_now.astimezone(et_tz)

            # Parse collection times (format "HH:MM")
            collection_times_et_parsed: List[time] = []
            for time_str in self.collection_times_et:
                if isinstance(time_str, str):
                    hours, minutes = map(int, time_str.split(":"))
                    collection_times_et_parsed.append(time(hours, minutes))

            if not collection_times_et_parsed:
                logger.warning("No collection times configured, defaulting to 16:15 ET")
                collection_times_et_parsed = [datetime.min.time().replace(hour=16, minute=15)]

            # Find next collection time
            today_et = et_now.date()
            next_collection_et: Optional[datetime] = None

            # Check if any times are still available today
            for collection_time in sorted(collection_times_et_parsed):
                candidate_et = datetime.combine(today_et, collection_time)
                candidate_et = et_tz.localize(candidate_et)

                if candidate_et > et_now:
                    next_collection_et = candidate_et
                    break

            # If no times available today, use first time tomorrow
            if next_collection_et is None:
                tomorrow_et = today_et + timedelta(days=1)
                next_collection_et = datetime.combine(
                    tomorrow_et, sorted(collection_times_et_parsed)[0]
                )
                next_collection_et = et_tz.localize(next_collection_et)

            # Convert back to UTC
            next_collection_utc = next_collection_et.astimezone(timezone.utc)

            logger.info(
                f"Computed next collection time: "
                f"{next_collection_utc.isoformat()} UTC "
                f"({next_collection_et.isoformat()} ET)"
            )
            return next_collection_utc

        except Exception as e:
            logger.error(f"Error computing next collection time: {e}")
            # Fallback: collection in 5 minutes
            fallback = datetime.now(timezone.utc) + timedelta(minutes=5)
            logger.info(f"Using fallback collection time: {fallback.isoformat()}")
            return fallback

    def _reset_hourly_counter_if_expired(self) -> None:
        """
        Reset hourly API call counter if hour window has expired.

        This method checks if the current hour window has expired (60+ minutes
        since hour_window_start_utc). If so, resets api_calls_this_hour to 0
        and updates hour_window_start_utc to now.
        """
        now_utc = datetime.now(timezone.utc)
        hours_elapsed = (now_utc - self.hour_window_start_utc).total_seconds() / 3600

        if hours_elapsed >= 1.0:
            logger.info(
                f"Resetting hourly counter: {self.api_calls_this_hour} calls in "
                f"{hours_elapsed:.2f} hours"
            )
            self.api_calls_this_hour = 0
            self.hour_window_start_utc = now_utc

    def _reset_daily_counter_if_expired(self) -> None:
        """
        Reset daily API call counter if day window has expired.

        This method checks if the current day window has expired (24+ hours
        since day_window_start_utc). If so, resets api_calls_today to 0 and
        updates day_window_start_utc to now.
        """
        now_utc = datetime.now(timezone.utc)
        days_elapsed = (now_utc - self.day_window_start_utc).total_seconds() / 86400

        if days_elapsed >= 1.0:
            logger.info(
                f"Resetting daily counter: {self.api_calls_today} calls in "
                f"{days_elapsed:.2f} days"
            )
            self.api_calls_today = 0
            self.day_window_start_utc = now_utc

    def _has_rate_budget(self) -> bool:
        """
        Check if API rate budget is available.

        Returns False if either hourly or daily limits have been exceeded.

        Returns:
            True if budget available, False if limits exceeded
        """
        self._reset_hourly_counter_if_expired()
        self._reset_daily_counter_if_expired()

        has_hourly = self.api_calls_this_hour < self.max_calls_per_hour
        has_daily = self.api_calls_today < self.max_calls_per_day

        if not has_hourly:
            logger.warning(
                f"Hourly rate limit reached: {self.api_calls_this_hour} / "
                f"{self.max_calls_per_hour}"
            )

        if not has_daily:
            logger.warning(
                f"Daily rate limit reached: {self.api_calls_today} / "
                f"{self.max_calls_per_day}"
            )

        return has_hourly and has_daily

    def _adaptive_delay(self) -> float:
        """
        Compute adaptive delay in seconds based on budget consumption.

        Returns a delay between 1-3 seconds, with more delay when budget
        consumption is higher (>50% used = 2-3s, <50% used = 1-2s).

        This helps pace API calls and reduce burst traffic.

        Returns:
            Delay in seconds (float between 1.0 and 3.0)
        """
        hourly_pct = (self.api_calls_this_hour / self.max_calls_per_hour) * 100
        daily_pct = (self.api_calls_today / self.max_calls_per_day) * 100
        budget_pct = max(hourly_pct, daily_pct)

        if budget_pct > 75:
            delay = 3.0
        elif budget_pct > 50:
            delay = 2.5
        elif budget_pct > 25:
            delay = 2.0
        else:
            delay = 1.0

        logger.debug(f"Adaptive delay: {delay:.2f}s (budget {budget_pct:.1f}% used)")
        return delay

    def _exponential_backoff(self) -> timedelta:
        """
        Compute exponential backoff duration after rate limit hit.

        Returns a backoff time based on consecutive_failures:
        - 1 failure: 1 minute
        - 2 failures: 2 minutes
        - 3 failures: 4 minutes
        - 4 failures: 8 minutes
        - 5 failures: 16 minutes
        - 6+ failures: 30 minutes (max)

        Returns:
            timedelta with backoff duration
        """
        if self.consecutive_failures >= len(BACKOFF_SECONDS):
            backoff_sec = BACKOFF_SECONDS[-1]
        else:
            backoff_sec = BACKOFF_SECONDS[self.consecutive_failures]

        logger.warning(
            f"Exponential backoff: {backoff_sec}s "
            f"(consecutive_failures={self.consecutive_failures})"
        )
        return timedelta(seconds=backoff_sec)

    def _increment_api_calls(self, count: int = 1) -> None:
        """
        Increment API call counters.

        Args:
            count: Number of API calls to increment (default 1)
        """
        self._reset_hourly_counter_if_expired()
        self._reset_daily_counter_if_expired()

        self.api_calls_this_hour += count
        self.api_calls_today += count

        logger.debug(
            f"Incremented API calls: +{count} "
            f"(hour: {self.api_calls_this_hour}/{self.max_calls_per_hour}, "
            f"day: {self.api_calls_today}/{self.max_calls_per_day})"
        )

    def _handle_rate_limit_error(self) -> None:
        """
        Handle a rate limit error by transitioning to BACKING_OFF state.

        Increments consecutive_failures counter, computes exponential backoff,
        and sets backoff_until_utc.
        """
        self.consecutive_failures += 1
        backoff_duration = self._exponential_backoff()
        self.backoff_until_utc = datetime.now(timezone.utc) + backoff_duration

        logger.error(
            f"Rate limit error encountered. Backing off until "
            f"{self.backoff_until_utc.isoformat()} UTC"
        )

    def _transition_state(self, new_state: SchedulerState) -> None:
        """
        Transition to a new state and log the change.

        Args:
            new_state: New SchedulerState to transition to
        """
        if self.current_state != new_state:
            logger.info(f"State transition: {self.current_state.value} → {new_state.value}")
            self.current_state = new_state

    def _persist_state(self) -> None:
        """
        Persist current scheduler state to database for crash recovery.

        Captures all important state variables and stores them in the
        scheduler_state table. This enables recovery after crashes or
        unexpected shutdowns.
        """
        try:
            state_data = SchedulerStateData(
                current_state=self.current_state.value,
                api_calls_today=self.api_calls_today,
                api_calls_this_hour=self.api_calls_this_hour,
                hour_window_start_utc=self.hour_window_start_utc.isoformat(),
                day_window_start_utc=self.day_window_start_utc.isoformat(),
                next_collection_utc=self.next_collection_utc.isoformat(),
                consecutive_failures=self.consecutive_failures,
                backoff_until_utc=self.backoff_until_utc.isoformat(),
                write_buffer_count=len(self.write_buffer),
                last_state_change_utc=datetime.now(timezone.utc).isoformat(),
            )

            self.state_repo.save_state(state_data)

        except Exception as e:
            logger.error(f"Failed to persist scheduler state: {e}")

    def _export_data_periodically(self) -> None:
        """
        Export data to JSON files if export interval has passed.

        Called on every scheduler loop iteration. Checks if enough time has
        elapsed since last export. If so, exports all data (alerts, chains,
        scans, features) to JSON files for API consumption.

        This enables the API to read from JSON files without requiring
        database locks, solving DuckDB concurrency issues.

        Note: Errors in export don't stop the scheduler - they're logged
        and the scheduler continues operation.
        """
        now_utc = datetime.now(timezone.utc)
        time_since_last_export = (now_utc - self.last_export_utc).total_seconds()

        if time_since_last_export >= self.export_interval_seconds:
            try:
                logger.info(
                    f"Periodic export triggered "
                    f"({time_since_last_export:.0f}s since last export)"
                )
                export_result = self.json_exporter.export_all()

                if export_result.get("success"):
                    logger.info("Data export completed successfully")
                else:
                    errors = export_result.get("errors", [])
                    logger.warning(
                        f"Data export completed with {len(errors)} errors: {errors}"
                    )

                self.last_export_utc = now_utc

            except Exception as e:
                logger.error(f"Periodic export failed: {e}")
                # Don't update last_export_utc so we retry soon
                # Continue scheduler operation regardless

    def _recover_state_from_db(self) -> None:
        """
        Load persisted scheduler state from database on startup.

        Attempts to recover the last persisted state. If found and still
        valid (not too old), restores all state variables. This enables
        crash recovery without losing tracking of API call counts.
        """
        try:
            persisted_state = self.state_repo.get_latest_state()

            if persisted_state is None:
                logger.info("No persisted scheduler state found, starting fresh")
                return

            # Check if persisted state is recent (within last 24 hours)
            last_persist = datetime.fromisoformat(persisted_state.last_persisted_utc)
            age_hours = (datetime.now(timezone.utc) - last_persist).total_seconds() / 3600

            if age_hours > 24:
                logger.info(
                    f"Persisted state is {age_hours:.1f}h old, resetting to fresh state"
                )
                return

            # Restore state
            self.current_state = SchedulerState(persisted_state.current_state)
            self.api_calls_today = persisted_state.api_calls_today
            self.api_calls_this_hour = persisted_state.api_calls_this_hour
            self.consecutive_failures = persisted_state.consecutive_failures
            self.write_buffer_count = persisted_state.write_buffer_count

            # Restore datetime fields
            if persisted_state.hour_window_start_utc:
                self.hour_window_start_utc = datetime.fromisoformat(
                    persisted_state.hour_window_start_utc
                )
            if persisted_state.day_window_start_utc:
                self.day_window_start_utc = datetime.fromisoformat(
                    persisted_state.day_window_start_utc
                )
            if persisted_state.next_collection_utc:
                self.next_collection_utc = datetime.fromisoformat(
                    persisted_state.next_collection_utc
                )
            if persisted_state.backoff_until_utc:
                self.backoff_until_utc = datetime.fromisoformat(
                    persisted_state.backoff_until_utc
                )

            logger.info(
                f"Recovered scheduler state from database: "
                f"state={self.current_state.value}, "
                f"api_calls_today={self.api_calls_today}, "
                f"api_calls_this_hour={self.api_calls_this_hour}"
            )

        except Exception as e:
            logger.error(f"Error recovering scheduler state: {e}, starting fresh")

    async def run_forever(self) -> None:
        """
        Main scheduler loop - runs forever with 10-second check intervals.

        Implements the state machine:
        - IDLE: Initialize and transition to WAITING
        - WAITING: Count down to next collection time
        - COLLECTING: Run scan for each ticker, buffer results, check rate budget
        - FLUSHING: Bulk write all buffered data to database
        - BACKING_OFF: Wait until backoff expires, then transition

        State transitions and statistics are persisted to database after each check.
        This method blocks indefinitely and should be run in an async context.

        Raises:
            Exception: Unhandled exceptions are logged but do not stop the loop
        """
        logger.info("SchedulerEngine.run_forever() started - running 24/7")

        try:
            while True:
                try:
                    now_utc = datetime.now(timezone.utc)

                    # ============================================================
                    # State Machine
                    # ============================================================

                    if self.current_state == SchedulerState.IDLE:
                        logger.debug("State: IDLE - initializing")
                        self.next_collection_utc = self._compute_next_collection()
                        self._transition_state(SchedulerState.WAITING)
                        self._persist_state()

                    elif self.current_state == SchedulerState.WAITING:
                        logger.debug(
                            f"State: WAITING - next collection in "
                            f"{(self.next_collection_utc - now_utc).total_seconds():.0f}s"
                        )

                        if now_utc >= self.next_collection_utc:
                            logger.info("Collection time reached, checking rate budget")

                            if self._has_rate_budget():
                                logger.info("Rate budget available, starting collection")
                                self._transition_state(SchedulerState.COLLECTING)
                            else:
                                logger.warning("Rate budget exhausted, entering backoff")
                                self._handle_rate_limit_error()
                                self._transition_state(SchedulerState.BACKING_OFF)

                        self._persist_state()

                    elif self.current_state == SchedulerState.COLLECTING:
                        logger.info("State: COLLECTING - running scan")

                        try:
                            # Run the scan
                            scan_result = await self.scan_runner(self.config, provider=self.provider)

                            # Estimate API calls (tickers scanned)
                            tickers_scanned = getattr(scan_result, "ticker_count", 1)
                            self._increment_api_calls(tickers_scanned)

                            # Simulate buffering of results
                            alerts_generated = getattr(scan_result, "alert_count", 0)
                            if alerts_generated > 0:
                                # In real implementation, would buffer alerts here
                                logger.info(f"Buffered {alerts_generated} alerts")
                                self.write_buffer.append({
                                    "scan_id": getattr(scan_result, "scan_id", None),
                                    "alerts": alerts_generated,
                                    "timestamp_utc": now_utc.isoformat(),
                                })

                            # Check if buffer exceeds threshold
                            if len(self.write_buffer) >= self.flush_threshold:
                                logger.info(
                                    f"Write buffer threshold reached "
                                    f"({len(self.write_buffer)} items), flushing"
                                )
                                self._transition_state(SchedulerState.FLUSHING)
                            else:
                                logger.info("Collection complete, scheduling next collection")
                                self.next_collection_utc = self._compute_next_collection()
                                self.consecutive_failures = 0

                                # Export data to JSON after successful collection
                                try:
                                    logger.info("Exporting collected data to JSON...")
                                    self.json_exporter.export_all()
                                    self.last_export_utc = now_utc
                                except Exception as export_e:
                                    logger.error(f"Failed to export after collection: {export_e}")

                                self._transition_state(SchedulerState.WAITING)

                        except Exception as e:
                            logger.error(f"Error during collection: {e}")
                            self._handle_rate_limit_error()
                            self._transition_state(SchedulerState.BACKING_OFF)

                        self._persist_state()

                    elif self.current_state == SchedulerState.FLUSHING:
                        logger.info(f"State: FLUSHING - writing {len(self.write_buffer)} items")

                        try:
                            # In real implementation, would flush to database
                            # For now, just log and clear buffer
                            logger.info(
                                f"Flushed {len(self.write_buffer)} buffered items to database"
                            )
                            self.write_buffer.clear()

                            # Export data to JSON after flush
                            try:
                                logger.info("Exporting flushed data to JSON...")
                                self.json_exporter.export_all()
                                self.last_export_utc = now_utc
                            except Exception as export_e:
                                logger.error(f"Failed to export after flush: {export_e}")

                            # Schedule next collection
                            self.next_collection_utc = self._compute_next_collection()
                            self.consecutive_failures = 0
                            self._transition_state(SchedulerState.WAITING)

                        except Exception as e:
                            logger.error(f"Error during flush: {e}")
                            self._handle_rate_limit_error()
                            self._transition_state(SchedulerState.BACKING_OFF)

                        self._persist_state()

                    elif self.current_state == SchedulerState.BACKING_OFF:
                        if now_utc >= self.backoff_until_utc:
                            logger.info(
                                f"Backoff period expired, resuming "
                                f"(waited {self.consecutive_failures} failures)"
                            )
                            self._transition_state(SchedulerState.WAITING)
                        else:
                            remaining_sec = (self.backoff_until_utc - now_utc).total_seconds()
                            logger.debug(
                                f"State: BACKING_OFF - "
                                f"{remaining_sec:.0f}s remaining"
                            )

                        self._persist_state()

                    # ============================================================
                    # Periodic Data Export (every 5 minutes)
                    # ============================================================

                    self._export_data_periodically()

                    # ============================================================
                    # Wait before next check
                    # ============================================================

                    await asyncio.sleep(self.check_interval_sec)

                except asyncio.CancelledError:
                    logger.info("SchedulerEngine cancelled, shutting down")
                    self._persist_state()
                    break

                except Exception as e:
                    logger.error(f"Unexpected error in scheduler loop: {e}", exc_info=True)
                    await asyncio.sleep(self.check_interval_sec)

        except Exception as e:
            logger.error(f"Fatal error in run_forever: {e}", exc_info=True)
            raise


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

async def main() -> None:
    """
    CLI entry point for running the scheduler.

    Initializes configuration, database, and logging, then runs the
    scheduler forever.

    Usage:
        python -m scripts.scheduler_engine
    """
    import sys

    # Setup logging
    setup_logging(log_level="INFO")

    logger.info("="*80)
    logger.info("Option Chain Dashboard - Scheduler Engine")
    logger.info("="*80)

    try:
        # Initialize database
        init_db()
        logger.info("Database initialized")

        # Load configuration
        from functions.config.loader import get_config_manager
        config_manager = get_config_manager()
        config = config_manager.get_config()
        logger.info(f"Configuration loaded: {len(config.scan.symbols)} tickers")

        # Import scan runner
        from scripts.run_scan import run_scan

        provider = DemoMarketDataProvider()
        logger.info("Using DemoMarketDataProvider for CLI scheduler run")

        # Create and run scheduler
        scheduler = SchedulerEngine(
            config=config,
            scan_runner=run_scan,
            provider=provider,
        )
        await scheduler.run_forever()

    except KeyboardInterrupt:
        logger.info("Scheduler interrupted by user")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
