"""
Time utility functions for the Option Chain Dashboard.

Provides consistent timezone handling, market hours calculations, and
time conversions between UTC and Eastern Time (market timezone).

All timestamps use UTC internally for consistency across systems.
Conversion to/from Eastern Time (ET) is done at system boundaries.

Market Hours (US Eastern Time):
- Regular Trading: Monday-Friday, 09:30 - 16:00 ET
- Pre-market: 04:00 - 09:30 ET
- After-hours: 16:00 - 20:00 ET

Usage:
    from functions.util.time_utils import get_utc_now, to_et, is_market_open

    now_utc = get_utc_now()
    now_et = to_et(now_utc)
    if is_market_open():
        print("Market is open!")
    remaining = market_hours_remaining()
    print(f"Market closes in {remaining} minutes")
"""

from datetime import datetime, timedelta, time
import pytz
from typing import Optional, Tuple

# ============================================================================
# Timezone Constants
# ============================================================================

UTC = pytz.UTC
"""UTC timezone"""

ET = pytz.timezone("America/New_York")
"""Eastern Time timezone (market timezone)"""

# Market hours in Eastern Time
MARKET_OPEN_TIME = time(9, 30)
"""Market opening time in ET: 09:30"""

MARKET_CLOSE_TIME = time(16, 0)
"""Market closing time in ET: 16:00"""

PREMARKET_OPEN_TIME = time(4, 0)
"""Pre-market opening time in ET: 04:00"""

AFTERHOURS_CLOSE_TIME = time(20, 0)
"""After-hours closing time in ET: 20:00"""


# ============================================================================
# Current Time Functions
# ============================================================================


def get_utc_now() -> datetime:
    """
    Get current time in UTC timezone.

    Returns:
        Current datetime in UTC with timezone info

    Example:
        from functions.util.time_utils import get_utc_now

        now = get_utc_now()
        print(f"Current UTC time: {now.isoformat()}")
        # Output: Current UTC time: 2026-01-26T21:30:45.123456+00:00
    """
    return datetime.now(UTC)


def get_et_now() -> datetime:
    """
    Get current time in Eastern Time.

    Equivalent to to_et(get_utc_now()).

    Returns:
        Current datetime in Eastern Time with timezone info

    Example:
        from functions.util.time_utils import get_et_now

        now = get_et_now()
        print(f"Current ET time: {now.isoformat()}")
        # Output: Current ET time: 2026-01-26T16:30:45.123456-05:00
    """
    return to_et(get_utc_now())


# ============================================================================
# Timezone Conversion Functions
# ============================================================================


def to_et(dt: Optional[datetime] = None) -> datetime:
    """
    Convert datetime to Eastern Time.

    If dt is naive (no timezone), assumes UTC.

    Args:
        dt: Datetime to convert. Defaults to current UTC time.

    Returns:
        Datetime in Eastern Time with timezone info

    Raises:
        TypeError: If dt is not a datetime instance

    Example:
        from datetime import datetime
        from functions.util.time_utils import to_et

        utc_time = datetime(2026, 1, 26, 21, 30, tzinfo=pytz.UTC)
        et_time = to_et(utc_time)
        print(f"ET: {et_time.strftime('%H:%M %Z')}")
        # Output: ET: 16:30 EST
    """
    if dt is None:
        dt = get_utc_now()

    if not isinstance(dt, datetime):
        raise TypeError(f"Expected datetime, got {type(dt)}")

    # If naive, assume UTC
    if dt.tzinfo is None:
        dt = UTC.localize(dt)

    # Convert to ET
    return dt.astimezone(ET)


def from_et(dt: datetime) -> datetime:
    """
    Convert datetime from Eastern Time to UTC.

    If dt is naive (no timezone), assumes Eastern Time.

    Args:
        dt: Datetime in Eastern Time to convert

    Returns:
        Datetime in UTC with timezone info

    Raises:
        TypeError: If dt is not a datetime instance

    Example:
        from datetime import datetime
        from functions.util.time_utils import from_et
        import pytz

        et_time = datetime(2026, 1, 26, 16, 30, tzinfo=pytz.timezone("America/New_York"))
        utc_time = from_et(et_time)
        print(f"UTC: {utc_time.strftime('%H:%M %Z')}")
        # Output: UTC: 21:30 UTC
    """
    if not isinstance(dt, datetime):
        raise TypeError(f"Expected datetime, got {type(dt)}")

    # If naive, assume ET
    if dt.tzinfo is None:
        dt = ET.localize(dt)

    # Convert to UTC
    return dt.astimezone(UTC)


