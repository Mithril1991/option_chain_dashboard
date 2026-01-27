"""
JSON Export Module for Option Chain Dashboard.

This module provides functionality to export data from the database to JSON files,
enabling the API to read data without requiring database locks. This solves DuckDB
concurrency issues by allowing the scheduler to write data while the API reads from files.

Classes:
    JSONExporter: Export alerts, chains, scans, and features to JSON files

Usage:
    from functions.export.json_exporter import JSONExporter

    exporter = JSONExporter()

    # Export all data
    exporter.export_all()

    # Export specific data types
    exporter.export_alerts()
    exporter.export_chains()
    exporter.export_scans()
    exporter.export_features()

Features:
    - Atomic writes (write to temp file, then rename)
    - Timestamped archives in data/exports/archive/
    - Latest exports in data/exports/ (for API to read)
    - Full type hints and comprehensive logging
    - Error handling with fallbacks
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from tempfile import NamedTemporaryFile
import os

from functions.util.logging_setup import get_logger
from functions.db.repositories import (
    AlertRepository,
    ChainSnapshotRepository,
    ScanRepository,
    FeatureSnapshotRepository,
)

logger = get_logger(__name__)


class JSONExporter:
    """
    Export data from database to JSON files for API consumption.

    This class handles exporting alerts, chains, scans, and features from the
    DuckDB database to JSON files in data/exports/, enabling read-only API access
    without database locks.

    Attributes:
        export_dir: Path to data/exports directory
        archive_dir: Path to data/exports/archive directory
        alert_repo: AlertRepository instance
        chain_repo: ChainSnapshotRepository instance
        scan_repo: ScanRepository instance
        feature_repo: FeatureSnapshotRepository instance
    """

    def __init__(self, export_base_dir: Optional[str] = None) -> None:
        """
        Initialize the JSON exporter.

        Args:
            export_base_dir: Optional custom base directory for exports
                           (defaults to data/exports/)

        Raises:
            RuntimeError: If export directories cannot be created
        """
        # Set up export directories
        if export_base_dir:
            self.export_dir = Path(export_base_dir)
        else:
            # Default: relative to project root
            project_root = Path(__file__).parent.parent.parent
            self.export_dir = project_root / "data" / "exports"

        self.archive_dir = self.export_dir / "archive"

        # Create directories if they don't exist
        try:
            self.export_dir.mkdir(parents=True, exist_ok=True)
            self.archive_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Export directories initialized: {self.export_dir}")
        except Exception as e:
            logger.error(f"Failed to create export directories: {e}")
            raise RuntimeError(f"Failed to initialize export directories: {e}") from e

        # Initialize repositories
        self.alert_repo = AlertRepository()
        self.chain_repo = ChainSnapshotRepository()
        self.scan_repo = ScanRepository()
        self.feature_repo = FeatureSnapshotRepository()

        logger.info("JSONExporter initialized successfully")

    def _atomic_write_json(
        self,
        file_path: Path,
        data: Dict[str, Any],
        timestamp: Optional[str] = None,
    ) -> None:
        """
        Atomically write JSON data to file (write temp, then rename).

        This prevents partial writes that could corrupt data if the process crashes.

        Args:
            file_path: Destination file path
            data: Dictionary to write as JSON
            timestamp: Optional timestamp to add to data

        Raises:
            RuntimeError: If write operation fails
        """
        try:
            # Add timestamp if not present
            if timestamp and "export_timestamp" not in data:
                data["export_timestamp"] = timestamp

            # Write to temporary file first
            temp_fd, temp_path = None, None
            try:
                temp_fd, temp_path = NamedTemporaryFile(
                    mode='w',
                    dir=self.export_dir,
                    delete=False,
                    suffix='.json',
                )
                json.dump(data, temp_fd, indent=2, default=str)
                temp_fd.close()

                # Atomic rename
                os.replace(temp_path, file_path)
                logger.debug(f"Wrote JSON file: {file_path}")

            except Exception as e:
                if temp_fd:
                    temp_fd.close()
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
                raise e

        except Exception as e:
            logger.error(f"Failed to write JSON file {file_path}: {e}")
            raise RuntimeError(f"Failed to write JSON file: {e}") from e

    def _create_archive_copy(self, filename: str, data: Dict[str, Any]) -> None:
        """
        Create timestamped archive copy of exported data.

        Archives are stored in data/exports/archive/ with timestamp suffix,
        enabling historical tracking and recovery.

        Args:
            filename: Base filename (e.g., "alerts.json")
            data: Dictionary to archive

        Raises:
            RuntimeError: If archive write fails
        """
        try:
            # Create timestamp for archive
            now = datetime.now(timezone.utc)
            timestamp_str = now.strftime("%Y%m%d_%H%M%S")
            base_name = filename.replace('.json', '')
            archive_filename = f"{base_name}_{timestamp_str}.json"
            archive_path = self.archive_dir / archive_filename

            # Write archive
            with open(archive_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            logger.debug(f"Created archive: {archive_path}")

        except Exception as e:
            logger.warning(f"Failed to create archive copy for {filename}: {e}")
            # Don't raise - archiving is non-critical

    def export_alerts(self, min_score: float = 0.0) -> Dict[str, Any]:
        """
        Export alerts to JSON.

        Exports all alerts from database, optionally filtered by minimum score.

        Args:
            min_score: Only export alerts with score >= this value (default 0.0)

        Returns:
            Dictionary with export metadata and alerts

        Raises:
            RuntimeError: If database query or write fails
        """
        try:
            logger.info("Exporting alerts to JSON...")

            # Query database for all alerts
            alerts = self.alert_repo.get_latest_alerts(limit=10000)

            # Filter by score
            if min_score > 0:
                alerts = [a for a in alerts if a.get("score", 0) >= min_score]

            # Create export data structure
            now = datetime.now(timezone.utc)
            export_data = {
                "export_timestamp": now.isoformat(),
                "alert_count": len(alerts),
                "min_score": min_score,
                "alerts": alerts,
            }

            # Write latest export
            alerts_path = self.export_dir / "alerts.json"
            self._atomic_write_json(alerts_path, export_data, now.isoformat())

            # Create archive
            self._create_archive_copy("alerts.json", export_data)

            logger.info(f"Exported {len(alerts)} alerts to JSON")
            return export_data

        except Exception as e:
            logger.error(f"Failed to export alerts: {e}")
            raise RuntimeError(f"Failed to export alerts: {e}") from e

    def export_chains(self, limit: int = 1000) -> Dict[str, Any]:
        """
        Export chain snapshots to JSON.

        Exports recent option chain snapshots, useful for API to access
        current options data without database lock.

        Args:
            limit: Maximum number of chain snapshots to export (default 1000)

        Returns:
            Dictionary with export metadata and chains

        Raises:
            RuntimeError: If database query or write fails
        """
        try:
            logger.info("Exporting chain snapshots to JSON...")

            # Query database for chain snapshots
            # Note: Assuming get_latest_snapshots exists or we fetch all
            chains = []
            try:
                # Get all chain snapshots (fallback to empty if repo method doesn't exist)
                sql = """
                    SELECT ticker, timestamp, underlying_price, expiration, calls_json, puts_json, created_at
                    FROM chain_snapshots
                    ORDER BY created_at DESC
                    LIMIT ?
                """
                result = self.chain_repo.db.execute(sql, [limit])
                rows = result.fetchall()

                for row in rows:
                    ticker, ts, price, expiration, calls_json, puts_json, created_at = row
                    chains.append({
                        "ticker": ticker,
                        "timestamp": ts,
                        "underlying_price": price,
                        "expiration": expiration,
                        "calls": json.loads(calls_json) if calls_json else [],
                        "puts": json.loads(puts_json) if puts_json else [],
                        "created_at": created_at,
                    })
            except Exception as e:
                logger.warning(f"Could not fetch chain snapshots from database: {e}")
                chains = []

            # Create export data structure
            now = datetime.now(timezone.utc)
            export_data = {
                "export_timestamp": now.isoformat(),
                "chain_count": len(chains),
                "chains": chains,
            }

            # Write latest export
            chains_path = self.export_dir / "chains.json"
            self._atomic_write_json(chains_path, export_data, now.isoformat())

            # Create archive
            self._create_archive_copy("chains.json", export_data)

            logger.info(f"Exported {len(chains)} chain snapshots to JSON")
            return export_data

        except Exception as e:
            logger.error(f"Failed to export chains: {e}")
            raise RuntimeError(f"Failed to export chains: {e}") from e

    def export_scans(self, days: int = 30) -> Dict[str, Any]:
        """
        Export scan history to JSON.

        Exports scan records for recent period, useful for tracking scan history
        without database access.

        Args:
            days: Number of days of scan history to export (default 30)

        Returns:
            Dictionary with export metadata and scans

        Raises:
            RuntimeError: If database query or write fails
        """
        try:
            logger.info(f"Exporting scan history (last {days} days) to JSON...")

            # Query database for scans
            scans = self.scan_repo.get_scan_history(days=days, limit=500)

            # Create export data structure
            now = datetime.now(timezone.utc)
            export_data = {
                "export_timestamp": now.isoformat(),
                "scan_count": len(scans),
                "days": days,
                "scans": scans,
            }

            # Write latest export
            scans_path = self.export_dir / "scans.json"
            self._atomic_write_json(scans_path, export_data, now.isoformat())

            # Create archive
            self._create_archive_copy("scans.json", export_data)

            logger.info(f"Exported {len(scans)} scans to JSON")
            return export_data

        except Exception as e:
            logger.error(f"Failed to export scans: {e}")
            raise RuntimeError(f"Failed to export scans: {e}") from e

    def export_features(self, limit: int = 10000) -> Dict[str, Any]:
        """
        Export feature snapshots to JSON.

        Exports computed features for all tickers, enabling API to access
        feature data without database lock.

        Args:
            limit: Maximum number of feature snapshots to export (default 10000)

        Returns:
            Dictionary with export metadata and features

        Raises:
            RuntimeError: If database query or write fails
        """
        try:
            logger.info("Exporting feature snapshots to JSON...")

            # Query database for features
            # Note: Fallback to empty if direct query needed
            features_list = []
            try:
                sql = """
                    SELECT ticker, features, created_at, scan_id
                    FROM feature_snapshots
                    ORDER BY created_at DESC
                    LIMIT ?
                """
                result = self.feature_repo.db.execute(sql, [limit])
                rows = result.fetchall()

                for row in rows:
                    ticker, features_json, created_at, scan_id = row
                    features_list.append({
                        "ticker": ticker,
                        "features": json.loads(features_json) if features_json else {},
                        "created_at": created_at,
                        "scan_id": scan_id,
                    })
            except Exception as e:
                logger.warning(f"Could not fetch features from database: {e}")
                features_list = []

            # Create export data structure
            now = datetime.now(timezone.utc)
            export_data = {
                "export_timestamp": now.isoformat(),
                "feature_count": len(features_list),
                "features": features_list,
            }

            # Write latest export
            features_path = self.export_dir / "features.json"
            self._atomic_write_json(features_path, export_data, now.isoformat())

            # Create archive
            self._create_archive_copy("features.json", export_data)

            logger.info(f"Exported {len(features_list)} feature snapshots to JSON")
            return export_data

        except Exception as e:
            logger.error(f"Failed to export features: {e}")
            raise RuntimeError(f"Failed to export features: {e}") from e

    def export_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Export all data (alerts, chains, scans, features) to JSON.

        This is the main export method called by the scheduler periodically
        (typically every 5-10 minutes).

        Returns:
            Dictionary with export results for each data type:
            {
                "alerts": {...},
                "chains": {...},
                "scans": {...},
                "features": {...},
                "export_timestamp": "2026-01-27T12:00:00Z",
                "success": True
            }

        Note:
            Individual export failures don't stop the entire export process.
            Each export attempt is logged separately.
        """
        logger.info("Starting full data export to JSON...")
        now = datetime.now(timezone.utc)

        results = {
            "export_timestamp": now.isoformat(),
            "exports": {},
            "errors": [],
            "success": True,
        }

        # Export alerts
        try:
            results["exports"]["alerts"] = self.export_alerts()
            logger.info("Alerts export completed successfully")
        except Exception as e:
            error_msg = f"Alerts export failed: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            results["exports"]["alerts"] = {"error": str(e)}

        # Export chains
        try:
            results["exports"]["chains"] = self.export_chains()
            logger.info("Chains export completed successfully")
        except Exception as e:
            error_msg = f"Chains export failed: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            results["exports"]["chains"] = {"error": str(e)}

        # Export scans
        try:
            results["exports"]["scans"] = self.export_scans()
            logger.info("Scans export completed successfully")
        except Exception as e:
            error_msg = f"Scans export failed: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            results["exports"]["scans"] = {"error": str(e)}

        # Export features
        try:
            results["exports"]["features"] = self.export_features()
            logger.info("Features export completed successfully")
        except Exception as e:
            error_msg = f"Features export failed: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            results["exports"]["features"] = {"error": str(e)}

        # Set success flag
        results["success"] = len(results["errors"]) == 0

        logger.info(
            f"Full export completed: success={results['success']}, "
            f"errors={len(results['errors'])}"
        )

        return results
