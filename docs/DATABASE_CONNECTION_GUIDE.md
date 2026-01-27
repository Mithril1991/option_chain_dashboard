# DuckDB Connection Manager Guide

Complete guide to using the DuckDB connection manager in the Option Chain Dashboard.

## Overview

The `functions.db.connection` module provides a thread-safe DuckDB connection manager with:

- **Thread-local connection caching**: One connection per thread, no global state conflicts
- **Connection pooling**: Efficient connection reuse
- **Context manager support**: Safe resource management with `with` statements
- **Query helpers**: Convenience methods for common operations
- **Schema initialization**: Automatic database setup from SQL files
- **Comprehensive logging**: All operations logged for debugging

## Quick Start

### 1. Initialize at Application Startup

```python
from functions.db.connection import init_db

# At application startup (main entry point)
init_db()

# Optional: with custom paths
init_db(
    db_path=Path("data/my_database.db"),
    schema_path=Path("data/sql/my_schema.sql")
)
```

### 2. Use Anywhere in Your Code

```python
from functions.db.connection import get_db

# Get the database manager
db = get_db()

# Execute a query
result = db.execute_one(
    "SELECT * FROM options WHERE symbol = ?",
    ["AAPL"]
)

# Insert data
rows = db.execute_insert(
    "INSERT INTO options (symbol, strike, price) VALUES (?, ?, ?)",
    ["AAPL", 150.0, 2.50]
)
```

### 3. Cleanup (Optional)

```python
from functions.db.connection import close_db

# At application shutdown
close_db()  # Closes connection for current thread
```

## API Reference

### Global Functions

#### `init_db(db_path=None, schema_path=None, auto_initialize=True) -> DuckDBManager`

Initialize the global DuckDB manager singleton.

**Arguments:**
- `db_path` (Path, optional): Database file path. Defaults to `data/cache.db` relative to project root.
- `schema_path` (Path, optional): Schema SQL file path. Defaults to `data/sql/schema.sql`.
- `auto_initialize` (bool): If True, automatically run schema initialization (default: True).

**Returns:** The initialized DuckDBManager instance

**Raises:**
- `RuntimeError`: If already initialized (idempotent if same paths)
- `ValueError`: If paths are invalid

**Example:**
```python
from pathlib import Path
from functions.db.connection import init_db

# Default paths
db_manager = init_db()

# Custom paths
db_manager = init_db(
    db_path=Path("/tmp/options.db"),
    schema_path=Path("/tmp/schema.sql")
)
```

---

#### `get_db() -> DuckDBManager`

Get the global DuckDB manager singleton.

**Returns:** The initialized DuckDBManager instance

**Raises:** `RuntimeError` if init_db() has not been called

**Example:**
```python
from functions.db.connection import get_db

db = get_db()
result = db.execute_one("SELECT COUNT(*) FROM options")
```

---

#### `close_db() -> None`

Close the thread-local connection for the current thread.

Safe to call even if no connection is open. Useful for cleanup or graceful shutdown.

**Example:**
```python
from functions.db.connection import close_db

# At application shutdown
close_db()
```

---

#### `reset_db() -> None`

Reset the global DuckDB manager singleton.

Closes current connection and clears the global instance. Useful for testing.

**Example:**
```python
from functions.db.connection import reset_db, init_db

# In tests
reset_db()
init_db(db_path=Path("/tmp/test.db"))
```

---

### DuckDBManager Class

#### `DuckDBManager(db_path, schema_path=None)`

Create a DuckDB connection manager.

**Arguments:**
- `db_path` (Path): Absolute path to database file
- `schema_path` (Path, optional): Path to schema.sql file

**Raises:** `ValueError` if db_path is not absolute

**Example:**
```python
from pathlib import Path
from functions.db.connection import DuckDBManager

manager = DuckDBManager(
    db_path=Path("/tmp/cache.db"),
    schema_path=Path("/tmp/schema.sql")
)
```

---

#### `manager.get_connection() -> duckdb.DuckDBPyConnection`

Get or create a thread-local DuckDB connection.

Returns a cached connection for the current thread. Subsequent calls return the same connection.

**Returns:** DuckDB connection object

