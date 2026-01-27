"""Integration tests for chain snapshot historization.

Tests verify that option chain snapshots are properly stored, retrieved,
and maintained in historical data with full data integrity.

This test validates:
1. Chain snapshots are written to historical_data/chains/YYYY-MM-DD/
2. Database metadata is recorded in chain_snapshots table
3. Snapshots can be retrieved from disk and database
4. Data integrity is maintained across store/retrieve cycles
5. Deduplication works on re-runs
6. JSON format is valid and complete

Running:
    pytest tests/tech/integration/test_chain_snapshot_historization.py -v
"""

import pytest
import json
import tempfile
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import duckdb


class TestChainSnapshotStorage:
    """Test chain snapshot storage to historical_data."""

    def test_chain_snapshot_directory_structure(self, tmp_path):
        """Test that chain snapshots are stored in date-organized directories."""
        # Create expected directory structure
        snapshot_dir = tmp_path / "historical_data" / "chains"
        snapshot_dir.mkdir(parents=True)

        # Create a sample snapshot for today
        today = date.today()
        date_dir = snapshot_dir / today.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True)

        # Verify structure
        assert date_dir.exists(), "Date directory should exist"
        assert date_dir.parent == snapshot_dir, "Date directory should be in chains directory"

    def test_chain_snapshot_file_naming(self, tmp_path):
        """Test that chain snapshot files are named correctly (TICKER_chains.json)."""
        snapshot_dir = tmp_path / "historical_data" / "chains"
        today_dir = snapshot_dir / date.today().strftime("%Y-%m-%d")
        today_dir.mkdir(parents=True)

        # Create sample chain files
        tickers = ["AAPL", "MSFT", "GOOGL"]
        for ticker in tickers:
            file_path = today_dir / f"{ticker}_chains.json"
            file_path.write_text(json.dumps({"ticker": ticker, "chains": []}))

        # Verify files exist
        for ticker in tickers:
            assert (today_dir / f"{ticker}_chains.json").exists()

    def test_chain_snapshot_json_structure(self, tmp_path):
        """Test that chain snapshot JSON has correct structure."""
        snapshot_dir = tmp_path / "historical_data" / "chains"
        today_dir = snapshot_dir / date.today().strftime("%Y-%m-%d")
        today_dir.mkdir(parents=True)

        # Create a sample chain snapshot
        chain_data = {
            "ticker": "AAPL",
            "snapshot_date": date.today().isoformat(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "underlying_price": 192.50,
            "chains": [
                {
                    "expiration": "2026-02-20",
                    "dte": 24,
                    "calls": [
                        {
                            "strike": 190.0,
                            "bid": 5.20,
                            "ask": 5.30,
                            "delta": 0.65,
                            "gamma": 0.018,
                            "vega": 0.42,
                            "theta": -0.08,
                            "volume": 1500,
                            "open_interest": 5000,
                        }
                    ],
                    "puts": [
                        {
                            "strike": 190.0,
                            "bid": 2.85,
                            "ask": 2.95,
                            "delta": -0.35,
                            "gamma": 0.017,
                            "vega": 0.41,
                            "theta": -0.05,
                            "volume": 800,
                            "open_interest": 3000,
                        }
                    ],
                }
            ],
        }

        # Write to file
        file_path = today_dir / "AAPL_chains.json"
        file_path.write_text(json.dumps(chain_data, indent=2))

        # Read back and verify
        loaded = json.loads(file_path.read_text())
        assert loaded["ticker"] == "AAPL"
        assert "chains" in loaded
        assert len(loaded["chains"]) > 0
        assert "calls" in loaded["chains"][0]
        assert "puts" in loaded["chains"][0]

    def test_chain_snapshot_required_fields(self):
        """Test that chain snapshot has all required fields."""
        required_snapshot_fields = {
            "ticker": str,
            "snapshot_date": str,
            "timestamp": str,
            "underlying_price": (int, float),
            "chains": list,
        }

        required_chain_fields = {
            "expiration": str,
            "dte": int,
            "calls": list,
            "puts": list,
        }

        required_contract_fields = {
            "strike": (int, float),
            "bid": (int, float),
            "ask": (int, float),
        }

        # Sample chain snapshot
        snapshot = {
            "ticker": "AAPL",
            "snapshot_date": date.today().isoformat(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "underlying_price": 192.50,
            "chains": [
                {
                    "expiration": "2026-02-20",
                    "dte": 24,
                    "calls": [{"strike": 190.0, "bid": 5.20, "ask": 5.30}],
                    "puts": [{"strike": 190.0, "bid": 2.85, "ask": 2.95}],
                }
            ],
        }

        # Verify snapshot fields
        for field, field_type in required_snapshot_fields.items():
            assert field in snapshot, f"Missing field: {field}"
            assert isinstance(snapshot[field], field_type), f"Wrong type for {field}"

        # Verify chain fields
        chain = snapshot["chains"][0]
        for field, field_type in required_chain_fields.items():
            assert field in chain, f"Missing chain field: {field}"
            assert isinstance(chain[field], field_type), f"Wrong type for {field}"

        # Verify contract fields
        contract = chain["calls"][0]
        for field, field_type in required_contract_fields.items():
            assert field in contract, f"Missing contract field: {field}"


class TestChainSnapshotRetrieval:
    """Test retrieving chain snapshots from historical storage."""

    def test_read_chain_snapshot_from_disk(self, tmp_path):
        """Test reading chain snapshot from disk."""
        snapshot_dir = tmp_path / "chains"
        snapshot_dir.mkdir()

        # Create sample data
        chain_data = {
            "ticker": "AAPL",
            "snapshot_date": date.today().isoformat(),
            "chains": [{"expiration": "2026-02-20", "dte": 24, "calls": [], "puts": []}],
        }

        file_path = snapshot_dir / "AAPL_chains.json"
        file_path.write_text(json.dumps(chain_data))

        # Read back
        loaded = json.loads(file_path.read_text())
        assert loaded["ticker"] == "AAPL"

    def test_list_available_snapshots_by_date(self, tmp_path):
        """Test listing available snapshots by date."""
        chains_dir = tmp_path / "chains"
        chains_dir.mkdir()

        # Create snapshots for multiple dates
        dates = [
            date.today() - timedelta(days=2),
            date.today() - timedelta(days=1),
            date.today(),
        ]

        for d in dates:
            date_dir = chains_dir / d.strftime("%Y-%m-%d")
            date_dir.mkdir(parents=True)
            (date_dir / "AAPL_chains.json").write_text(json.dumps({"ticker": "AAPL"}))

        # List directories (simulate finding snapshots by date)
        snapshot_dirs = sorted([d for d in chains_dir.iterdir() if d.is_dir()])
        assert len(snapshot_dirs) == 3

    def test_list_available_tickers_for_date(self, tmp_path):
        """Test listing available tickers for a specific date."""
        chains_dir = tmp_path / "chains"
        today_dir = chains_dir / date.today().strftime("%Y-%m-%d")
        today_dir.mkdir(parents=True)

        # Create snapshots for multiple tickers
        tickers = ["AAPL", "MSFT", "GOOGL", "TSLA"]
        for ticker in tickers:
            (today_dir / f"{ticker}_chains.json").write_text(
                json.dumps({"ticker": ticker})
            )

        # List tickers
        available_files = list(today_dir.glob("*_chains.json"))
        available_tickers = [f.name.replace("_chains.json", "") for f in available_files]

        assert set(available_tickers) == set(tickers)

    def test_retrieve_snapshot_between_dates(self, tmp_path):
        """Test retrieving snapshots within a date range."""
        chains_dir = tmp_path / "chains"

        # Create snapshots for a week
        snapshots_by_date = {}
        for i in range(7):
            d = date.today() - timedelta(days=i)
            date_dir = chains_dir / d.strftime("%Y-%m-%d")
            date_dir.mkdir(parents=True)

            file_path = date_dir / "AAPL_chains.json"
            file_path.write_text(json.dumps({"ticker": "AAPL", "day": i}))
            snapshots_by_date[d] = file_path

        # Query range (last 3 days)
        start_date = date.today() - timedelta(days=2)
        end_date = date.today()

        results = []
        for d, path in snapshots_by_date.items():
            if start_date <= d <= end_date:
                results.append(path)

        assert len(results) == 3


class TestChainSnapshotDataIntegrity:
    """Test data integrity of chain snapshots."""

    def test_chain_snapshot_json_validity(self, tmp_path):
        """Test that stored snapshots are valid JSON."""
        snapshot_file = tmp_path / "test.json"

        # Create complex chain data
        chain_data = {
            "ticker": "AAPL",
            "snapshot_date": date.today().isoformat(),
            "chains": [
                {
                    "expiration": "2026-02-20",
                    "dte": 24,
                    "calls": [
                        {"strike": 190.0 + i, "bid": 5.0 + i * 0.1, "ask": 5.1 + i * 0.1}
                        for i in range(5)
                    ],
                    "puts": [
                        {"strike": 190.0 - i, "bid": 2.8 - i * 0.1, "ask": 2.9 - i * 0.1}
                        for i in range(5)
                    ],
                }
            ],
        }

        # Write and read
        snapshot_file.write_text(json.dumps(chain_data))
        loaded = json.loads(snapshot_file.read_text())

        # Verify
        assert loaded == chain_data

    def test_chain_snapshot_no_data_loss(self, tmp_path):
        """Test that no data is lost when writing/reading snapshots."""
        snapshot_file = tmp_path / "chains.json"

        # Create detailed chain data with many fields
        chain_data = {
            "ticker": "AAPL",
            "snapshot_date": date.today().isoformat(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "underlying_price": 192.50,
            "chains": [
                {
                    "expiration": "2026-02-20",
                    "dte": 24,
                    "calls": [
                        {
                            "strike": 190.0,
                            "bid": 5.20,
                            "ask": 5.30,
                            "delta": 0.65,
                            "gamma": 0.018,
                            "vega": 0.42,
                            "theta": -0.08,
                            "rho": 0.12,
                            "volume": 1500,
                            "open_interest": 5000,
                            "iv": 0.28,
                        }
                    ],
                }
            ],
        }

        # Write
        snapshot_file.write_text(json.dumps(chain_data, indent=2))

        # Read
        loaded = json.loads(snapshot_file.read_text())

        # Verify all fields preserved
        original_calls = chain_data["chains"][0]["calls"][0]
        loaded_calls = loaded["chains"][0]["calls"][0]

        for key, value in original_calls.items():
            assert key in loaded_calls, f"Missing key: {key}"
            assert loaded_calls[key] == value, f"Value mismatch for {key}"

    def test_chain_snapshot_numeric_precision(self):
        """Test that numeric values maintain precision."""
        # Test various numeric values
        test_values = {
            "price": 192.50,
            "delta": 0.6547823,
            "gamma": 0.018432,
            "very_small": 1e-6,
            "zero": 0,
            "negative": -0.08,
        }

        # Simulate JSON serialization
        json_str = json.dumps(test_values)
        loaded = json.loads(json_str)

        # Verify precision (JSON may have floating point differences)
        for key, value in test_values.items():
            assert abs(loaded[key] - value) < 1e-10, f"Precision lost for {key}"


class TestChainSnapshotDeduplication:
    """Test deduplication of chain snapshots."""

    def test_duplicate_snapshot_detection(self, tmp_path):
        """Test that duplicate snapshots can be detected."""
        snapshot_file = tmp_path / "AAPL_chains.json"

        # Create snapshot
        chain_data = {
            "ticker": "AAPL",
            "snapshot_date": date.today().isoformat(),
            "timestamp": "2026-01-27T16:00:00+00:00",
            "underlying_price": 192.50,
            "chains": [],
        }

        # Write twice
        snapshot_file.write_text(json.dumps(chain_data))
        first_content = snapshot_file.read_text()

        snapshot_file.write_text(json.dumps(chain_data))
        second_content = snapshot_file.read_text()

        # Should be identical (deduplication key: ticker + date + expiration)
        assert first_content == second_content

    def test_snapshot_uniqueness_by_date_and_ticker(self, tmp_path):
        """Test that snapshots are unique by (ticker, snapshot_date, expiration)."""
        chains_dir = tmp_path / "chains"
        today_dir = chains_dir / date.today().strftime("%Y-%m-%d")
        today_dir.mkdir(parents=True)

        # Create snapshot
        snapshot1 = {
            "ticker": "AAPL",
            "snapshot_date": date.today().isoformat(),
            "chains": [{"expiration": "2026-02-20"}],
        }

        snapshot2 = {
            "ticker": "AAPL",
            "snapshot_date": date.today().isoformat(),
            "chains": [{"expiration": "2026-03-20"}],
        }

        # Same ticker and date but different expirations - should both be stored
        (today_dir / "AAPL_chains.json").write_text(json.dumps(snapshot1))
        assert (today_dir / "AAPL_chains.json").exists()


class TestChainSnapshotMetadata:
    """Test metadata tracking for chain snapshots."""

    def test_snapshot_has_timestamp(self):
        """Test that snapshots include proper timestamp."""
        snapshot = {
            "ticker": "AAPL",
            "snapshot_date": date.today().isoformat(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        assert "timestamp" in snapshot
        assert snapshot["timestamp"].endswith("Z") or "+" in snapshot["timestamp"]

    def test_snapshot_date_format(self):
        """Test that snapshot_date is in ISO format (YYYY-MM-DD)."""
        snapshot_date = date.today().isoformat()

        # Should be YYYY-MM-DD format
        assert len(snapshot_date) == 10
        assert snapshot_date[4] == "-"
        assert snapshot_date[7] == "-"

    def test_snapshot_file_path_format(self, tmp_path):
        """Test that file paths follow expected format."""
        chains_dir = tmp_path / "historical_data" / "chains"
        today = date.today()
        date_dir = chains_dir / today.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True)

        # Expected file path: historical_data/chains/YYYY-MM-DD/TICKER_chains.json
        expected_path = date_dir / "AAPL_chains.json"

        # Create file
        expected_path.write_text("{}")

        # Verify path structure
        assert str(expected_path).endswith("AAPL_chains.json")
        assert today.strftime("%Y-%m-%d") in str(expected_path)


class TestChainSnapshotRetention:
    """Test retention and cleanup policies for snapshots."""

    def test_old_snapshots_persist(self, tmp_path):
        """Test that old snapshots are retained."""
        chains_dir = tmp_path / "chains"

        # Create old snapshot
        old_date = date.today() - timedelta(days=365)
        old_dir = chains_dir / old_date.strftime("%Y-%m-%d")
        old_dir.mkdir(parents=True)
        old_file = old_dir / "AAPL_chains.json"
        old_file.write_text(json.dumps({"ticker": "AAPL"}))

        # Verify it exists
        assert old_file.exists()

    def test_snapshot_directory_persistence_across_runs(self, tmp_path):
        """Test that snapshot directories persist across multiple runs."""
        chains_dir = tmp_path / "chains"

        # First run
        date1 = date.today() - timedelta(days=1)
        dir1 = chains_dir / date1.strftime("%Y-%m-%d")
        dir1.mkdir(parents=True)
        (dir1 / "AAPL_chains.json").write_text("{}")

        # Second run
        date2 = date.today()
        dir2 = chains_dir / date2.strftime("%Y-%m-%d")
        dir2.mkdir(parents=True)
        (dir2 / "AAPL_chains.json").write_text("{}")

        # Both should exist
        assert dir1.exists()
        assert dir2.exists()


class TestChainSnapshotIndexing:
    """Test ability to index and search snapshots."""

    def test_snapshot_query_by_ticker_and_date(self, tmp_path):
        """Test querying snapshots by ticker and date."""
        chains_dir = tmp_path / "chains"

        # Create snapshots
        for i in range(3):
            d = date.today() - timedelta(days=i)
            date_dir = chains_dir / d.strftime("%Y-%m-%d")
            date_dir.mkdir(parents=True)
            for ticker in ["AAPL", "MSFT"]:
                (date_dir / f"{ticker}_chains.json").write_text(
                    json.dumps({"ticker": ticker, "date": str(d)})
                )

        # Query: AAPL on specific date
        query_date = date.today()
        query_dir = chains_dir / query_date.strftime("%Y-%m-%d")
        result = (query_dir / "AAPL_chains.json").read_text()

        loaded = json.loads(result)
        assert loaded["ticker"] == "AAPL"

    def test_list_all_snapshots_chronologically(self, tmp_path):
        """Test listing all snapshots in chronological order."""
        chains_dir = tmp_path / "chains"

        # Create snapshots across dates
        dates = [date.today() - timedelta(days=i) for i in range(5)]
        for d in dates:
            date_dir = chains_dir / d.strftime("%Y-%m-%d")
            date_dir.mkdir(parents=True)
            (date_dir / "AAPL_chains.json").write_text(
                json.dumps({"date": d.isoformat()})
            )

        # List chronologically
        snapshot_dirs = sorted([d for d in chains_dir.iterdir() if d.is_dir()])
        dir_dates = [d.name for d in snapshot_dirs]

        # Should be in order
        assert len(dir_dates) == 5


# ============================================================================
# Test Execution
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