# ============================================================================
# Market Hours Functions
# ============================================================================


def is_market_open(dt: Optional[datetime] = None) -> bool:
    """
    Check if market is currently open (regular trading hours).

    Regular trading hours: Monday-Friday, 09:30 - 16:00 ET

    Does NOT include pre-market or after-hours trading.

    Args:
        dt: Datetime to check. Defaults to current ET time.

    Returns:
        True if within regular trading hours

    Example:
        from functions.util.time_utils import is_market_open

        if is_market_open():
            print("Market is open!")
        else:
            print("Market is closed!")
    """
    if dt is None:
        dt = get_et_now()
    else:
        dt = to_et(dt)

    # Check if weekday (0=Monday, 6=Sunday)
    if dt.weekday() >= 5:  # Saturday or Sunday
        return False

    # Check if within market hours
    market_open = dt.time() >= MARKET_OPEN_TIME
    market_close = dt.time() < MARKET_CLOSE_TIME

    return market_open and market_close


def is_market_hours(dt: Optional[datetime] = None) -> Tuple[bool, str]:
    """
    Determine current market session type.

    Returns which session is active: pre-market, open, after-hours, or closed.

    Args:
        dt: Datetime to check. Defaults to current ET time.

    Returns:
        Tuple of (is_trading_hours: bool, session_type: str)
        session_type values: "pre-market", "open", "after-hours", "closed"

    Example:
        from functions.util.time_utils import is_market_hours

        is_trading, session = is_market_hours()
        print(f"Session: {session} (trading: {is_trading})")
        # Output: Session: open (trading: True)
    """
    if dt is None:
        dt = get_et_now()
    else:
        dt = to_et(dt)

    # Check if weekend
    if dt.weekday() >= 5:
        return False, "closed"

    current_time = dt.time()

    # Determine session
    if current_time < PREMARKET_OPEN_TIME:
        return False, "closed"
    elif current_time < MARKET_OPEN_TIME:
        return True, "pre-market"
    elif current_time < MARKET_CLOSE_TIME:
        return True, "open"
    elif current_time < AFTERHOURS_CLOSE_TIME:
        return True, "after-hours"
    else:
        return False, "closed"


def market_hours_remaining(dt: Optional[datetime] = None) -> int:
    """
    Get minutes remaining until market closes (regular hours).

    If market is closed, returns negative value showing time until open.
    If after-hours, returns time until after-hours ends.

    Args:
        dt: Datetime to check. Defaults to current ET time.

    Returns:
        Minutes remaining (negative if market is closed)

    Example:
        from functions.util.time_utils import market_hours_remaining

        remaining = market_hours_remaining()
        if remaining > 0:
            print(f"Market closes in {remaining} minutes")
        else:
            print(f"Market opens in {abs(remaining)} minutes")
    """
    if dt is None:
        dt = get_et_now()
    else:
        dt = to_et(dt)

    current_time = dt.time()

    # If before market opens
    if current_time < MARKET_OPEN_TIME:
        open_time_seconds = (
            MARKET_OPEN_TIME.hour * 3600 + MARKET_OPEN_TIME.minute * 60
        )
        current_seconds = current_time.hour * 3600 + current_time.minute * 60
        return (open_time_seconds - current_seconds) // 60

    # If during regular hours
    if current_time < MARKET_CLOSE_TIME:
        close_time_seconds = (
            MARKET_CLOSE_TIME.hour * 3600 + MARKET_CLOSE_TIME.minute * 60
        )
        current_seconds = current_time.hour * 3600 + current_time.minute * 60
        return (close_time_seconds - current_seconds) // 60

    # If after regular hours
    return -1


