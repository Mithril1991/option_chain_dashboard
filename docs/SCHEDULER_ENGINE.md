# Scheduler Engine - Rate-Limit-Aware Scheduler for 24/7 Operation

## Overview

The **SchedulerEngine** (`scripts/scheduler_engine.py`) is a sophisticated state machine that manages continuous options data collection with built-in rate limiting, crash recovery, and adaptive backoff strategies. It's designed for unattended 24/7 operation with minimal manual intervention.

## Architecture

### State Machine States

The scheduler operates as a finite state machine with 5 states:

```
┌─────────┐
│  IDLE   │  Initial state, compute next collection time
└────┬────┘
     │
     ▼
┌─────────┐
│ WAITING │  Count down to scheduled collection time
└────┬────┘
     │ (time reached)
     ▼
┌─────────────┐
│ COLLECTING  │  Run scan, fetch data, buffer results
└────┬────────┘
     │ (budget ok)
     ├─→ (buffer full) ─→ FLUSHING
     │ (rate limit)
     └─→ BACKING_OFF

┌──────────┐
│ FLUSHING │  Bulk write buffered alerts to database
└────┬─────┘
     │
     └─→ WAITING (after flush)

┌────────────┐
│ BACKING_OFF│  Wait exponentially after rate limit hit
└────┬───────┘
     │ (backoff expired)
     └─→ WAITING
```

### State Descriptions

| State | Purpose | Duration | Transitions |
|-------|---------|----------|-------------|
| **IDLE** | Initialize scheduler, compute first collection time | 10 sec | → WAITING |
| **WAITING** | Count down to scheduled collection time | Variable | → COLLECTING (time reached, budget ok) or → BACKING_OFF (budget exhausted) |
| **COLLECTING** | Run scan for watchlist, fetch data, compute features | Variable | → FLUSHING (buffer full) or → WAITING (success) or → BACKING_OFF (error/rate limit) |
| **FLUSHING** | Bulk write buffered alerts to database | Variable | → WAITING (always) |
| **BACKING_OFF** | Wait after rate limit hit, implement exponential backoff | 1-30 min | → WAITING (backoff expired) |

## Rate Limiting

### Dual-Window Rate Limiting

The scheduler tracks API calls across two independent windows:

1. **Hourly Window**: Max 250 calls per hour
2. **Daily Window**: Max 2000 calls per day

Each window independently triggers rate limiting. If either window is exhausted, the scheduler enters BACKING_OFF state.

### Rate Budget Tracking

```python
# Example: 50 tickers scanned = 50 API calls

api_calls_this_hour = 50    # Reset every hour
api_calls_today = 50         # Reset every 24 hours

# Check budget
has_budget = (api_calls_this_hour < 250) and (api_calls_today < 2000)
```

### Adaptive Delays

To avoid bursting all requests at once, delays scale with budget consumption:

```
Budget Used     Delay per Call
0-25%           1.0 seconds
25-50%          2.0 seconds
50-75%          2.5 seconds
>75%            3.0 seconds
```

This paces API calls and prevents unnecessary rate limit hits.

## Exponential Backoff

When a rate limit error occurs, the scheduler backs off exponentially:

```
Consecutive Failures    Backoff Duration
1st                     1 minute
2nd                     2 minutes
3rd                     4 minutes
4th                     8 minutes
5th                     16 minutes
6th+                    30 minutes (maximum)
```

The backoff duration resets to 1 minute after a successful collection.

## Crash Recovery

All scheduler state is persisted to the database after each state change:

```python
SchedulerStateData:
  - current_state: IDLE|WAITING|COLLECTING|FLUSHING|BACKING_OFF
  - api_calls_today: Count of calls made today
  - api_calls_this_hour: Count of calls made this hour
  - hour_window_start_utc: When current hour window started
  - day_window_start_utc: When current day window started
  - next_collection_utc: Scheduled time of next collection
  - consecutive_failures: Count of consecutive rate limit hits
  - backoff_until_utc: When safe to resume after backoff
  - write_buffer_count: Number of buffered alerts awaiting flush
```

On startup, the scheduler recovers the latest persisted state. If persisted state is less than 24 hours old, it's restored. Otherwise, a fresh state is initialized.

## Configuration

### Configuration Keys

Add these to your `config.yaml`:

