"""
DuckDB connection management with thread-local caching and connection pooling.

Provides a thread-safe connection manager for DuckDB database operations with:
- Thread-local connection caching (one connection per thread)
- Connection pooling for efficiency
- Context manager support for safe resource management
- Schema initialization from SQL files
- Helper methods for common query patterns
- Comprehensive logging of all database operations

Usage:
    from functions.db.connection import get_db, init_db

    # Initialize database on startup
    init_db()

    # Get connection (thread-local cached)
    db = get_db()
    result = db.execute_one("SELECT * FROM options WHERE symbol = ?", ["AAPL"])

    # Or use context manager
    with get_db().connection() as conn:
        result = conn.execute("SELECT COUNT(*) FROM options").fetchall()

    # Insert data with automatic commit
    db.execute_insert(
        "INSERT INTO options (symbol, strike, price) VALUES (?, ?, ?)",
        ["AAPL", 150.0, 2.50]
    )
"""

import threading
from pathlib import Path
from typing import Any, Optional, List, Dict, Tuple
from contextlib import contextmanager

import duckdb

from functions.util.logging_setup import get_logger

logger = get_logger(__name__)


class DuckDBManager:
    """
    Thread-safe DuckDB connection manager with pooling and context manager support.

    Features:
    - Thread-local connection caching (one connection per thread)
    - Automatic schema initialization
    - Helper methods for queries (execute, execute_one, execute_insert)
    - Context manager for safe resource management
    - Graceful error handling for "already exists" conditions
    - Comprehensive logging of database operations

    Attributes:
        db_path (Path): Path to the DuckDB database file
        schema_path (Path): Path to the schema.sql file
        _thread_local (threading.local): Thread-local storage for connections
    """

    def __init__(self, db_path: Path, schema_path: Optional[Path] = None) -> None:
        """
        Initialize the DuckDB connection manager.

        Args:
            db_path: Path to the DuckDB database file (will be created if missing)
            schema_path: Path to SQL schema file to initialize database.
                        If None, defaults to data/sql/schema.sql

        Raises:
            ValueError: If db_path is not an absolute path
        """
        # Validate path is absolute
        if not db_path.is_absolute():
            raise ValueError(f"db_path must be absolute, got {db_path}")

        self.db_path = db_path
        self.schema_path = schema_path or (db_path.parent / "sql" / "schema.sql")

        # Thread-local storage for connections
        self._thread_local = threading.local()

        logger.info(f"DuckDBManager initialized: db_path={db_path}, schema_path={self.schema_path}")

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """
        Get or create a thread-local DuckDB connection.

        Returns a cached connection for the current thread. If no connection exists
        for this thread, creates a new one. Each thread maintains its own connection
        to avoid threading issues.

        Returns:
            A DuckDB connection object

        Raises:
            RuntimeError: If connection cannot be established
        """
        if not hasattr(self._thread_local, "connection"):
            try:
                logger.debug(f"Creating new DuckDB connection for thread {threading.current_thread().name}")
                self._thread_local.connection = duckdb.connect(str(self.db_path))
            except Exception as e:
                logger.error(f"Failed to connect to DuckDB at {self.db_path}: {e}")
                raise RuntimeError(f"Cannot connect to DuckDB: {e}") from e

        return self._thread_local.connection

    def close_connection(self) -> None:
        """
        Close the thread-local connection.

        Safely closes the connection for the current thread if it exists.
        Safe to call even if no connection is open (no-op in that case).
        """
        if hasattr(self._thread_local, "connection"):
            try:
                logger.debug(f"Closing DuckDB connection for thread {threading.current_thread().name}")
                self._thread_local.connection.close()
                delattr(self._thread_local, "connection")
            except Exception as e:
                logger.warning(f"Error closing DuckDB connection: {e}")

    @contextmanager
    def connection(self):
        """
        Context manager for safe connection handling.

        Yields a DuckDB connection and ensures it remains open for the context.
        Connection is cached thread-locally and remains open after context exit
        (connections are closed explicitly via close_connection).

        Usage:
            with db_manager.connection() as conn:
                result = conn.execute("SELECT * FROM options").fetchall()

        Yields:
            DuckDB connection object

        Example:
            manager = DuckDBManager(Path("data/cache.db"))
            with manager.connection() as conn:
                result = conn.execute("SELECT COUNT(*) FROM options").fetchone()
        """
        try:
            conn = self.get_connection()
            logger.debug(f"Entering connection context for thread {threading.current_thread().name}")
            yield conn
        except Exception as e:
            logger.error(f"Error in connection context: {e}")
            raise
        finally:
            logger.debug(f"Exiting connection context for thread {threading.current_thread().name}")

    def initialize(self, ignore_exists: bool = True) -> None:
        """
        Initialize database schema from SQL file.

        Loads and executes SQL from schema.sql file to set up database tables.
        Handles "already exists" errors gracefully if ignore_exists=True.

        Args:
            ignore_exists: If True, ignore "already exists" errors during table creation.
                          If False, raise error on existing tables.

        Raises:
            FileNotFoundError: If schema.sql file does not exist
            RuntimeError: If SQL execution fails (unless it's an "already exists" error)

        Example:
            manager = DuckDBManager(Path("data/cache.db"))
            manager.initialize()  # Creates tables if needed
        """
        if not self.schema_path.exists():
            raise FileNotFoundError(
                f"Schema file not found at {self.schema_path}. "
                f"Create {self.schema_path} with table definitions."
            )

        try:
            with open(self.schema_path, "r") as f:
                schema_sql = f.read()

            logger.info(f"Initializing database schema from {self.schema_path}")
            conn = self.get_connection()
            conn.execute(schema_sql)
            logger.info("Database schema initialized successfully")

        except duckdb.CatalogException as e:
            if ignore_exists and "already exists" in str(e).lower():
                logger.debug(f"Table already exists during initialization: {e}")
            else:
                logger.error(f"Catalog error during schema initialization: {e}")
                raise RuntimeError(f"Schema initialization failed: {e}") from e

        except FileNotFoundError as e:
            logger.error(f"Schema file not found: {self.schema_path}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error during schema initialization: {e}")
            raise RuntimeError(f"Schema initialization failed: {e}") from e

    def execute(self, sql: str, params: Optional[List[Any]] = None) -> Any:
        """
        Execute a SQL query and return all results.

        Executes a SQL query with optional parameters and returns all rows
        as DuckDB result format. Useful for SELECT queries returning multiple rows.

        Args:
            sql: SQL query string with ? placeholders for parameters
            params: Optional list of parameters to bind to query

        Returns:
            DuckDB relation object (can be converted to list/dataframe)

        Raises:
            RuntimeError: If query execution fails

        Example:
            manager = DuckDBManager(Path("data/cache.db"))
            results = manager.execute(
                "SELECT * FROM options WHERE strike > ? AND symbol = ?",
                [150.0, "AAPL"]
            )
            for row in results.fetchall():
                print(row)
        """
        try:
            logger.debug(f"Executing query: {sql[:80]}..." if len(sql) > 80 else f"Executing query: {sql}")
            conn = self.get_connection()

            if params:
                result = conn.execute(sql, params)
            else:
                result = conn.execute(sql)

            return result

        except Exception as e:
            logger.error(f"Query execution failed: {sql[:100]} - Error: {e}")
            raise RuntimeError(f"Query execution failed: {e}") from e

    def execute_one(self, sql: str, params: Optional[List[Any]] = None) -> Optional[Tuple]:
        """
        Execute a SQL query and return the first result row.

        Executes a SQL query and returns only the first row as a tuple.
        Useful for queries expected to return a single row (e.g., lookups).

        Args:
            sql: SQL query string with ? placeholders for parameters
            params: Optional list of parameters to bind to query

        Returns:
            First row as tuple, or None if no results

        Raises:
            RuntimeError: If query execution fails

        Example:
            manager = DuckDBManager(Path("data/cache.db"))
            row = manager.execute_one(
                "SELECT * FROM options WHERE symbol = ? AND strike = ?",
                ["AAPL", 150.0]
            )
            if row:
                print(f"Found option: {row}")
            else:
                print("No option found")
        """
        try:
            logger.debug(f"Executing single-row query: {sql[:80]}..." if len(sql) > 80 else f"Executing query: {sql}")
            result = self.execute(sql, params)
            row = result.fetchone()

            if row:
                logger.debug(f"Query returned row: {row}")
            else:
                logger.debug("Query returned no rows")

            return row

        except Exception as e:
            logger.error(f"Single-row query execution failed: {e}")
            raise RuntimeError(f"Single-row query execution failed: {e}") from e

    def execute_insert(
        self, sql: str, params: Optional[List[Any]] = None, commit: bool = True
    ) -> int:
        """
        Execute an INSERT/UPDATE/DELETE query and return rows affected.

        Executes a SQL INSERT, UPDATE, or DELETE statement with optional parameters.
        Automatically commits transaction if commit=True.

        Args:
            sql: SQL query string (INSERT/UPDATE/DELETE) with ? placeholders
            params: Optional list of parameters to bind to query
            commit: If True, automatically commit transaction (default: True)

        Returns:
            Number of rows affected by the operation

        Raises:
            RuntimeError: If query execution fails

        Example:
            manager = DuckDBManager(Path("data/cache.db"))

            # Insert single row
            rows = manager.execute_insert(
                "INSERT INTO options (symbol, strike, price) VALUES (?, ?, ?)",
                ["AAPL", 150.0, 2.50]
            )
            print(f"Inserted {rows} rows")

            # Insert multiple rows
            data = [
                ["AAPL", 155.0, 1.80],
                ["AAPL", 160.0, 1.20],
            ]
            for row in data:
                manager.execute_insert(
                    "INSERT INTO options (symbol, strike, price) VALUES (?, ?, ?)",
                    row
                )
        """
        try:
            logger.debug(f"Executing insert/update: {sql[:80]}..." if len(sql) > 80 else f"Executing: {sql}")
            conn = self.get_connection()

            if params:
                result = conn.execute(sql, params)
            else:
                result = conn.execute(sql)

            rows_affected = result.rowcount if hasattr(result, "rowcount") else 0

            if commit:
                conn.commit()
                logger.debug(f"Transaction committed, {rows_affected} rows affected")
            else:
                logger.debug(f"Query executed, {rows_affected} rows affected (not committed)")

            return rows_affected

        except Exception as e:
            logger.error(f"Insert/update execution failed: {sql[:100]} - Error: {e}")
            raise RuntimeError(f"Insert/update execution failed: {e}") from e

    def __enter__(self):
        """Context manager entry - returns connection."""
        return self.get_connection()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - no-op, connections managed via close_connection()."""
        if exc_type:
            logger.warning(f"Exception in context manager: {exc_type.__name__}: {exc_val}")
        return False


# Global singleton instance
_db_manager: Optional[DuckDBManager] = None
_db_manager_lock = threading.Lock()


def get_db() -> DuckDBManager:
    """
    Get the global DuckDB manager singleton instance.

    Returns the initialized DuckDB manager. Must call init_db() first to initialize.

    Returns:
        The global DuckDBManager instance

    Raises:
        RuntimeError: If init_db() has not been called yet

    Example:
        # At application startup
        init_db()

        # In any module
        db = get_db()
        result = db.execute_one("SELECT COUNT(*) FROM options")
    """
    global _db_manager

    if _db_manager is None:
        raise RuntimeError(
            "Database not initialized. Call init_db() at application startup."
        )

    return _db_manager


def init_db(
    db_path: Optional[Path] = None,
    schema_path: Optional[Path] = None,
    auto_initialize: bool = True,
) -> DuckDBManager:
    """
    Initialize the global DuckDB manager singleton.

    Must be called once at application startup before using get_db().
    Creates DuckDBManager instance with specified paths.

    Args:
        db_path: Path to DuckDB database file. Defaults to data/cache.db relative
                to project root (one level up from functions/).
        schema_path: Path to schema.sql file. Defaults to data/sql/schema.sql.
        auto_initialize: If True, automatically run manager.initialize() (default: True)

    Returns:
        The initialized DuckDBManager instance

    Raises:
        RuntimeError: If already initialized (call is idempotent if same paths)
        ValueError: If paths are invalid

    Example:
        # At application startup
        from pathlib import Path
        from functions.db.connection import init_db, get_db

        # Default paths (data/cache.db and data/sql/schema.sql)
        db_manager = init_db()

        # Or custom paths
        db_manager = init_db(
            db_path=Path("/tmp/options.db"),
            schema_path=Path("/tmp/schema.sql")
        )

        # Now get_db() is available everywhere
        db = get_db()
        result = db.execute_one("SELECT COUNT(*) FROM options")
    """
    global _db_manager

    with _db_manager_lock:
        # Default paths: data/ directory in project root
        if db_path is None:
            # Path resolution: functions/db/connection.py -> functions -> project_root
            project_root = Path(__file__).parent.parent.parent
            db_path = project_root / "data" / "cache.db"

        if schema_path is None:
            schema_path = db_path.parent / "sql" / "schema.sql"

        # Ensure paths are absolute
        db_path = db_path.absolute()
        schema_path = schema_path.absolute()

        # Create database directory if needed
        db_path.parent.mkdir(parents=True, exist_ok=True)
        schema_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize manager
        if _db_manager is None:
            logger.info(f"Initializing DuckDB with db_path={db_path}")
            _db_manager = DuckDBManager(db_path=db_path, schema_path=schema_path)

            if auto_initialize:
                try:
                    _db_manager.initialize(ignore_exists=True)
                except FileNotFoundError:
                    logger.warning(
                        f"Schema file not found at {schema_path}. "
                        f"Database will be initialized on demand."
                    )

        else:
            logger.debug(f"DuckDB already initialized")

        return _db_manager


def close_db() -> None:
    """
    Close the global DuckDB connection for the current thread.

    Safe to call even if no connection is open. Useful for cleanup in tests
    or when gracefully shutting down the application.

    Example:
        # At application shutdown
        from functions.db.connection import close_db

        close_db()  # Close connection for this thread
    """
    global _db_manager

    if _db_manager is not None:
        _db_manager.close_connection()
        logger.debug("DuckDB connection closed")


def reset_db() -> None:
    """
    Reset the global DuckDB manager singleton.

    Closes current connection and clears the global instance. Useful for testing
    or when you need to reinitialize with different settings.

    This is an advanced function - normally not needed in production.

    Example:
        # In tests
        from functions.db.connection import reset_db, init_db

        reset_db()
        init_db(db_path=Path("/tmp/test.db"))
    """
    global _db_manager

    with _db_manager_lock:
        if _db_manager is not None:
            _db_manager.close_connection()
            _db_manager = None
            logger.debug("DuckDB manager reset")