**Example:**
```python
manager = DuckDBManager(db_path=Path("data/cache.db"))
conn = manager.get_connection()
result = conn.execute("SELECT * FROM options").fetchall()
```

---

#### `manager.close_connection() -> None`

Close the thread-local connection.

Safe to call even if no connection is open.

**Example:**
```python
manager.close_connection()
```

---

#### `manager.connection() -> context manager`

Context manager for safe connection handling.

Yields a DuckDB connection within a try/finally block. Connection remains open after context exit.

**Yields:** DuckDB connection object

**Example:**
```python
manager = DuckDBManager(db_path=Path("data/cache.db"))

with manager.connection() as conn:
    result = conn.execute("SELECT COUNT(*) FROM options").fetchone()
    print(f"Total options: {result[0]}")
```

---

#### `manager.initialize(ignore_exists=True) -> None`

Initialize database schema from SQL file.

Executes the SQL file to create tables. Handles "already exists" errors gracefully.

**Arguments:**
- `ignore_exists` (bool): If True, ignore "already exists" errors (default: True)

**Raises:**
- `FileNotFoundError`: If schema.sql file not found
- `RuntimeError`: If SQL execution fails (unless "already exists" error)

**Example:**
```python
manager = DuckDBManager(
    db_path=Path("data/cache.db"),
    schema_path=Path("data/sql/schema.sql")
)
manager.initialize()  # Creates tables if needed
```

---

#### `manager.execute(sql, params=None) -> DuckDB Relation`

Execute a SELECT query and return all results.

**Arguments:**
- `sql` (str): SQL query with `?` placeholders for parameters
- `params` (list, optional): Query parameters

**Returns:** DuckDB relation object (convert with `.fetchall()`, `.fetchone()`, etc.)

**Raises:** `RuntimeError` if query execution fails

**Example:**
```python
manager = DuckDBManager(db_path=Path("data/cache.db"))

# Query with parameters
results = manager.execute(
    "SELECT * FROM options WHERE strike > ? AND symbol = ?",
    [150.0, "AAPL"]
)

# Convert to list
rows = results.fetchall()
for row in rows:
    print(row)

# Or convert to pandas DataFrame
df = results.df()
```

---

#### `manager.execute_one(sql, params=None) -> Optional[tuple]`

Execute a SELECT query and return the first row only.

**Arguments:**
- `sql` (str): SQL query with `?` placeholders
- `params` (list, optional): Query parameters

**Returns:** First row as tuple, or None if no results

**Raises:** `RuntimeError` if query execution fails

**Example:**
```python
manager = DuckDBManager(db_path=Path("data/cache.db"))

# Get single option
option = manager.execute_one(
    "SELECT * FROM options WHERE symbol = ? AND strike = ?",
    ["AAPL", 150.0]
)

if option:
    print(f"Found: {option}")
else:
    print("Not found")
```

---

#### `manager.execute_insert(sql, params=None, commit=True) -> int`

Execute an INSERT/UPDATE/DELETE query.

**Arguments:**
- `sql` (str): SQL statement with `?` placeholders
- `params` (list, optional): Query parameters
- `commit` (bool): If True, auto-commit transaction (default: True)

**Returns:** Number of rows affected

**Raises:** `RuntimeError` if query execution fails

**Example:**
```python
manager = DuckDBManager(db_path=Path("data/cache.db"))

# Insert single row
rows = manager.execute_insert(
    "INSERT INTO options (symbol, strike, price) VALUES (?, ?, ?)",
    ["AAPL", 150.0, 2.50]
)
print(f"Inserted {rows} rows")

# Update
rows = manager.execute_insert(
    "UPDATE options SET price = ? WHERE symbol = ?",
    [2.75, "AAPL"]
)

# Bulk insert without auto-commit
for symbol in ["AAPL", "GOOGL", "MSFT"]:
    manager.execute_insert(
        "INSERT INTO stocks (symbol) VALUES (?)",
        [symbol],
        commit=False
    )
manager.get_connection().commit()  # Commit once at end
```

---

#### `with manager as conn:`

Context manager for use with `with` statement.