def next_market_open(dt: Optional[datetime] = None) -> datetime:
    """
    Get the datetime of the next market open.

    If market is currently open, returns next day's open.

    Args:
        dt: Reference datetime. Defaults to current ET time.

    Returns:
        Datetime of next market open in ET

    Example:
        from functions.util.time_utils import next_market_open

        next_open = next_market_open()
        print(f"Market opens next at: {next_open.strftime('%Y-%m-%d %H:%M %Z')}")
    """
    if dt is None:
        dt = get_et_now()
    else:
        dt = to_et(dt)

    # Start from tomorrow
    next_day = (dt + timedelta(days=1)).replace(
        hour=MARKET_OPEN_TIME.hour,
        minute=MARKET_OPEN_TIME.minute,
        second=0,
        microsecond=0,
    )

    # Find next weekday
    while next_day.weekday() >= 5:  # Skip weekends
        next_day += timedelta(days=1)

    return next_day


def next_market_close(dt: Optional[datetime] = None) -> datetime:
    """
    Get the datetime of the next market close.

    If market is currently open, returns today's close.
    If market is closed, returns next market day's close.

    Args:
        dt: Reference datetime. Defaults to current ET time.

    Returns:
        Datetime of next market close in ET

    Example:
        from functions.util.time_utils import next_market_close

        next_close = next_market_close()
        print(f"Market closes at: {next_close.strftime('%Y-%m-%d %H:%M %Z')}")
    """
    if dt is None:
        dt = get_et_now()
    else:
        dt = to_et(dt)

    # Try today's close
    today_close = dt.replace(
        hour=MARKET_CLOSE_TIME.hour,
        minute=MARKET_CLOSE_TIME.minute,
        second=0,
        microsecond=0,
    )

    # If today's close hasn't passed and it's a weekday, use today
    if dt < today_close and dt.weekday() < 5:
        return today_close

    # Otherwise, find next market day
    next_day = (dt + timedelta(days=1)).replace(
        hour=MARKET_CLOSE_TIME.hour,
        minute=MARKET_CLOSE_TIME.minute,
        second=0,
        microsecond=0,
    )

    while next_day.weekday() >= 5:  # Skip weekends
        next_day += timedelta(days=1)

    return next_day


# ============================================================================
# Business Day Functions
# ============================================================================


def is_trading_day(dt: Optional[datetime] = None) -> bool:
    """
    Check if given date is a trading day (weekday, not a holiday).

    Currently only checks weekdays. Does not account for market holidays.

    Args:
        dt: Datetime to check. Defaults to current ET date.

    Returns:
        True if it's a trading day

    Example:
        from datetime import datetime
        from functions.util.time_utils import is_trading_day
        import pytz

        et = pytz.timezone("America/New_York")
        friday = datetime(2026, 1, 30, tzinfo=et)  # Friday
        monday = datetime(2026, 2, 2, tzinfo=et)   # Monday

        print(is_trading_day(friday))  # True
        print(is_trading_day(monday))  # True
    """
    if dt is None:
        dt = get_et_now()
    else:
        dt = to_et(dt)

    return dt.weekday() < 5  # Monday=0, Friday=4


def get_business_days_remaining(
    dt: Optional[datetime] = None, end_date: Optional[datetime] = None
) -> int:
    """
    Get number of business days (weekdays) between two dates.

    Useful for calculating days to expiration (DTE) for options.

    Args:
        dt: Start date. Defaults to current ET date.
        end_date: End date. If None, counts to end of current day.

    Returns:
        Number of business days remaining (not including start date)

    Example:
        from datetime import datetime
        from functions.util.time_utils import get_business_days_remaining
        import pytz

        et = pytz.timezone("America/New_York")
        start = datetime(2026, 1, 26, tzinfo=et)  # Monday
        end = datetime(2026, 1, 30, tzinfo=et)    # Friday

        dte = get_business_days_remaining(start, end)
        print(f"Days to expiration: {dte}")  # 4 days
    """
    if dt is None:
        dt = get_et_now()
    else:
        dt = to_et(dt)

    if end_date is None:
        end_date = dt + timedelta(days=1)
    else:
        end_date = to_et(end_date)

    business_days = 0
    current = dt.date()
    while current < end_date.date():
        if current.weekday() < 5:  # Weekday
            business_days += 1
        current += timedelta(days=1)

    return business_days
