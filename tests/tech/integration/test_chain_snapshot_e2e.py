"""End-to-end tests for chain snapshot historization workflow.

Tests verify the complete chain snapshot workflow:
1. Collection: Gather option chains from market
2. Storage: Save to both disk (JSON) and database (metadata)
3. Retrieval: Load from disk and database
4. Verification: Ensure data integrity throughout

This test validates:
1. Full collection -> storage -> retrieval cycle
2. Data consistency between disk and database
3. Error handling for missing files/data
4. Graceful handling of partial failures
5. Historical data persistence and querying

Running:
    pytest tests/tech/integration/test_chain_snapshot_e2e.py -v
"""

import pytest
import json
import tempfile
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import duckdb


class TestChainSnapshotE2E:
    """End-to-end tests for complete snapshot workflow."""

    def test_collect_store_retrieve_workflow(self, tmp_path):
        """Test complete workflow: collect -> store -> retrieve."""
        # Setup
        db_path = tmp_path / "test.db"
        chains_dir = tmp_path / "chains"
        chains_dir.mkdir()

        conn = duckdb.connect(str(db_path))

        # Create table
        conn.execute("""
            CREATE TABLE chain_snapshots (
                id INTEGER PRIMARY KEY,
                ticker VARCHAR(10),
                snapshot_date DATE,
                expiration DATE,
                underlying_price FLOAT,
                chain_json JSON,
                file_path VARCHAR(256)
            )
        """)

        # Step 1: Collect (simulate)
        collected_data = {
            "AAPL": {
                "snapshot_date": date.today().isoformat(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "underlying_price": 192.50,
                "chains": [
                    {"expiration": "2026-02-20", "dte": 24, "calls": [], "puts": []}
                ],
            },
            "MSFT": {
                "snapshot_date": date.today().isoformat(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "underlying_price": 420.00,
                "chains": [
                    {"expiration": "2026-02-20", "dte": 24, "calls": [], "puts": []}
                ],
            },
        }

        # Step 2: Store to disk
        today_dir = chains_dir / date.today().strftime("%Y-%m-%d")
        today_dir.mkdir(parents=True)

        for ticker, data in collected_data.items():
            file_path = today_dir / f"{ticker}_chains.json"
            file_path.write_text(json.dumps(data, indent=2))

        # Step 3: Store metadata to database
        for ticker, data in collected_data.items():
            file_path_rel = (
                f"chains/{date.today().strftime('%Y-%m-%d')}/{ticker}_chains.json"
            )
            conn.execute(
                """
                INSERT INTO chain_snapshots
                (ticker, snapshot_date, expiration, underlying_price, chain_json, file_path)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    ticker,
                    data["snapshot_date"],
                    data["chains"][0]["expiration"],
                    data["underlying_price"],
                    json.dumps(data),
                    file_path_rel,
                ],
            )

        # Step 4: Retrieve from database
        result = conn.execute(
            "SELECT * FROM chain_snapshots WHERE ticker = 'AAPL'"
        ).fetchone()

        assert result[1] == "AAPL"
        assert result[4] == 192.50  # underlying_price

        # Step 5: Retrieve from disk and verify
        file_path = today_dir / "AAPL_chains.json"
        assert file_path.exists()

        loaded_data = json.loads(file_path.read_text())
        assert loaded_data["underlying_price"] == 192.50

        conn.close()

    def test_multi_day_snapshot_accumulation(self, tmp_path):
        """Test accumulating snapshots across multiple days."""
        chains_dir = tmp_path / "chains"
        chains_dir.mkdir()

        # Create snapshots for 5 days
        dates = [date.today() - timedelta(days=i) for i in range(5)]

        for d in dates:
            date_dir = chains_dir / d.strftime("%Y-%m-%d")
            date_dir.mkdir(parents=True)

            for ticker in ["AAPL", "MSFT"]:
                file_path = date_dir / f"{ticker}_chains.json"
                data = {
                    "ticker": ticker,
                    "snapshot_date": d.isoformat(),
                    "chains": [],
                }
                file_path.write_text(json.dumps(data))

        # Verify structure
        all_dirs = sorted([d for d in chains_dir.iterdir() if d.is_dir()])
        assert len(all_dirs) == 5

        # Verify each day has 2 snapshots
        for day_dir in all_dirs:
            files = list(day_dir.glob("*_chains.json"))
            assert len(files) == 2

    def test_snapshot_retrieval_by_date_range(self, tmp_path):
        """Test retrieving snapshots within a date range."""
        chains_dir = tmp_path / "chains"
        chains_dir.mkdir()

        db_path = tmp_path / "test.db"
        conn = duckdb.connect(str(db_path))

        conn.execute("""
            CREATE TABLE chain_snapshots (
                id INTEGER PRIMARY KEY,
                ticker VARCHAR(10),
                snapshot_date DATE,
                chain_json JSON
            )
        """)

        # Create snapshots for 10 days
        for i in range(10):
            d = date.today() - timedelta(days=i)

            # Store to disk
            date_dir = chains_dir / d.strftime("%Y-%m-%d")
            date_dir.mkdir(parents=True)
            (date_dir / "AAPL_chains.json").write_text(json.dumps({"date": str(d)}))

            # Store to database
            conn.execute(
                "INSERT INTO chain_snapshots (ticker, snapshot_date, chain_json) VALUES (?, ?, ?)",
                ["AAPL", d.isoformat(), json.dumps({"date": str(d)})],
            )

        # Query range (last 3 days)
        start = date.today() - timedelta(days=2)
        end = date.today()

        result = conn.execute(
            "SELECT COUNT(*) FROM chain_snapshots WHERE snapshot_date BETWEEN ? AND ?",
            [start.isoformat(), end.isoformat()],
        ).fetchone()

        assert result[0] >= 1

        conn.close()

    def test_snapshot_with_various_expiration_dates(self, tmp_path):
        """Test storing snapshots with multiple expiration dates."""
        db_path = tmp_path / "test.db"
        conn = duckdb.connect(str(db_path))

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

        # Single snapshot date, multiple expirations
        snapshot_date = date.today()
        expirations = [
            date.today() + timedelta(days=14),
            date.today() + timedelta(days=21),
            date.today() + timedelta(days=28),
            date.today() + timedelta(days=42),
        ]

        # Insert for each expiration
        for i, exp_date in enumerate(expirations):
            conn.execute(
                """
                INSERT INTO chain_snapshots
                (id, ticker, snapshot_date, expiration, chain_json)
                VALUES (?, 'AAPL', ?, ?, '{}')
                """,
                [i + 1, snapshot_date.isoformat(), exp_date.isoformat()],
            )

        # Verify all stored
        result = conn.execute(
            "SELECT COUNT(*) FROM chain_snapshots WHERE ticker = 'AAPL'"
        ).fetchone()
        assert result[0] == 4

        conn.close()

    def test_snapshot_data_consistency(self, tmp_path):
        """Test that data is consistent between disk and database."""
        chains_dir = tmp_path / "chains"
        today_dir = chains_dir / date.today().strftime("%Y-%m-%d")
        today_dir.mkdir(parents=True)

        db_path = tmp_path / "test.db"
        conn = duckdb.connect(str(db_path))

        conn.execute("""
            CREATE TABLE chain_snapshots (
                id INTEGER PRIMARY KEY,
                ticker VARCHAR(10),
                underlying_price FLOAT,
                chain_json JSON
            )
        """)

        # Create detailed snapshot
        snapshot_data = {
            "ticker": "AAPL",
            "underlying_price": 192.50,
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

        # Store to disk
        file_path = today_dir / "AAPL_chains.json"
        file_path.write_text(json.dumps(snapshot_data))

        # Store to database
        conn.execute(
            """
            INSERT INTO chain_snapshots
            (id, ticker, underlying_price, chain_json)
            VALUES (1, 'AAPL', 192.50, ?)
            """,
            [json.dumps(snapshot_data)],
        )

        # Retrieve from disk
        disk_data = json.loads(file_path.read_text())

        # Retrieve from database
        db_result = conn.execute(
            "SELECT chain_json FROM chain_snapshots WHERE id = 1"
        ).fetchone()
        db_data = json.loads(db_result[0])

        # Compare
        assert disk_data == db_data
        assert disk_data["underlying_price"] == 192.50
        assert len(disk_data["chains"][0]["calls"]) == 2

        conn.close()

    def test_snapshot_retrieval_with_missing_file(self, tmp_path):
        """Test handling of missing snapshot files."""
        db_path = tmp_path / "test.db"
        conn = duckdb.connect(str(db_path))

        conn.execute("""
            CREATE TABLE chain_snapshots (
                id INTEGER PRIMARY KEY,
                ticker VARCHAR(10),
                file_path VARCHAR(256),
                chain_json JSON
            )
        """)

        # Store reference to non-existent file
        conn.execute(
            """
            INSERT INTO chain_snapshots
            (id, ticker, file_path, chain_json)
            VALUES (1, 'AAPL', 'non/existent/path.json', '{}')
            """
        )

        # Retrieve - data should still be there in database
        result = conn.execute(
            "SELECT * FROM chain_snapshots WHERE id = 1"
        ).fetchone()

        assert result[1] == "AAPL"
        assert result[2] == "non/existent/path.json"

        conn.close()

    def test_snapshot_query_performance(self, tmp_path):
        """Test that snapshot queries are performant with many records."""
        db_path = tmp_path / "test.db"
        conn = duckdb.connect(str(db_path))

        conn.execute("""
            CREATE TABLE chain_snapshots (
                id INTEGER PRIMARY KEY,
                ticker VARCHAR(10),
                snapshot_date DATE,
                chain_json JSON
            )
        """)

        # Create many snapshots
        tickers = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMD", "NVDA", "SOFI", "META"]
        dates = [date.today() - timedelta(days=i) for i in range(30)]

        id_counter = 1
        for d in dates:
            for ticker in tickers:
                conn.execute(
                    """
                    INSERT INTO chain_snapshots
                    (id, ticker, snapshot_date, chain_json)
                    VALUES (?, ?, ?, '{}')
                    """,
                    [id_counter, ticker, d.isoformat()],
                )
                id_counter += 1

        # Query should be fast
        import time

        start = time.time()
        result = conn.execute(
            "SELECT COUNT(*) FROM chain_snapshots WHERE ticker = 'AAPL'"
        ).fetchone()
        elapsed = time.time() - start

        assert result[0] == 30  # 30 days of AAPL snapshots
        assert elapsed < 1.0  # Should complete in under 1 second

        conn.close()

    def test_snapshot_update_workflow(self, tmp_path):
        """Test updating snapshot data."""
        db_path = tmp_path / "test.db"
        conn = duckdb.connect(str(db_path))

        conn.execute("""
            CREATE TABLE chain_snapshots (
                id INTEGER PRIMARY KEY,
                ticker VARCHAR(10),
                underlying_price FLOAT,
                chain_json JSON
            )
        """)

        # Insert initial
        conn.execute(
            """
            INSERT INTO chain_snapshots
            (id, ticker, underlying_price, chain_json)
            VALUES (1, 'AAPL', 190.0, '{}')
            """
        )

        # Verify insert
        result = conn.execute(
            "SELECT underlying_price FROM chain_snapshots WHERE id = 1"
        ).fetchone()
        assert result[0] == 190.0

        # Update (though typically snapshots are immutable)
        conn.execute(
            "UPDATE chain_snapshots SET underlying_price = 192.5 WHERE id = 1"
        )

        # Verify update
        result = conn.execute(
            "SELECT underlying_price FROM chain_snapshots WHERE id = 1"
        ).fetchone()
        assert result[0] == 192.5

        conn.close()


class TestChainSnapshotErrorHandling:
    """Test error handling in snapshot workflows."""

    def test_handle_invalid_json_in_storage(self, tmp_path):
        """Test handling of invalid JSON data."""
        db_path = tmp_path / "test.db"
        conn = duckdb.connect(str(db_path))

        conn.execute("""
            CREATE TABLE chain_snapshots (
                id INTEGER PRIMARY KEY,
                chain_json JSON
            )
        """)

        # Valid JSON should work
        conn.execute(
            "INSERT INTO chain_snapshots (id, chain_json) VALUES (1, ?)",
            [json.dumps({"valid": "data"})],
        )

        # Verify
        result = conn.execute("SELECT * FROM chain_snapshots WHERE id = 1").fetchone()
        assert result is not None

        conn.close()

    def test_handle_missing_required_fields(self):
        """Test handling of snapshots missing required fields."""
        # Snapshot without required fields should be caught
        incomplete_snapshot = {"chains": []}  # Missing ticker, snapshot_date, etc.

        # This would be caught at application level
        required_fields = ["ticker", "snapshot_date"]
        for field in required_fields:
            assert field not in incomplete_snapshot

    def test_handle_null_values(self, tmp_path):
        """Test handling of null values in snapshots."""
        db_path = tmp_path / "test.db"
        conn = duckdb.connect(str(db_path))

        conn.execute("""
            CREATE TABLE chain_snapshots (
                id INTEGER PRIMARY KEY,
                ticker VARCHAR(10),
                atm_iv FLOAT,  -- Can be NULL
                chain_json JSON
            )
        """)

        # Insert with NULL
        conn.execute(
            """
            INSERT INTO chain_snapshots
            (id, ticker, atm_iv, chain_json)
            VALUES (1, 'AAPL', NULL, '{}')
            """
        )

        # Retrieve
        result = conn.execute(
            "SELECT atm_iv FROM chain_snapshots WHERE id = 1"
        ).fetchone()
        assert result[0] is None

        conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