**Example:**
```python
manager = DuckDBManager(db_path=Path("data/cache.db"))

with manager as conn:
    result = conn.execute("SELECT COUNT(*) FROM options").fetchone()
    print(f"Total options: {result[0]}")
```

---

## Usage Patterns

### Pattern 1: Global Singleton (Recommended)

Initialize once at startup, use everywhere.

```python
# main.py or app.py
from functions.db.connection import init_db

def main():
    init_db()  # Initialize database
    # ... rest of application
    run_app()

if __name__ == "__main__":
    main()
```

```python
# Any other module
from functions.db.connection import get_db

def get_options_count():
    db = get_db()
    result = db.execute_one("SELECT COUNT(*) FROM options")
    return result[0]
```

---

### Pattern 2: Direct Manager Instantiation

Create manager instances for specific needs.

```python
from pathlib import Path
from functions.db.connection import DuckDBManager

# Create for specific database
manager = DuckDBManager(db_path=Path("data/cache.db"))
manager.initialize()

# Use it
result = manager.execute_one("SELECT * FROM options LIMIT 1")
```

---

### Pattern 3: Context Manager

Use with `with` statement for explicit lifecycle.

```python
from functions.db.connection import get_db

db = get_db()

# Use context manager
with db.connection() as conn:
    result = conn.execute("SELECT COUNT(*) FROM options").fetchone()
```

---

### Pattern 4: Batch Operations

Insert multiple rows efficiently.

```python
from functions.db.connection import get_db

db = get_db()

# Insert multiple rows, commit once
options_data = [
    ["AAPL", 150.0, 2.50],
    ["AAPL", 155.0, 1.80],
    ["AAPL", 160.0, 1.20],
]

for symbol, strike, price in options_data:
    db.execute_insert(
        "INSERT INTO options (symbol, strike, price) VALUES (?, ?, ?)",
        [symbol, strike, price],
        commit=False  # Don't commit each row
    )

# Commit all at once
db.get_connection().commit()
```

---

### Pattern 5: Testing

Reset database for each test.

```python
import pytest
from pathlib import Path
from functions.db.connection import init_db, reset_db

@pytest.fixture(autouse=True)
def clean_database():
    """Reset database before each test."""
    reset_db()
    init_db(
        db_path=Path("/tmp/test.db"),
        schema_path=Path("data/sql/schema.sql")
    )
    yield
    reset_db()

def test_insert_option():
    from functions.db.connection import get_db
    db = get_db()

    db.execute_insert(
        "INSERT INTO options (symbol, strike, price) VALUES (?, ?, ?)",
        ["AAPL", 150.0, 2.50]
    )

    result = db.execute_one(
        "SELECT * FROM options WHERE symbol = ?",
        ["AAPL"]
    )
    assert result is not None
```

---

## Thread Safety

The connection manager is **thread-safe** using thread-local storage.

Each thread gets its own connection:

```python
from threading import Thread
from functions.db.connection import get_db, init_db

init_db()

def worker():
    """Each thread gets its own connection."""
    db = get_db()
    result = db.execute_one("SELECT 1")
    print(f"Thread result: {result}")

# Main thread
db = get_db()

# Start worker thread
thread = Thread(target=worker)
thread.start()
thread.join()

# Both had their own connections
```

---

## Error Handling

### Common Errors

**RuntimeError: Database not initialized**
```python
from functions.db.connection import get_db

# ERROR: Call init_db() first
db = get_db()  # RuntimeError!

# CORRECT:
from functions.db.connection import init_db
init_db()
db = get_db()
```

**FileNotFoundError: Schema file not found**
```python
from pathlib import Path
from functions.db.connection import DuckDBManager

# ERROR: File doesn't exist
manager = DuckDBManager(
    db_path=Path("data/cache.db"),
    schema_path=Path("data/sql/nonexistent.sql")
)
manager.initialize()  # FileNotFoundError!

# CORRECT: Create schema.sql first, or set auto_initialize=False
```

**RuntimeError: Query execution failed**
```python
from functions.db.connection import get_db

db = get_db()

# ERROR: Invalid SQL
try:
    result = db.execute("INVALID SQL SYNTAX")  # RuntimeError!
except RuntimeError as e:
    print(f"Query failed: {e}")
```