```yaml
scheduler:
  # List of collection times (ET, 24-hour format)
  # Use multiple times for multiple daily collections
  collection_times_et:
    - "16:15"  # Post-market close (4:15 PM ET)
  
  # Conservative API call limits (adjust based on provider)
  max_calls_per_hour: 250
  max_calls_per_day: 2000
  
  # How many buffered alerts before flushing to database
  flush_threshold: 50
  
  # How often to check state machine (seconds)
  check_interval_sec: 10
```

### Default Configuration

If not specified in `config.yaml`:

| Parameter | Default |
|-----------|---------|
| `collection_times_et` | `["16:15"]` |
| `max_calls_per_hour` | `250` |
| `max_calls_per_day` | `2000` |
| `flush_threshold` | `50` |
| `check_interval_sec` | `10` |

## Usage

### Running the Scheduler

```bash
# Install dependencies
source venv/bin/activate
pip install -r requirements.txt

# Run the scheduler (blocks forever)
python -m scripts.scheduler_engine
```

### Programmatic Usage

```python
import asyncio
from functions.config.loader import get_config_manager
from scripts.scheduler_engine import SchedulerEngine
from scripts.run_scan import run_scan

async def main():
    # Load configuration
    config_manager = get_config_manager()
    config = config_manager.get_config()
    
    # Create scheduler
    scheduler = SchedulerEngine(
        config=config,
        scan_runner=run_scan
    )
    
    # Run forever (blocks)
    await scheduler.run_forever()

if __name__ == "__main__":
    asyncio.run(main())
```

## Logging

The scheduler logs all state transitions and significant events:

```
2026-01-26T15:30:45.123Z [INFO] SchedulerEngine initialized: max_calls_per_hour=250, max_calls_per_day=2000
2026-01-26T15:30:45.456Z [INFO] State transition: IDLE → WAITING
2026-01-26T15:30:45.789Z [INFO] Computed next collection time: 2026-01-26T20:15:00+00:00 UTC
2026-01-26T16:00:00.000Z [INFO] State transition: WAITING → COLLECTING
2026-01-26T16:00:15.123Z [INFO] Incremented API calls: +50 (hour: 50/250, day: 50/2000)
2026-01-26T16:02:30.456Z [INFO] State transition: COLLECTING → FLUSHING
2026-01-26T16:02:35.789Z [INFO] Flushed 25 buffered items to database
2026-01-26T16:02:36.000Z [INFO] State transition: FLUSHING → WAITING
```

Log levels:
- **DEBUG**: Detailed state machine progression, adaptive delays, counter resets
- **INFO**: State transitions, collection events, buffer operations
- **WARNING**: Rate limit warnings, budget exhausted
- **ERROR**: Failed scans, database errors, recovery attempts

## Key Methods

### SchedulerEngine

| Method | Purpose |
|--------|---------|
| `__init__(config, scan_runner)` | Initialize scheduler and recover persisted state |
| `async run_forever()` | Main event loop (blocks forever) |
| `_compute_next_collection()` | Calculate next collection time in UTC |
| `_has_rate_budget()` | Check if API budget available |
| `_adaptive_delay()` | Calculate delay based on budget % used |
| `_exponential_backoff()` | Calculate backoff duration for current failure count |
| `_reset_hourly_counter_if_expired()` | Reset hourly counter after 60 min |
| `_reset_daily_counter_if_expired()` | Reset daily counter after 24 hours |
| `_increment_api_calls()` | Increment counters and log |
| `_handle_rate_limit_error()` | Handle rate limit error with backoff |
| `_transition_state()` | Change state and log transition |
| `_persist_state()` | Save state to database |
| `_recover_state_from_db()` | Load persisted state on startup |

### SchedulerStateRepository

| Method | Purpose |
|--------|---------|
| `save_state(state)` | Persist scheduler state to database |
| `get_latest_state()` | Recover latest persisted state |
| `_ensure_table_exists()` | Create `scheduler_state` table if needed |

## Database Schema

The scheduler creates a `scheduler_state` table:

