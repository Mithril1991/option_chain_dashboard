"""
Alert throttling module for cooldown tracking and daily rate limiting.

This module provides the AlertThrottler class that manages:
- Per-ticker cooldown periods (default 24 hours) to prevent alert spam
- Daily alert rate limiting (default 5 alerts per day per ticker)
- Intelligent throttling decisions based on both conditions

Throttler prevents duplicate alerts for the same ticker within a cooldown window
and enforces maximum alerts per day limits to prevent overwhelming users.

Usage:
    from functions.config.loader import get_config
    from functions.db.connection import init_db
    from functions.scoring.throttler import AlertThrottler

    # Initialize DB at startup
    init_db()

    # Create throttler with config
    config = get_config()
    throttler = AlertThrottler(db_connection=get_db(), config=config)

    # Check if alert should be sent
    ticker = "AAPL"
    detector = "volume_spike"
    score = 75.5

    if throttler.should_alert(ticker, detector, score):
        # Send alert
        alert_id = send_alert(...)
        # Record that alert was sent
        throttler.record_alert(ticker, detector, score, alert_id)
    else:
        print(f"Alert throttled for {ticker}")

    # Check remaining cooldown
    remaining = throttler.get_cooldown_remaining(ticker)
    if remaining:
        print(f"Cooldown remaining: {remaining}")

Configuration Requirements (in AppConfig):
    - "scoring.cooldown_hours" (default 24): Cooldown period in hours per ticker
    - "scoring.max_alerts_per_day" (default 5): Maximum alerts per day per ticker

Database Tables Required:
    - alert_cooldowns: Tracks last alert time and score per ticker
    - daily_alert_counts: Tracks alert count per day per ticker

All timestamps are UTC. Missing data is handled gracefully (assumes no prior cooldown).
"""

from datetime import datetime, timedelta, date
from typing import Optional
from pathlib import Path

from functions.util.logging_setup import get_logger
from functions.util.time_utils import get_utc_now
from functions.config.models import AppConfig
from functions.db.connection import DuckDBManager
from functions.db.repositories import CooldownRepository, AlertRepository

logger = get_logger(__name__)


