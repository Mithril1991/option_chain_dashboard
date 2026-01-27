# Database Module - Option Chain Dashboard

Thread-safe DuckDB connection manager with connection pooling and context manager support.

## Quick Start

### 1. Initialize at Application Startup

```python
from functions.db.connection import init_db

# In your main.py or app.py
init_db()  # Loads from data/cache.db and data/sql/schema.sql by default
```

### 2. Use in Any Module

```python
from functions.db import get_db

db = get_db()

# Execute a query
result = db.execute_one(
    "SELECT * FROM options WHERE symbol = ?",
    ["AAPL"]
)

# Insert data
db.execute_insert(
    "INSERT INTO options (symbol, strike, price) VALUES (?, ?, ?)",
    ["AAPL", 150.0, 2.50]
)
```

### 3. Use Context Manager (Optional)

```python
from functions.db import get_db

db = get_db()

with db.connection() as conn:
    result = conn.execute("SELECT COUNT(*) FROM options").fetchone()
    print(f"Total options: {result[0]}")
```

## API

### Global Functions

- `init_db(db_path=None, schema_path=None, auto_initialize=True)` - Initialize singleton
- `get_db() -> DuckDBManager` - Get the connection manager
- `close_db()` - Close connection for current thread
- `reset_db()` - Reset singleton (for testing)

### DuckDBManager Methods

- `get_connection()` - Get or create thread-local connection
- `close_connection()` - Close thread-local connection
- `initialize(ignore_exists=True)` - Initialize schema from SQL file
- `execute(sql, params=None)` - Execute SELECT, return all rows
- `execute_one(sql, params=None)` - Execute SELECT, return first row
- `execute_insert(sql, params=None, commit=True)` - Execute INSERT/UPDATE/DELETE
- `connection()` - Context manager for safe connection handling

## Thread Safety

Each thread gets its own connection (thread-local storage). Safe to use in multi-threaded applications.

```python
from threading import Thread
from functions.db import get_db

def worker():
    db = get_db()  # Each thread gets its own connection
    result = db.execute_one("SELECT 1")

db = get_db()  # Main thread connection

thread = Thread(target=worker)
thread.start()
thread.join()  # Both had separate connections - no conflicts
```

## Database Schema

13 tables covering:
- **Options Data**: option contracts with Greeks
- **Market Data**: underlying stock prices
- **Strategies**: multi-leg option trades
- **Analysis**: pattern detection and scoring
- **Metadata**: cache and scan tracking
- **Audit**: application events logging

See `data/sql/schema.sql` for complete schema.

## Documentation

- **DATABASE_CONNECTION_GUIDE.md** - Complete API reference and patterns
- **tests/tech/unit/test_db_connection.py** - Usage examples in tests
- **Docstrings** in connection.py - Inline documentation with examples

## Examples

### Basic Query
```python
from functions.db import get_db

db = get_db()
option = db.execute_one(
    "SELECT * FROM options WHERE symbol = ? AND strike = ?",
    ["AAPL", 150.0]
)
if option:
    print(f"Found: {option}")
```

### Batch Insert
```python
from functions.db import get_db

db = get_db()

# Insert multiple rows, commit once
data = [
    ["AAPL", 150.0, 2.50],
    ["AAPL", 155.0, 1.80],
    ["AAPL", 160.0, 1.20],
]

for symbol, strike, price in data:
    db.execute_insert(
        "INSERT INTO options (symbol, strike, price) VALUES (?, ?, ?)",
        [symbol, strike, price],
        commit=False
    )

db.get_connection().commit()  # Commit all at once
```

### Testing
```python
import pytest
from pathlib import Path
from functions.db import init_db, reset_db

@pytest.fixture(autouse=True)
def setup_test_db():
    """Reset database for each test."""
    reset_db()
    init_db(db_path=Path("/tmp/test.db"))
    yield
    reset_db()

def test_something():
    from functions.db import get_db
    db = get_db()
    # Your test code here
```

## Error Handling

```python
from functions.db import get_db

db = get_db()

try:
    result = db.execute_one("SELECT * FROM options WHERE symbol = ?", ["AAPL"])
except RuntimeError as e:
    print(f"Query failed: {e}")
```

## Logging

All operations are logged to `logs/option_chain_dashboard.log`:

```bash
# View all database operations
grep "functions.db" logs/option_chain_dashboard.log

# View errors only
grep "functions.db.*ERROR" logs/option_chain_dashboard.log
```

## Performance Tips

1. **Use parameters** - Prevents SQL injection and improves query reuse
   ```python
   # Good
   db.execute("SELECT * FROM options WHERE symbol = ?", ["AAPL"])

   # Avoid
   db.execute(f"SELECT * FROM options WHERE symbol = 'AAPL'")
   ```

2. **Batch operations** - Commit multiple changes at once
   ```python
   for row in rows:
       db.execute_insert(sql, row, commit=False)
   db.get_connection().commit()
   ```

3. **Use indexes** - Schema includes indexes on common columns

4. **Connections cached** - No need to recreate connections

## Configuration

Default paths (relative to project root):
- Database: `data/cache.db`
- Schema: `data/sql/schema.sql`

Override at startup:
```python
from pathlib import Path
from functions.db import init_db

init_db(
    db_path=Path("custom/location/cache.db"),
    schema_path=Path("custom/location/schema.sql")
)
```

## See Also

- `data/sql/schema.sql` - Database schema definition
- `docs/DATABASE_CONNECTION_GUIDE.md` - Complete documentation
- `tests/tech/unit/test_db_connection.py` - Usage examples
- `functions/util/logging_setup.py` - Logging configuration

## License

Part of the Option Chain Dashboard project.
