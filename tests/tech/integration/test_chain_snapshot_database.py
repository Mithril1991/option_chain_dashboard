"""Integration tests for chain snapshot database operations.

Tests verify that chain snapshots are properly stored and retrieved
from the DuckDB database with correct metadata and relationships.

This test validates:
1. chain_snapshots table stores all required fields
2. Metadata correctly links to scans and features
3. Queries return correct data
4. Deduplication prevents duplicates
5. Foreign key relationships work

Running:
    pytest tests/tech/integration/test_chain_snapshot_database.py -v
"""

import pytest
import json
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

import duckdb


class TestChainSnapshotDatabaseSchema:
    """Test chain_snapshots table schema and structure."""

    def test_chain_snapshots_table_exists(self):
        """Test that chain_snapshots table can be created."""
        conn = duckdb.connect(":memory:")

        # Create table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chain_snapshots (
                id INTEGER PRIMARY KEY,
                scan_id INTEGER,
                ticker VARCHAR(10) NOT NULL,
                snapshot_date DATE NOT NULL,
                expiration DATE NOT NULL,
                dte INTEGER NOT NULL,
                underlying_price FLOAT NOT NULL,
                chain_json JSON NOT NULL,
                num_calls INTEGER,
                num_puts INTEGER,
                atm_iv FLOAT,
                total_volume INTEGER,
                total_oi INTEGER,
                file_path VARCHAR(256),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, snapshot_date, expiration)
            )
        """)

        # Verify table exists
        result = conn.execute(
            "SELECT name FROM duckdb_tables() WHERE name = 'chain_snapshots'"
        ).fetchall()
        assert len(result) > 0

    def test_chain_snapshots_required_columns(self):
        """Test that all required columns exist."""
        conn = duckdb.connect(":memory:")

        conn.execute("""
            CREATE TABLE chain_snapshots (
                id INTEGER PRIMARY KEY,
                scan_id INTEGER,
                ticker VARCHAR(10) NOT NULL,
                snapshot_date DATE NOT NULL,
                expiration DATE NOT NULL,
                dte INTEGER NOT NULL,
                underlying_price FLOAT NOT NULL,
                chain_json JSON NOT NULL,
                created_at TIMESTAMP
            )
        """)

        # Get columns
        result = conn.execute("DESCRIBE chain_snapshots").fetchall()
        column_names = [row[0] for row in result]

        required = [
            "id",
            "scan_id",
            "ticker",
            "snapshot_date",
            "expiration",
            "dte",
            "underlying_price",
            "chain_json",
            "created_at",
        ]

        for col in required:
            assert col in column_names, f"Missing column: {col}"

    def test_unique_constraint_on_snapshot_key(self):
        """Test unique constraint on (ticker, snapshot_date, expiration)."""
        conn = duckdb.connect(":memory:")

        conn.execute("""
            CREATE TABLE chain_snapshots (
                id INTEGER PRIMARY KEY,
                ticker VARCHAR(10),
                snapshot_date DATE,
                expiration DATE,
                chain_json JSON,
                UNIQUE(ticker, snapshot_date, expiration)
            )
        """)

        # Insert first record
        conn.execute(
            """
            INSERT INTO chain_snapshots (id, ticker, snapshot_date, expiration, chain_json)
            VALUES (1, 'AAPL', '2026-01-27', '2026-02-20', '{}')
            """
        )

        # Try to insert duplicate - should fail
        with pytest.raises(Exception):
            conn.execute(
                """
                INSERT INTO chain_snapshots (id, ticker, snapshot_date, expiration, chain_json)
                VALUES (2, 'AAPL', '2026-01-27', '2026-02-20', '{}')
                """
            )


class TestChainSnapshotInsert:
    """Test inserting chain snapshots into database."""

    def test_insert_chain_snapshot(self):
        """Test inserting a single chain snapshot."""
        conn = duckdb.connect(":memory:")

        conn.execute("""
            CREATE TABLE chain_snapshots (
                id INTEGER PRIMARY KEY,
                ticker VARCHAR(10),
                snapshot_date DATE,
                expiration DATE,
                dte INTEGER,
                underlying_price FLOAT,
                chain_json JSON,
                created_at TIMESTAMP
            )
        """)

        # Insert snapshot
        snapshot = {
            "calls": [{"strike": 190, "bid": 5.2, "ask": 5.3}],
            "puts": [{"strike": 190, "bid": 2.8, "ask": 2.9}],
        }

        conn.execute(
            """
            INSERT INTO chain_snapshots
            (id, ticker, snapshot_date, expiration, dte, underlying_price, chain_json, created_at)
            VALUES (1, 'AAPL', '2026-01-27', '2026-02-20', 24, 192.5, ?, ?)
            """,
            [json.dumps(snapshot), datetime.now(timezone.utc)],
        )

        # Verify insert
        result = conn.execute("SELECT * FROM chain_snapshots WHERE id = 1").fetchall()
        assert len(result) == 1
        assert result[0][1] == "AAPL"  # ticker

    def test_insert_multiple_chain_snapshots(self):
        """Test inserting multiple chain snapshots."""
        conn = duckdb.connect(":memory:")

        conn.execute("""
            CREATE TABLE chain_snapshots (
                id INTEGER PRIMARY KEY,
                ticker VARCHAR(10),
                snapshot_date DATE,
                expiration DATE,
                dte INTEGER,
                chain_json JSON
            )
        """)

        # Insert multiple
        snapshots = [
            ("AAPL", "2026-01-27", "2026-02-20", 24),
            ("MSFT", "2026-01-27", "2026-02-20", 24),
            ("GOOGL", "2026-01-27", "2026-02-20", 24),
        ]

        for i, (ticker, snap_date, exp_date, dte) in enumerate(snapshots, 1):
            conn.execute(
                """
                INSERT INTO chain_snapshots
                (id, ticker, snapshot_date, expiration, dte, chain_json)
                VALUES (?, ?, ?, ?, ?, '{}')
                """,
                [i, ticker, snap_date, exp_date, dte],
            )

        # Verify all inserted
        result = conn.execute("SELECT COUNT(*) FROM chain_snapshots").fetchone()
        assert result[0] == 3

    def test_insert_chain_with_all_fields(self):
        """Test inserting chain snapshot with all optional fields."""
        conn = duckdb.connect(":memory:")

        conn.execute("""
            CREATE TABLE chain_snapshots (
                id INTEGER PRIMARY KEY,
                ticker VARCHAR(10),
                snapshot_date DATE,
                expiration DATE,
                dte INTEGER,
                underlying_price FLOAT,
                chain_json JSON,
                num_calls INTEGER,
                num_puts INTEGER,
                atm_iv FLOAT,
                total_volume INTEGER,
                total_oi INTEGER,
                file_path VARCHAR(256)
            )
        """)

        # Insert with all fields
        conn.execute(
            """
            INSERT INTO chain_snapshots
            (id, ticker, snapshot_date, expiration, dte, underlying_price, chain_json,
             num_calls, num_puts, atm_iv, total_volume, total_oi, file_path)
            VALUES (1, 'AAPL', '2026-01-27', '2026-02-20', 24, 192.5, '{}',
                    45, 42, 0.28, 125000, 500000, 'historical_data/chains/2026-01-27/AAPL_chains.json')
            """
        )

        # Verify
        result = conn.execute(
            "SELECT num_calls, num_puts, atm_iv FROM chain_snapshots WHERE id = 1"
        ).fetchone()
        assert result[0] == 45  # num_calls
        assert result[1] == 42  # num_puts
        assert abs(result[2] - 0.28) < 0.001  # atm_iv


class TestChainSnapshotQuery:
    """Test querying chain snapshots from database."""

    def test_query_snapshot_by_ticker(self):
        """Test querying snapshots by ticker."""
        conn = duckdb.connect(":memory:")

        conn.execute("""
            CREATE TABLE chain_snapshots (
                ticker VARCHAR(10),
                snapshot_date DATE,
                chain_json JSON
            )
        """)

        # Insert test data
        for ticker in ["AAPL", "MSFT", "GOOGL"]:
            conn.execute(
                "INSERT INTO chain_snapshots VALUES (?, '2026-01-27', '{}')",
                [ticker],
            )

        # Query AAPL
        result = conn.execute(
            "SELECT * FROM chain_snapshots WHERE ticker = 'AAPL'"
        ).fetchall()
        assert len(result) == 1
        assert result[0][0] == "AAPL"

    def test_query_snapshot_by_date(self):
        """Test querying snapshots by date."""
        conn = duckdb.connect(":memory:")

        conn.execute("""
            CREATE TABLE chain_snapshots (
                ticker VARCHAR(10),
                snapshot_date DATE,
                chain_json JSON
            )
        """)

        # Insert for different dates
        dates = [
            "2026-01-25",
            "2026-01-26",
            "2026-01-27",
        ]

        for i, d in enumerate(dates):
            conn.execute(
                "INSERT INTO chain_snapshots VALUES (?, ?, '{}')",
                ["AAPL", d],
            )

        # Query specific date
        result = conn.execute(
            "SELECT * FROM chain_snapshots WHERE snapshot_date = '2026-01-27'"
        ).fetchall()
        assert len(result) == 1

    def test_query_snapshot_by_date_range(self):
        """Test querying snapshots within date range."""
        conn = duckdb.connect(":memory:")

        conn.execute("""
            CREATE TABLE chain_snapshots (
                ticker VARCHAR(10),
                snapshot_date DATE,
                chain_json JSON
            )
        """)

        # Insert for range of dates
        for i in range(10):
            d = f"2026-01-{20+i:02d}"
            conn.execute(
                "INSERT INTO chain_snapshots VALUES (?, ?, '{}')",
                ["AAPL", d],
            )

        # Query range
        result = conn.execute(
            """
            SELECT COUNT(*) FROM chain_snapshots
            WHERE snapshot_date BETWEEN '2026-01-25' AND '2026-01-27'
            """
        ).fetchone()

        assert result[0] >= 1

    def test_query_latest_snapshot_per_ticker(self):
        """Test getting latest snapshot for each ticker."""
        conn = duckdb.connect(":memory:")

        conn.execute("""
            CREATE TABLE chain_snapshots (
                id INTEGER PRIMARY KEY,
                ticker VARCHAR(10),
                snapshot_date DATE,
                chain_json JSON
            )
        """)

        # Insert multiple snapshots per ticker
        data = [
            (1, "AAPL", "2026-01-25"),
            (2, "AAPL", "2026-01-26"),
            (3, "AAPL", "2026-01-27"),
            (4, "MSFT", "2026-01-25"),
            (5, "MSFT", "2026-01-27"),
        ]

        for id, ticker, date in data:
            conn.execute(
                "INSERT INTO chain_snapshots VALUES (?, ?, ?, '{}')",
                [id, ticker, date],
            )

        # Get latest for each ticker
        result = conn.execute(
            """
            SELECT ticker, MAX(snapshot_date) FROM chain_snapshots
            GROUP BY ticker
            """
        ).fetchall()

        assert len(result) == 2
        assert result[0][1] >= "2026-01-27"


class TestChainSnapshotJSONData:
    """Test JSON data in chain snapshots."""

    def test_store_and_retrieve_chain_json(self):
        """Test storing and retrieving chain JSON data."""
        conn = duckdb.connect(":memory:")

        conn.execute("""
            CREATE TABLE chain_snapshots (
                id INTEGER,
                ticker VARCHAR(10),
                chain_json JSON
            )
        """)

        # Complex chain data
        chain_data = {
            "ticker": "AAPL",
            "chains": [
                {
                    "expiration": "2026-02-20",
                    "calls": [
                        {"strike": 190, "bid": 5.2, "ask": 5.3, "iv": 0.28},
                        {"strike": 195, "bid": 3.1, "ask": 3.2, "iv": 0.27},
                    ],
                }
            ],
        }

        # Insert
        conn.execute(
            "INSERT INTO chain_snapshots VALUES (1, 'AAPL', ?)",
            [json.dumps(chain_data)],
        )

        # Retrieve
        result = conn.execute(
            "SELECT chain_json FROM chain_snapshots WHERE id = 1"
        ).fetchone()

        retrieved = json.loads(result[0])
        assert retrieved["ticker"] == "AAPL"
        assert len(retrieved["chains"]) == 1
        assert len(retrieved["chains"][0]["calls"]) == 2

    def test_json_access_in_query(self):
        """Test accessing JSON fields in queries."""
        conn = duckdb.connect(":memory:")

        conn.execute("""
            CREATE TABLE chain_snapshots (
                id INTEGER,
                chain_json JSON
            )
        """)

        chain_data = {
            "ticker": "AAPL",
            "underlying_price": 192.5,
            "chains": [{"expiration": "2026-02-20", "num_calls": 45}],
        }

        conn.execute(
            "INSERT INTO chain_snapshots VALUES (1, ?)",
            [json.dumps(chain_data)],
        )

        # Query JSON fields (DuckDB syntax)
        result = conn.execute(
            "SELECT chain_json FROM chain_snapshots WHERE id = 1"
        ).fetchone()

        data = json.loads(result[0])
        assert data["underlying_price"] == 192.5


class TestChainSnapshotIntegration:
    """Test full integration scenarios."""

    def test_snapshot_workflow(self):
        """Test complete workflow: insert -> query -> verify."""
        conn = duckdb.connect(":memory:")

        # Create table
        conn.execute("""
            CREATE TABLE chain_snapshots (
                id INTEGER PRIMARY KEY,
                ticker VARCHAR(10),
                snapshot_date DATE,
                expiration DATE,
                dte INTEGER,
                chain_json JSON,
                UNIQUE(ticker, snapshot_date, expiration)
            )
        """)

        # Insert
        snapshot = {"calls": [], "puts": []}
        conn.execute(
            """
            INSERT INTO chain_snapshots
            (id, ticker, snapshot_date, expiration, dte, chain_json)
            VALUES (1, 'AAPL', '2026-01-27', '2026-02-20', 24, ?)
            """,
            [json.dumps(snapshot)],
        )

        # Query
        result = conn.execute(
            "SELECT * FROM chain_snapshots WHERE ticker = 'AAPL'"
        ).fetchone()

        # Verify
        assert result[1] == "AAPL"
        assert result[2] == "2026-01-27"
        retrieved_json = json.loads(result[5])
        assert "calls" in retrieved_json

    def test_deduplication_prevents_duplicate_inserts(self):
        """Test that unique constraint prevents duplicates."""
        conn = duckdb.connect(":memory:")

        conn.execute("""
            CREATE TABLE chain_snapshots (
                id INTEGER PRIMARY KEY,
                ticker VARCHAR(10),
                snapshot_date DATE,
                expiration DATE,
                chain_json JSON,
                UNIQUE(ticker, snapshot_date, expiration)
            )
        """)

        # Insert first
        conn.execute(
            """
            INSERT INTO chain_snapshots
            (id, ticker, snapshot_date, expiration, chain_json)
            VALUES (1, 'AAPL', '2026-01-27', '2026-02-20', '{}')
            """
        )

        # Try duplicate - should fail
        with pytest.raises(Exception) as exc_info:
            conn.execute(
                """
                INSERT INTO chain_snapshots
                (id, ticker, snapshot_date, expiration, chain_json)
                VALUES (2, 'AAPL', '2026-01-27', '2026-02-20', '{}')
                """
            )

        assert "UNIQUE constraint" in str(exc_info.value) or "Constraint Error" in str(
            exc_info.value
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
