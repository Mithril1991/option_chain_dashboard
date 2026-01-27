"""
Market calendar utilities for US equity markets.

This module provides functions for working with market hours, timezone conversion,
and trading day validation. All times are handled in UTC internally with conversion
to/from Eastern Time (ET) for market-specific operations.

Market Hours (US Equity, Eastern Time):
    - Pre-market: 4:00 AM - 9:30 AM ET
    - Regular: 9:30 AM - 4:00 PM ET
    - After-hours: 4:00 PM - 8:00 PM ET

Timezone Note:
    Functions accept and return UTC datetime objects. Internal conversions to ET
    are handled automatically for market hour calculations.
"""

from datetime import datetime, date, time, timedelta
from typing import Optional
import pytz


# Timezone definitions
UTC = pytz.UTC
ET = pytz.timezone('US/Eastern')

# Market hours (in Eastern Time)
PREMARKET_OPEN = time(4, 0)      # 4:00 AM ET
MARKET_OPEN = time(9, 30)         # 9:30 AM ET
MARKET_CLOSE = time(16, 0)        # 4:00 PM ET
AFTERHOURS_CLOSE = time(20, 0)    # 8:00 PM ET

# US Market Holidays 2026 (observed dates)
# Hard-coded for the current year as specified
MARKET_HOLIDAYS_2026 = {
    date(2026, 1, 1),    # New Year's Day
    date(2026, 1, 19),   # MLK Jr Day
    date(2026, 2, 16),   # Presidents Day
    date(2026, 4, 10),   # Good Friday
    date(2026, 5, 25),   # Memorial Day
    date(2026, 6, 19),   # Juneteenth
    date(2026, 7, 3),    # Independence Day (observed)
    date(2026, 9, 7),    # Labor Day
    date(2026, 11, 26),  # Thanksgiving
    date(2026, 12, 25),  # Christmas
}


def get_utc_now() -> datetime:
    """
    Get the current time in UTC.

    Returns:
        datetime: Current UTC datetime with timezone info.

    Example:
        >>> utc_now = get_utc_now()
        >>> utc_now.tzinfo == UTC
        True
    """
    return datetime.now(UTC)


def to_et(dt_utc: datetime) -> datetime:
    """
    Convert a UTC datetime to Eastern Time.

    Args:
        dt_utc: A datetime object in UTC (should have tzinfo=UTC).

    Returns:
        datetime: The equivalent datetime in Eastern Time (ET).

    Raises:
        ValueError: If the datetime is not UTC-aware.

    Example:
        >>> utc_dt = datetime(2026, 1, 26, 14, 30, tzinfo=UTC)
        >>> et_dt = to_et(utc_dt)
        >>> et_dt.hour
        9
    """
    if dt_utc.tzinfo is None:
        raise ValueError("Input datetime must be UTC-aware (have tzinfo=UTC)")

    # Convert to ET
    return dt_utc.astimezone(ET)


def from_et(dt_et: datetime) -> datetime:
    """
    Convert an Eastern Time datetime to UTC.

    Args:
        dt_et: A datetime object in Eastern Time (should have tzinfo=ET).

    Returns:
        datetime: The equivalent datetime in UTC.

    Raises:
        ValueError: If the datetime is not ET-aware.

    Example:
        >>> et_dt = datetime(2026, 1, 26, 9, 30, tzinfo=ET)
        >>> utc_dt = from_et(et_dt)
        >>> utc_dt.hour
        14
    """
    if dt_et.tzinfo is None:
        raise ValueError("Input datetime must be ET-aware (have tzinfo=ET)")

    # Convert to UTC
    return dt_et.astimezone(UTC)


def is_trading_day(d: date) -> bool:
    """
    Determine if a given date is a trading day.

    A trading day is a weekday (Monday-Friday) that is not a market holiday.

    Args:
        d: A date object to check.

    Returns:
        bool: True if the date is a trading day, False otherwise.

    Example:
        >>> is_trading_day(date(2026, 1, 19))  # MLK Jr Day (holiday)
        False
        >>> is_trading_day(date(2026, 1, 20))  # Tuesday (not a holiday)
        True
        >>> is_trading_day(date(2026, 1, 24))  # Saturday
        False
    """
    # Check if it's a weekend (Monday=0, Sunday=6)
    if d.weekday() >= 5:
        return False

    # Check if it's a market holiday
    if d in MARKET_HOLIDAYS_2026:
        return False

    return True


def is_market_open(dt_utc: Optional[datetime] = None) -> bool:
    """
    Determine if the market is currently open during regular hours.

    Regular market hours: 9:30 AM - 4:00 PM ET, Monday-Friday.

    Args:
        dt_utc: UTC datetime to check. If None, uses current time.

    Returns:
        bool: True if the market is open during regular hours, False otherwise.

    Example:
        >>> # Market open: Tuesday 9:30 AM ET
        >>> dt_utc = datetime(2026, 1, 27, 14, 30, tzinfo=UTC)  # 9:30 AM ET
        >>> is_market_open(dt_utc)
        True
        >>> # Market closed: Tuesday 3:00 AM ET
        >>> dt_utc = datetime(2026, 1, 27, 8, 0, tzinfo=UTC)  # 3:00 AM ET
        >>> is_market_open(dt_utc)
        False
    """
    if dt_utc is None:
        dt_utc = get_utc_now()

    dt_et = to_et(dt_utc)
    current_date = dt_et.date()
    current_time = dt_et.time()

    # Check if trading day
    if not is_trading_day(current_date):
        return False

    # Check if within regular market hours (9:30 AM - 4:00 PM ET)
    return MARKET_OPEN <= current_time < MARKET_CLOSE