---

## Database Schema

The default schema includes:

### Core Tables
- **options**: Individual option contracts
- **stock_prices**: Underlying stock data
- **strategies**: Multi-leg option strategies
- **strategy_legs**: Individual strategy components

### Analysis Tables
- **detected_patterns**: Pattern detection results
- **opportunities**: Opportunity scoring results

### Metadata Tables
- **cache_metadata**: Cache freshness tracking
- **scan_results**: Historical scan records
- **events**: Application event log

See `data/sql/schema.sql` for complete schema definition.

---

## Performance Tips

1. **Use parameters for queries** - Prevents SQL injection and improves reuse
   ```python
   # Good
   result = db.execute("SELECT * FROM options WHERE symbol = ?", ["AAPL"])

   # Avoid
   result = db.execute(f"SELECT * FROM options WHERE symbol = 'AAPL'")
   ```

2. **Batch inserts** - Commit multiple rows at once
   ```python
   for row in rows:
       db.execute_insert(sql, row, commit=False)
   db.get_connection().commit()
   ```

3. **Use indexes** - Schema includes indexes on common query columns
   ```python
   -- Already indexed in schema
   CREATE INDEX idx_options_symbol_exp ON options(symbol, expiration);
   ```

4. **Cache connections** - Thread-local caching is automatic
   ```python
   # No need to create new connections
   db = get_db()  # Returns cached connection
   ```

---

## Logging

All database operations are logged to `logs/option_chain_dashboard.log`.

**Log levels:**
- **DEBUG**: Query execution details
- **INFO**: Initialization, schema creation
- **WARNING**: Connection issues, ignored errors
- **ERROR**: Query failures, execution errors

Check logs for debugging:
```bash
# Watch logs in real-time
tail -f logs/option_chain_dashboard.log

# Filter for database errors
grep "\[ERROR\]" logs/option_chain_dashboard.log | grep -i "database\|query"
```

---

## Example: Complete Application

```python
"""Option Chain Dashboard application with database."""

from pathlib import Path
from functions.db.connection import init_db, get_db, close_db


def fetch_options_from_api(symbol: str) -> list:
    """Fetch options data from API (mock for example)."""
    return [
        {"symbol": "AAPL", "strike": 150.0, "price": 2.50},
        {"symbol": "AAPL", "strike": 155.0, "price": 1.80},
        {"symbol": "AAPL", "strike": 160.0, "price": 1.20},
    ]


def cache_options_in_db(symbol: str) -> int:
    """Fetch options and cache in database."""
    db = get_db()

    # Fetch from API
    options = fetch_options_from_api(symbol)

    # Cache in database
    count = 0
    for opt in options:
        db.execute_insert(
            "INSERT INTO options (symbol, strike, price) VALUES (?, ?, ?)",
            [opt["symbol"], opt["strike"], opt["price"]]
        )
        count += 1

    return count


def get_cached_options(symbol: str) -> list:
    """Get options from cache."""
    db = get_db()

    result = db.execute(
        "SELECT * FROM options WHERE symbol = ? ORDER BY strike",
        [symbol]
    )

    return result.fetchall()


def main():
    """Main application entry point."""
    # 1. Initialize database
    init_db()

    # 2. Cache some options
    symbol = "AAPL"
    cached = cache_options_in_db(symbol)
    print(f"Cached {cached} options for {symbol}")

    # 3. Retrieve cached options
    options = get_cached_options(symbol)
    for opt in options:
        print(f"  {opt[0]} ${opt[1]} strike: ${opt[2]} price")

    # 4. Cleanup
    close_db()


if __name__ == "__main__":
    main()
```

---

## See Also

- `functions/config/settings.py` - Configuration management
- `functions/util/logging_setup.py` - Logging configuration
- `data/sql/schema.sql` - Database schema definition
- `tests/tech/unit/test_db_connection.py` - Unit tests with examples

---

## Questions?

Check the docstrings in `functions/db/connection.py` for more details:
```python
from functions.db.connection import DuckDBManager
help(DuckDBManager.execute)
```

Or examine test cases in `tests/tech/unit/test_db_connection.py` for usage examples.