class AlertThrottler:
    """
    Manages alert throttling with cooldown tracking and daily rate limiting.

    This class enforces two throttling conditions:
    1. **Cooldown Check**: Prevents alerts for the same ticker within cooldown_duration
    2. **Daily Limit Check**: Prevents exceeding max_alerts_per_day

    Both conditions must pass for an alert to be sent. If either is violated,
    the alert is throttled and a reason is logged.

    Attributes:
        db (DuckDBManager): Database connection manager
        config (AppConfig): Application configuration with thresholds
        cooldown_hours (int): Cooldown period in hours (from config)
        max_alerts_per_day (int): Maximum alerts per day (from config)
        cooldown_repo (CooldownRepository): Repository for cooldown tracking
        alert_repo (AlertRepository): Repository for alert data
    """

    def __init__(self, db_connection: DuckDBManager, config: AppConfig) -> None:
        """
        Initialize AlertThrottler with database connection and configuration.

        Args:
            db_connection (DuckDBManager): Thread-safe database connection manager
            config (AppConfig): Application configuration containing:
                - "scoring.cooldown_hours" (default 24)
                - "scoring.max_alerts_per_day" (default 5)

        Raises:
            TypeError: If db_connection is not a DuckDBManager or config is not AppConfig
            ValueError: If configuration values are invalid

        Example:
            >>> from functions.db.connection import init_db, get_db
            >>> from functions.config.loader import get_config
            >>> init_db()
            >>> throttler = AlertThrottler(get_db(), get_config())
        """
        if not isinstance(db_connection, DuckDBManager):
            raise TypeError(
                f"db_connection must be DuckDBManager, got {type(db_connection).__name__}"
            )
        if not isinstance(config, AppConfig):
            raise TypeError(
                f"config must be AppConfig, got {type(config).__name__}"
            )

        self.db = db_connection
        self.config = config

        # Get throttling thresholds from config
        # Use getattr with defaults for robustness
        self.cooldown_hours = int(
            getattr(getattr(config, "scoring", {}), "cooldown_hours", 24)
            or 24
        )
        self.max_alerts_per_day = int(
            getattr(getattr(config, "scoring", {}), "max_alerts_per_day", 5)
            or 5
        )

        # Validate thresholds
        if self.cooldown_hours <= 0:
            raise ValueError(f"cooldown_hours must be positive, got {self.cooldown_hours}")
        if self.max_alerts_per_day <= 0:
            raise ValueError(
                f"max_alerts_per_day must be positive, got {self.max_alerts_per_day}"
            )

        # Initialize repositories
        self.cooldown_repo = CooldownRepository()
        self.alert_repo = AlertRepository()

        logger.info(
            f"Initialized AlertThrottler: cooldown_hours={self.cooldown_hours}, "
            f"max_alerts_per_day={self.max_alerts_per_day}"
        )

    def should_alert(self, ticker: str, detector_name: str, current_score: float) -> bool:
        """
        Determine if an alert should be sent based on throttling conditions.

        Checks two conditions:
        a) **Cooldown Check**: Was the last alert < cooldown_duration ago?
           - If yes, alert is throttled (return False)
        b) **Daily Limit Check**: Have we sent max_alerts_per_day already?
           - If yes, alert is throttled (return False)

        Returns True only if BOTH checks pass (not in cooldown AND under daily limit).
        Logs throttle reason at DEBUG level if alert is blocked.

        Args:
            ticker (str): Stock ticker symbol (e.g., "AAPL")
            detector_name (str): Name of detector generating alert
            current_score (float): Current alert score (0-100)

        Returns:
            bool: True if alert should be sent, False if throttled

        Raises:
            ValueError: If inputs are invalid

        Example:
            >>> throttler = AlertThrottler(db, config)
            >>> if throttler.should_alert("AAPL", "volume_spike", 75.5):
            ...     send_alert()
            ... else:
            ...     print("Alert throttled")
        """
        if not ticker or not isinstance(ticker, str):
            raise ValueError(f"ticker must be non-empty string, got {ticker}")
        if not detector_name or not isinstance(detector_name, str):
            raise ValueError(
                f"detector_name must be non-empty string, got {detector_name}"
            )
        if not isinstance(current_score, (int, float)):
            raise ValueError(
                f"current_score must be numeric, got {type(current_score).__name__}"
            )

        ticker = ticker.upper()

        logger.debug(
            f"Checking throttle status: ticker={ticker}, detector={detector_name}, score={current_score:.1f}"
        )

        try:
            # Check 1: Cooldown status
            is_on_cooldown, hours_remaining = self.cooldown_repo.is_in_cooldown(
                ticker=ticker,
                cooldown_hours=self.cooldown_hours
            )

            if is_on_cooldown:
                logger.debug(
                    f"Alert throttled for {ticker}: in cooldown ({hours_remaining:.1f} hours remaining)"
                )
                return False

            # Check 2: Daily alert limit
            daily_count = self.get_daily_count()

            if daily_count >= self.max_alerts_per_day:
                logger.debug(
                    f"Alert throttled for {ticker}: daily limit reached ({daily_count}/{self.max_alerts_per_day})"
                )
                return False

            # Both checks passed
            logger.debug(
                f"Alert ALLOWED for {ticker}: not in cooldown, "
                f"daily count {daily_count}/{self.max_alerts_per_day}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error checking throttle status for {ticker}: {e}", exc_info=True
            )
            # Conservative: fail open (allow alert) if error occurs
            return True

    def record_alert(
        self, ticker: str, detector_name: str, score: float, alert_id: int
    ) -> bool:
        """
        Record that an alert was sent for tracking and throttling.

        Updates two database records:
        1. **alert_cooldowns**: Sets last_alert_ts=now_utc and last_score=score
        2. **daily_alert_counts**: Increments alert count for today

        Logs successful recording at INFO level. Returns False on database error.

        Args:
            ticker (str): Stock ticker symbol (e.g., "AAPL")
            detector_name (str): Name of detector that generated alert
            score (float): Alert score that was sent (0-100)
            alert_id (int): Database ID of the generated alert

        Returns:
            bool: True on success, False if database error occurs

        Raises:
            ValueError: If inputs are invalid

        Example:
            >>> throttler = AlertThrottler(db, config)
            >>> success = throttler.record_alert("AAPL", "volume_spike", 75.5, 42)
            >>> if success:
            ...     print("Alert recorded for throttling")
            ... else:
            ...     print("Failed to record alert")
        """
        if not ticker or not isinstance(ticker, str):
            raise ValueError(f"ticker must be non-empty string, got {ticker}")
        if not detector_name or not isinstance(detector_name, str):
            raise ValueError(
                f"detector_name must be non-empty string, got {detector_name}"
            )
        if not isinstance(score, (int, float)):
            raise ValueError(
                f"score must be numeric, got {type(score).__name__}"
            )
        if not isinstance(alert_id, int) or alert_id <= 0:
            raise ValueError(
                f"alert_id must be positive integer, got {alert_id}"
            )

        ticker = ticker.upper()

        logger.debug(
            f"Recording alert: ticker={ticker}, detector={detector_name}, "
            f"score={score:.1f}, alert_id={alert_id}"
        )

        try:
            # Update cooldown record
            self.cooldown_repo.update_cooldown(ticker=ticker, score=score)
            logger.debug(f"Updated cooldown record for {ticker}")

            # Increment daily alert count
            self.alert_repo.increment_daily_count()
            logger.debug(f"Incremented daily alert count")

            logger.info(
                f"Alert recorded: ticker={ticker}, detector={detector_name}, "
                f"score={score:.1f}, alert_id={alert_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to record alert for {ticker}: {e}", exc_info=True
            )
            return False

    def get_cooldown_remaining(self, ticker: str) -> Optional[timedelta]:
        """
        Get time remaining on cooldown period for a ticker.

        Retrieves the last alert timestamp from database and calculates:
        remaining = cooldown_duration - (now - last_alert)

        Returns timedelta if > 0 (still in cooldown), else None (no cooldown active).
        Handles missing data gracefully (returns None if no prior alert).

        Args:
            ticker (str): Stock ticker symbol (e.g., "AAPL")

        Returns:
            timedelta: Time remaining in cooldown, or None if expired/no prior alert

        Example:
            >>> throttler = AlertThrottler(db, config)
            >>> remaining = throttler.get_cooldown_remaining("AAPL")
            >>> if remaining:
            ...     print(f"Cooldown expires in {remaining}")
            ... else:
            ...     print("No active cooldown")
        """
        if not ticker or not isinstance(ticker, str):
            raise ValueError(f"ticker must be non-empty string, got {ticker}")

        ticker = ticker.upper()

        try:
            cooldown = self.cooldown_repo.get_cooldown(ticker)

            if not cooldown or cooldown.get("last_alert_ts") is None:
                logger.debug(f"No cooldown record found for {ticker}")
                return None

            last_alert_ts = cooldown["last_alert_ts"]

            # Handle both datetime and string timestamps
            if isinstance(last_alert_ts, str):
                # Parse ISO format timestamp
                from datetime import datetime as dt_module
                last_alert_dt = dt_module.fromisoformat(last_alert_ts.replace("Z", "+00:00"))
            else:
                last_alert_dt = last_alert_ts

            # Calculate elapsed time
            now_utc = get_utc_now()
            elapsed = now_utc - last_alert_dt
            cooldown_duration = timedelta(hours=self.cooldown_hours)

            remaining = cooldown_duration - elapsed

            if remaining > timedelta(0):
                logger.debug(
                    f"Cooldown remaining for {ticker}: {remaining} "
                    f"(expires at {(now_utc + remaining).isoformat()})"
                )
                return remaining
            else:
                logger.debug(f"Cooldown expired for {ticker}")
                return None

        except Exception as e:
            logger.error(
                f"Error calculating cooldown remaining for {ticker}: {e}",
                exc_info=True
            )
            return None

    def get_daily_count(self, target_date: Optional[date] = None) -> int:
        """
        Get alert count for a specific date.

        Queries daily_alert_counts table for the given date (defaults to today).
        Returns the count, or 0 if no record exists for that date.

        Args:
            target_date (date, optional): Date to query. Defaults to today's date in UTC.

        Returns:
            int: Number of alerts sent on that date (0 if no record)

        Example:
            >>> throttler = AlertThrottler(db, config)
            >>> today_count = throttler.get_daily_count()
            >>> print(f"Alerts today: {today_count}")
            Alerts today: 3
        """
        if target_date is not None and not isinstance(target_date, date):
            raise ValueError(
                f"target_date must be date object, got {type(target_date).__name__}"
            )

        try:
            # Get today's date in UTC if not specified
            if target_date is None:
                target_date = get_utc_now().date()

            # Query daily_alert_counts
            sql = """
                SELECT alert_count
                FROM daily_alert_counts
                WHERE count_date = ?
                LIMIT 1
            """
            result = self.db.execute(sql, [target_date])
            row = result.fetchone()

            if row:
                count = row[0]
                logger.debug(
                    f"Daily alert count for {target_date}: {count}"
                )
                return count
            else:
                logger.debug(
                    f"No daily alert count found for {target_date}, returning 0"
                )
                return 0

        except Exception as e:
            logger.error(
                f"Error retrieving daily alert count for {target_date}: {e}",
                exc_info=True
            )
            return 0

    def reset_daily_count(self, target_date: date) -> bool:
        """
        Reset daily alert count for a specific date to 0.

        Updates daily_alert_counts table, setting alert_count to 0 for the given date.
        Useful for testing or manual reset operations.

        Args:
            target_date (date): Date to reset

        Returns:
            bool: True on success, False on database error

        Raises:
            ValueError: If target_date is not a date object

        Example:
            >>> from datetime import date
            >>> throttler = AlertThrottler(db, config)
            >>> success = throttler.reset_daily_count(date.today())
            >>> if success:
            ...     print("Daily count reset")
        """
        if not isinstance(target_date, date):
            raise ValueError(
                f"target_date must be date object, got {type(target_date).__name__}"
            )

        try:
            sql = """
                UPDATE daily_alert_counts
                SET alert_count = 0
                WHERE count_date = ?
            """
            self.db.execute_insert(sql, [target_date])

            logger.info(f"Reset daily alert count for {target_date}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to reset daily alert count for {target_date}: {e}",
                exc_info=True
            )
            return False