def next_market_open(dt_utc: Optional[datetime] = None) -> datetime:
    """
    Calculate the next market open time from a given datetime.

    Returns the UTC time when the market will next open (9:30 AM ET).

    Args:
        dt_utc: UTC datetime to calculate from. If None, uses current time.

    Returns:
        datetime: UTC datetime of the next market open (9:30 AM ET).

    Example:
        >>> # Friday 4:00 PM ET
        >>> dt_utc = datetime(2026, 1, 23, 21, 0, tzinfo=UTC)  # 4:00 PM ET Friday
        >>> next_open = next_market_open(dt_utc)
        >>> to_et(next_open).time()
        datetime.time(9, 30)
        >>> next_open.date()
        datetime.date(2026, 1, 26)  # Monday (next trading day)
    """
    if dt_utc is None:
        dt_utc = get_utc_now()

    dt_et = to_et(dt_utc)
    current_date = dt_et.date()
    current_time = dt_et.time()

    # If before or at market open on a trading day, return today's open
    if is_trading_day(current_date) and current_time < MARKET_OPEN:
        market_open_et = ET.localize(datetime.combine(current_date, MARKET_OPEN))
        return market_open_et.astimezone(UTC)

    # Otherwise, start looking from tomorrow
    search_date = current_date + timedelta(days=1)

    # Find next trading day
    while not is_trading_day(search_date):
        search_date += timedelta(days=1)

    # Return that day's market open
    market_open_et = ET.localize(datetime.combine(search_date, MARKET_OPEN))
    return market_open_et.astimezone(UTC)


def next_market_close(dt_utc: Optional[datetime] = None) -> datetime:
    """
    Calculate the next market close time from a given datetime.

    Returns the UTC time when the market will next close (4:00 PM ET).

    Args:
        dt_utc: UTC datetime to calculate from. If None, uses current time.

    Returns:
        datetime: UTC datetime of the next market close (4:00 PM ET).

    Example:
        >>> # Monday 10:00 AM ET
        >>> dt_utc = datetime(2026, 1, 26, 15, 0, tzinfo=UTC)  # 10:00 AM ET
        >>> next_close = next_market_close(dt_utc)
        >>> to_et(next_close).time()
        datetime.time(16, 0)
        >>> next_close.date()
        datetime.date(2026, 1, 26)  # Same day
    """
    if dt_utc is None:
        dt_utc = get_utc_now()

    dt_et = to_et(dt_utc)
    current_date = dt_et.date()
    current_time = dt_et.time()

    # If before market close on a trading day, return today's close
    if is_trading_day(current_date) and current_time < MARKET_CLOSE:
        market_close_et = ET.localize(datetime.combine(current_date, MARKET_CLOSE))
        return market_close_et.astimezone(UTC)

    # Otherwise, start looking from tomorrow
    search_date = current_date + timedelta(days=1)

    # Find next trading day
    while not is_trading_day(search_date):
        search_date += timedelta(days=1)

    # Return that day's market close
    market_close_et = ET.localize(datetime.combine(search_date, MARKET_CLOSE))
    return market_close_et.astimezone(UTC)


def market_hours_remaining(dt_utc: Optional[datetime] = None) -> timedelta:
    """
    Calculate the time remaining until market close on the current trading day.

    Returns timedelta with remaining hours in the current trading session.
    If market is closed, returns the time until the next market open.

    Args:
        dt_utc: UTC datetime to calculate from. If None, uses current time.

    Returns:
        timedelta: Time remaining until market close (or until next market open if closed).

    Example:
        >>> # Monday 3:00 PM ET (1 hour before close)
        >>> dt_utc = datetime(2026, 1, 26, 20, 0, tzinfo=UTC)  # 3:00 PM ET
        >>> remaining = market_hours_remaining(dt_utc)
        >>> remaining.total_seconds() / 3600
        1.0
        >>> # After market close
        >>> dt_utc = datetime(2026, 1, 26, 21, 0, tzinfo=UTC)  # 4:00 PM ET
        >>> remaining = market_hours_remaining(dt_utc)
        >>> remaining > timedelta(hours=15)  # Until next day's 9:30 AM
        True
    """
    if dt_utc is None:
        dt_utc = get_utc_now()

    dt_et = to_et(dt_utc)
    current_date = dt_et.date()
    current_time = dt_et.time()

    # If market is currently open, return time until close
    if is_trading_day(current_date) and MARKET_OPEN <= current_time < MARKET_CLOSE:
        market_close_et = ET.localize(datetime.combine(current_date, MARKET_CLOSE))
        return market_close_et - dt_et

    # Market is closed, return time until next open
    next_open = next_market_open(dt_utc)
    return next_open - dt_utc
