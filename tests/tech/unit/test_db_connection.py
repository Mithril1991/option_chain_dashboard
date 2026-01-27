"""
Unit tests for DuckDB connection manager.

Tests the DuckDBManager class with focus on:
- Thread-local connection caching
- Connection lifecycle management
- Query execution (execute, execute_one, execute_insert)
- Context manager functionality
- Schema initialization
- Error handling
"""

import pytest
import tempfile
from pathlib import Path
from threading import Thread
import time

# Note: These tests require duckdb to be installed
# Run with: pytest tests/tech/unit/test_db_connection.py


@pytest.fixture
def temp_db():
    """Create a temporary database directory and files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir)
        sql_dir = db_dir / "sql"
        sql_dir.mkdir(parents=True)

        # Create a minimal schema for testing
        schema_file = sql_dir / "schema.sql"
        schema_file.write_text("""
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY,
                name VARCHAR NOT NULL,
                value DECIMAL(10, 2)
            );
        """)

        db_file = db_dir / "test.db"

        yield {
            "db_path": db_file,
            "schema_path": schema_file,
            "db_dir": db_dir,
        }


class TestDuckDBManager:
    """Tests for DuckDBManager class."""

    def test_initialization(self, temp_db):
        """Test DuckDBManager initialization with paths."""
        from functions.db.connection import DuckDBManager

        manager = DuckDBManager(
            db_path=temp_db["db_path"],
            schema_path=temp_db["schema_path"],
        )

        assert manager.db_path == temp_db["db_path"]
        assert manager.schema_path == temp_db["schema_path"]

    def test_initialization_with_relative_path_fails(self, temp_db):
        """Test that relative paths are rejected."""
        from functions.db.connection import DuckDBManager

        with pytest.raises(ValueError, match="must be absolute"):
            DuckDBManager(
                db_path=Path("relative/path.db"),
                schema_path=temp_db["schema_path"],
            )

    def test_get_connection(self, temp_db):
        """Test getting a connection."""
        from functions.db.connection import DuckDBManager

        manager = DuckDBManager(
            db_path=temp_db["db_path"],
            schema_path=temp_db["schema_path"],
        )

        conn = manager.get_connection()
        assert conn is not None

        # Second call should return same connection (cached)
        conn2 = manager.get_connection()
        assert conn is conn2

    def test_thread_local_connections(self, temp_db):
        """Test that different threads get different connections."""
        from functions.db.connection import DuckDBManager

        manager = DuckDBManager(
            db_path=temp_db["db_path"],
            schema_path=temp_db["schema_path"],
        )

        connections = []

        def get_conn_in_thread():
            conn = manager.get_connection()
            connections.append(conn)

        # Main thread connection
        main_conn = manager.get_connection()
        connections.append(main_conn)

        # Start another thread
        thread = Thread(target=get_conn_in_thread)
        thread.start()
        thread.join()

        # Connections should be different objects
        assert connections[0] is not connections[1]

    def test_context_manager(self, temp_db):
        """Test using manager as context manager."""
        from functions.db.connection import DuckDBManager

        manager = DuckDBManager(
            db_path=temp_db["db_path"],
            schema_path=temp_db["schema_path"],
        )

        with manager as conn:
            assert conn is not None

    def test_connection_context_manager(self, temp_db):
        """Test connection() context manager method."""
        from functions.db.connection import DuckDBManager

        manager = DuckDBManager(
            db_path=temp_db["db_path"],
            schema_path=temp_db["schema_path"],
        )

        with manager.connection() as conn:
            assert conn is not None

    def test_initialize_schema(self, temp_db):
        """Test schema initialization."""
        from functions.db.connection import DuckDBManager

        manager = DuckDBManager(
            db_path=temp_db["db_path"],
            schema_path=temp_db["schema_path"],
        )

        # Should not raise
        manager.initialize(ignore_exists=True)

        # Verify table was created
        result = manager.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
        tables = result.fetchall()
        assert len(tables) > 0

    def test_initialize_schema_file_not_found(self, temp_db):
        """Test schema initialization with missing file."""
        from functions.db.connection import DuckDBManager

        manager = DuckDBManager(
            db_path=temp_db["db_path"],
            schema_path=Path("/nonexistent/schema.sql"),
        )

        with pytest.raises(FileNotFoundError):
            manager.initialize()

    def test_execute_select(self, temp_db):
        """Test SELECT query execution."""
        from functions.db.connection import DuckDBManager

        manager = DuckDBManager(
            db_path=temp_db["db_path"],
            schema_path=temp_db["schema_path"],
        )
        manager.initialize(ignore_exists=True)

        # Insert test data
        manager.execute_insert(
            "INSERT INTO test_table (id, name, value) VALUES (?, ?, ?)",
            [1, "test", 100.50],
        )

        # Execute SELECT
        result = manager.execute("SELECT * FROM test_table WHERE id = ?", [1])
        rows = result.fetchall()

        assert len(rows) == 1
        assert rows[0][0] == 1
        assert rows[0][1] == "test"

    def test_execute_one(self, temp_db):
        """Test single-row query execution."""
        from functions.db.connection import DuckDBManager

        manager = DuckDBManager(
            db_path=temp_db["db_path"],
            schema_path=temp_db["schema_path"],
        )
        manager.initialize(ignore_exists=True)

        # Insert test data
        manager.execute_insert(
            "INSERT INTO test_table (id, name, value) VALUES (?, ?, ?)",
            [2, "single", 200.75],
        )

        # Execute single-row query
        row = manager.execute_one("SELECT * FROM test_table WHERE id = ?", [2])

        assert row is not None
        assert row[0] == 2
        assert row[1] == "single"

    def test_execute_one_no_results(self, temp_db):
        """Test single-row query with no results."""
        from functions.db.connection import DuckDBManager

        manager = DuckDBManager(
            db_path=temp_db["db_path"],
            schema_path=temp_db["schema_path"],
        )
        manager.initialize(ignore_exists=True)

        # Query non-existent row
        row = manager.execute_one("SELECT * FROM test_table WHERE id = ?", [999])

        assert row is None

    def test_execute_insert(self, temp_db):
        """Test INSERT query execution."""
        from functions.db.connection import DuckDBManager

        manager = DuckDBManager(
            db_path=temp_db["db_path"],
            schema_path=temp_db["schema_path"],
        )
        manager.initialize(ignore_exists=True)

        # Insert data
        rows = manager.execute_insert(
            "INSERT INTO test_table (id, name, value) VALUES (?, ?, ?)",
            [3, "insert", 300.99],
        )

        assert rows >= 0  # DuckDB may return 0 or actual count

        # Verify data was inserted
        row = manager.execute_one("SELECT * FROM test_table WHERE id = ?", [3])
        assert row is not None
        assert row[1] == "insert"

    def test_execute_insert_multiple(self, temp_db):
        """Test multiple INSERT operations."""
        from functions.db.connection import DuckDBManager

        manager = DuckDBManager(
            db_path=temp_db["db_path"],
            schema_path=temp_db["schema_path"],
        )
        manager.initialize(ignore_exists=True)

        # Insert multiple rows
        for i in range(5):
            manager.execute_insert(
                "INSERT INTO test_table (id, name, value) VALUES (?, ?, ?)",
                [i, f"test_{i}", float(i) * 100],
            )

        # Verify all inserted
        result = manager.execute("SELECT COUNT(*) FROM test_table")
        count = result.fetchone()[0]
        assert count >= 5

    def test_close_connection(self, temp_db):
        """Test closing connection."""
        from functions.db.connection import DuckDBManager

        manager = DuckDBManager(
            db_path=temp_db["db_path"],
            schema_path=temp_db["schema_path"],
        )

        conn = manager.get_connection()
        manager.close_connection()

        # Getting connection after close should create a new one
        conn2 = manager.get_connection()
        assert conn2 is not None


class TestGlobalSingleton:
    """Tests for global singleton functions."""

    def test_init_db_default_paths(self, temp_db):
        """Test init_db with default paths."""
        from functions.db.connection import init_db, reset_db, get_db

        try:
            # Override default paths for testing
            db_manager = init_db(
                db_path=temp_db["db_path"],
                schema_path=temp_db["schema_path"],
                auto_initialize=True,
            )

            assert db_manager is not None

            # get_db should now work
            db = get_db()
            assert db is db_manager

        finally:
            reset_db()

    def test_get_db_before_init_raises(self):
        """Test that get_db() raises if not initialized."""
        from functions.db.connection import get_db, reset_db

        reset_db()

        with pytest.raises(RuntimeError, match="not initialized"):
            get_db()

    def test_close_db(self, temp_db):
        """Test close_db function."""
        from functions.db.connection import init_db, close_db, reset_db

        try:
            init_db(
                db_path=temp_db["db_path"],
                schema_path=temp_db["schema_path"],
                auto_initialize=False,
            )

            # Should not raise
            close_db()

        finally:
            reset_db()

    def test_reset_db(self, temp_db):
        """Test reset_db function."""
        from functions.db.connection import init_db, reset_db, get_db

        init_db(
            db_path=temp_db["db_path"],
            schema_path=temp_db["schema_path"],
            auto_initialize=False,
        )

        reset_db()

        # After reset, get_db should raise
        with pytest.raises(RuntimeError):
            get_db()


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_sql_query(self, temp_db):
        """Test handling of invalid SQL."""
        from functions.db.connection import DuckDBManager

        manager = DuckDBManager(
            db_path=temp_db["db_path"],
            schema_path=temp_db["schema_path"],
        )
        manager.initialize(ignore_exists=True)

        with pytest.raises(RuntimeError):
            manager.execute("INVALID SQL SYNTAX")

    def test_execute_insert_with_no_commit(self, temp_db):
        """Test execute_insert with commit=False."""
        from functions.db.connection import DuckDBManager

        manager = DuckDBManager(
            db_path=temp_db["db_path"],
            schema_path=temp_db["schema_path"],
        )
        manager.initialize(ignore_exists=True)

        # Insert without commit
        manager.execute_insert(
            "INSERT INTO test_table (id, name, value) VALUES (?, ?, ?)",
            [10, "nocommit", 10.0],
            commit=False,
        )

        # Data should still be available in same connection
        row = manager.execute_one("SELECT * FROM test_table WHERE id = ?", [10])
        assert row is not None


class TestDocstringExamples:
    """Test examples from docstrings."""

    def test_basic_usage_example(self, temp_db):
        """Test basic usage from module docstring."""
        from functions.db.connection import DuckDBManager

        # Example from docstring
        manager = DuckDBManager(
            db_path=temp_db["db_path"],
            schema_path=temp_db["schema_path"],
        )
        manager.initialize(ignore_exists=True)

        # Insert test data
        manager.execute_insert(
            "INSERT INTO test_table (id, name, value) VALUES (?, ?, ?)",
            [100, "example", 1000.00],
        )

        result = manager.execute_one(
            "SELECT * FROM test_table WHERE id = ?",
            [100],
        )

        assert result is not None

    def test_context_manager_example(self, temp_db):
        """Test context manager example from docstring."""
        from functions.db.connection import DuckDBManager

        manager = DuckDBManager(
            db_path=temp_db["db_path"],
            schema_path=temp_db["schema_path"],
        )
        manager.initialize(ignore_exists=True)

        # Example from docstring
        with manager.connection() as conn:
            result = conn.execute("SELECT COUNT(*) FROM test_table").fetchone()
            assert result is not None