```sql
CREATE TABLE scheduler_state (
    id INTEGER PRIMARY KEY,
    current_state VARCHAR NOT NULL,
    api_calls_today INTEGER DEFAULT 0,
    api_calls_this_hour INTEGER DEFAULT 0,
    hour_window_start_utc TIMESTAMP,
    day_window_start_utc TIMESTAMP,
    next_collection_utc TIMESTAMP,
    consecutive_failures INTEGER DEFAULT 0,
    backoff_until_utc TIMESTAMP,
    write_buffer_count INTEGER DEFAULT 0,
    last_state_change_utc TIMESTAMP,
    persisted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Timestamps

All timestamps use **UTC** with ISO 8601 format:

```
2026-01-26T15:30:45.123Z  # UTC
```

Time conversions for collection times:
- Configuration uses **Eastern Time (ET)**: "16:15"
- Internal storage uses **UTC**: "2026-01-26T20:15:00Z"
- All logging uses **UTC**

## Error Handling

The scheduler is resilient to errors:

1. **Rate Limit Hit**: Transitions to BACKING_OFF with exponential delay
2. **Scan Failed**: Logs error, backs off, tries again
3. **Database Error**: Logs error, continues with fallback
4. **Crash/Restart**: Recovers state from database, resumes

The main loop catches all exceptions and continues running.

## Performance Characteristics

| Aspect | Value |
|--------|-------|
| State check interval | 10 seconds |
| Max latency to collection | ~10 seconds |
| Memory footprint | ~10MB (state + buffer) |
| Database writes | Per state change (~every 10-30 sec) |
| CPU usage | Minimal (mostly sleeping) |

## Monitoring

Monitor scheduler health via logs:

```bash
# Watch scheduler logs in real-time
tail -f logs/option_chain_dashboard.log | grep SchedulerEngine

# Count state transitions
grep "State transition" logs/option_chain_dashboard.log | wc -l

# Check for errors
grep "ERROR" logs/option_chain_dashboard.log | grep Scheduler
```

## Troubleshooting

### Scheduler stuck in WAITING

Check if scheduled time has passed in UTC:

```python
from datetime import datetime, timezone
import pytz

next_collection_utc = ...  # From logs
now_utc = datetime.now(timezone.utc)
diff = (next_collection_utc - now_utc).total_seconds()
print(f"Time until collection: {diff:.0f} seconds")
```

### Frequent rate limit backoffs

Adjust configuration limits upward:

```yaml
scheduler:
  max_calls_per_hour: 300    # Increase from 250
  max_calls_per_day: 2500    # Increase from 2000
```

### State recovery not working

Check persisted state in database:

```sql
SELECT * FROM scheduler_state ORDER BY persisted_at DESC LIMIT 5;
```

## Implementation Details

### State Machine Loop

```python
while True:
    now_utc = datetime.now(timezone.utc)
    
    match self.current_state:
        case IDLE:
            # Compute next collection, transition to WAITING
            
        case WAITING:
            # Wait for collection time, check budget
            # Transition to COLLECTING or BACKING_OFF
            
        case COLLECTING:
            # Run scan, buffer results, check rate
            # Transition to FLUSHING or WAITING or BACKING_OFF
            
        case FLUSHING:
            # Flush buffer to database
            # Always transition to WAITING
            
        case BACKING_OFF:
            # Wait until backoff_until_utc
            # Transition to WAITING
    
    # Persist state after each iteration
    self._persist_state()
    
    # Sleep before next check
    await asyncio.sleep(check_interval_sec)
```

### Rate Budget Check

```python
def _has_rate_budget() -> bool:
    # Reset counters if windows expired
    self._reset_hourly_counter_if_expired()
    self._reset_daily_counter_if_expired()
    
    # Check both limits
    has_hourly = api_calls_this_hour < max_calls_per_hour
    has_daily = api_calls_today < max_calls_per_day
    
    return has_hourly and has_daily
```

## Future Enhancements

Potential improvements for future versions:

- [ ] Adaptive collection frequency based on market volatility
- [ ] Dynamic rate limit adjustment based on provider responses
- [ ] Multi-provider failover with per-provider rate limiting
- [ ] Pause/resume API via database flag
- [ ] Scheduler metrics dashboard
- [ ] Anomaly detection for rate limit behavior
- [ ] Integration with circuit breaker pattern

## Related Files

- **Main scheduler**: `/scripts/scheduler_engine.py`
- **Scan runner**: `/scripts/run_scan.py`
- **Config**: `/functions/config/models.py`
- **Database**: `/functions/db/connection.py`, `/functions/db/repositories.py`
- **Logging**: `/functions/util/logging_setup.py`

## References

- [ISO 8601 Date/Time Format](https://en.wikipedia.org/wiki/ISO_8601)
- [Exponential Backoff Pattern](https://en.wikipedia.org/wiki/Exponential_backoff)
- [Rate Limiting Strategies](https://cloud.google.com/architecture/rate-limiting-strategies-techniques)
- [State Machines](https://en.wikipedia.org/wiki/Finite-state_machine)

