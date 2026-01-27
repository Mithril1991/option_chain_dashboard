"""
Database module for Option Chain Dashboard.

Provides connection management and repository classes for data operations.

Core Components:
    - DuckDBManager: Thread-safe connection manager with pooling and context manager support
    - Connection helpers: get_db(), init_db(), close_db(), reset_db()

Usage:
    from functions.db.connection import get_db, init_db

    # At application startup
    init_db()  # Initialize with default paths (data/cache.db, data/sql/schema.sql)

    # In any module
    db = get_db()  # Get thread-local cached connection
    result = db.execute_one("SELECT * FROM options WHERE symbol = ?", ["AAPL"])

    # For context manager usage
    with db.connection() as conn:
        results = conn.execute("SELECT COUNT(*) FROM options").fetchall()

    # Insert/update with automatic commit
    rows = db.execute_insert(
        "INSERT INTO options (symbol, strike, price) VALUES (?, ?, ?)",
        ["AAPL", 150.0, 2.50]
    )
"""

# Public API exports
from functions.db.connection import (
    DuckDBManager,
    get_db,
    init_db,
    close_db,
    reset_db,
)

__all__ = [
    "DuckDBManager",
    "get_db",
    "init_db",
    "close_db",
    "reset_db",
]
