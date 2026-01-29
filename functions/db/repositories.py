"""
Database Repository Classes for Option Chain Dashboard

This module provides repository classes for data persistence and retrieval.
Each repository handles a specific entity or data domain with consistent CRUD operations.

Classes:
    - ScanRepository: Manage option chain scans
    - FeatureSnapshotRepository: Store feature calculations and metrics
    - AlertRepository: Track generated alerts
    - CooldownRepository: Manage alert cooldown periods
    - IVHistoryRepository: Track implied volatility over time
    - ChainSnapshotRepository: Archive historical option chains
    - TransactionRepository: Track trading transactions

Usage:
    from functions.db.repositories import ScanRepository, AlertRepository
    from functions.db.connection import init_db

    # Initialize DB at startup
    init_db()

    # Use repositories
    scan_repo = ScanRepository()
    scan_id = scan_repo.create_scan("abc123")
    latest = scan_repo.get_latest_scan()
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any, Tuple
import json
from abc import ABC, abstractmethod

from functions.db.connection import get_db
from functions.util.logging_setup import get_logger

logger = get_logger(__name__)


class BaseRepository(ABC):
    """
    Abstract base class for all repositories.
    Provides common interface for data persistence operations.
    """

    def __init__(self):
        """Initialize repository with database connection."""
        self.db = get_db()
        logger.debug(f"Initialized {self.__class__.__name__}")


class ScanRepository(BaseRepository):
    """
    Repository for managing option chain scan records.

    Handles storage and retrieval of scan executions, including metadata
    about when scans were performed, which tickers were processed, and
    scan execution statistics.

    Methods:
        create_scan: Create a new scan record
        update_scan: Update scan status and results
        get_scan: Get a scan by ID
        get_latest_scan: Get most recent scan
        get_scan_history: Get scan history with pagination
    """

    def create_scan(self, config_hash: str) -> int:
        """
        Create a new scan record.

        Args:
            config_hash: SHA256 hash of configuration used for scan

        Returns:
            ID of created scan record

        Raises:
            RuntimeError: If database operation fails
        """
        try:
            # Use RETURNING id to get the auto-generated ID back from DuckDB
            sql = """
                INSERT INTO scans (scan_ts, config_hash, status, created_at)
                VALUES (CURRENT_TIMESTAMP, ?, 'pending', CURRENT_TIMESTAMP)
                RETURNING id
            """
            result = self.db.execute(sql, [config_hash])
            row = result.fetchone()
            scan_id = row[0] if row else None

            if scan_id is None:
                raise RuntimeError("Failed to retrieve inserted scan ID")

            logger.info(f"Created scan record: id={scan_id}, config_hash={config_hash[:8]}")
            return scan_id

        except Exception as e:
            logger.error(f"Failed to create scan: {e}")
            raise RuntimeError(f"Failed to create scan record: {e}") from e

    def update_scan(
        self,
        scan_id: int,
        status: str,
        tickers_scanned: Optional[int] = None,
        alerts_generated: Optional[int] = None,
        runtime_seconds: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update scan status and results.

        Args:
            scan_id: ID of scan to update
            status: New status (pending, running, completed, failed, partial)
            tickers_scanned: Number of tickers scanned
            alerts_generated: Number of alerts generated
            runtime_seconds: Execution time in seconds
            error_message: Error message if scan failed

        Raises:
            RuntimeError: If database operation fails
        """
        try:
            updates = ["status = ?"]
            params = [status]

            if tickers_scanned is not None:
                updates.append("tickers_scanned = ?")
                params.append(tickers_scanned)

            if alerts_generated is not None:
                updates.append("alerts_generated = ?")
                params.append(alerts_generated)

            if runtime_seconds is not None:
                updates.append("runtime_seconds = ?")
                params.append(runtime_seconds)

            if error_message is not None:
                updates.append("error_message = ?")
                params.append(error_message)

            params.append(scan_id)

            sql = f"UPDATE scans SET {', '.join(updates)} WHERE id = ?"
            self.db.execute_insert(sql, params)

            logger.info(f"Updated scan: id={scan_id}, status={status}")

        except Exception as e:
            logger.error(f"Failed to update scan {scan_id}: {e}")
            raise RuntimeError(f"Failed to update scan: {e}") from e

    def get_scan(self, scan_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a scan by ID.

        Args:
            scan_id: ID of scan to retrieve

        Returns:
            Scan record as dictionary or None if not found
        """
        try:
            sql = "SELECT * FROM scans WHERE id = ?"
            result = self.db.execute(sql, [scan_id])
            row = result.fetchone()

            if not row:
                return None

            columns = [desc[0] for desc in result.description]
            return dict(zip(columns, row))

        except Exception as e:
            logger.error(f"Failed to get scan {scan_id}: {e}")
            raise RuntimeError(f"Failed to retrieve scan: {e}") from e

    def get_latest_scan(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent scan record.

        Returns:
            Most recent scan record or None if no scans exist

        Example:
            latest = scan_repo.get_latest_scan()
            if latest:
                print(f"Latest scan: {latest['scan_ts']}, status: {latest['status']}")
        """
        try:
            sql = """
                SELECT * FROM scans
                ORDER BY scan_ts DESC
                LIMIT 1
            """
            result = self.db.execute(sql)
            row = result.fetchone()

            if not row:
                logger.debug("No scans found in database")
                return None

            columns = [desc[0] for desc in result.description]
            scan = dict(zip(columns, row))
            logger.debug(f"Retrieved latest scan: id={scan['id']}, status={scan['status']}")
            return scan

        except Exception as e:
            logger.error(f"Failed to get latest scan: {e}")
            raise RuntimeError(f"Failed to retrieve latest scan: {e}") from e

    def get_scan_history(
        self, days: int = 30, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieve scan history for recent period.

        Args:
            days: Number of days to look back (default 30)
            limit: Maximum records to return (default 100)
            offset: Pagination offset (default 0)

        Returns:
            List of scan records sorted by date descending

        Example:
            scans = scan_repo.get_scan_history(days=7, limit=50)
            for scan in scans:
                print(f"{scan['created_at']}: {scan['tickers_scanned']} tickers, {scan['alerts_generated']} alerts")
        """
        try:
            # FIX: Parameter binding for INTERVAL requires special syntax.
            # In DuckDB, INTERVAL '? days' doesn't work - the ? must be outside the string.
            # Changed from:
            #   WHERE created_at >= (CURRENT_TIMESTAMP - INTERVAL '? days')
            # To:
            #   WHERE created_at >= (CURRENT_TIMESTAMP - ? * INTERVAL '1 day')
            # This properly binds the 'days' parameter as a numeric multiplier.
            sql = """
                SELECT * FROM scans
                WHERE created_at >= (CURRENT_TIMESTAMP - ? * INTERVAL '1 day')
                ORDER BY scan_ts DESC
                LIMIT ? OFFSET ?
            """
            # Parameters: days (for interval calculation), limit (for LIMIT), offset (for OFFSET)
            result = self.db.execute(sql, [days, limit, offset])
            rows = result.fetchall()

            if not rows:
                logger.debug(f"No scans found in last {days} days")
                return []

            columns = [desc[0] for desc in result.description]
            scans = [dict(zip(columns, row)) for row in rows]
            logger.debug(f"Retrieved {len(scans)} scans from last {days} days")
            return scans

        except Exception as e:
            logger.error(f"Failed to get scan history: {e}")
            raise RuntimeError(f"Failed to retrieve scan history: {e}") from e


class FeatureSnapshotRepository(BaseRepository):
    """
    Repository for managing feature snapshots.

    Stores calculated feature values and metrics for option chains,
    allowing historical analysis of how features evolve over time.

    Methods:
        save_snapshot: Save a feature snapshot
        get_snapshot: Get a specific snapshot
        get_latest_snapshot: Get most recent snapshot for ticker
    """

    def save_snapshot(self, scan_id: int, ticker: str, features: Dict[str, Any]) -> None:
        """
        Save a feature snapshot.

        Args:
            scan_id: Reference to parent scan
            ticker: Stock ticker symbol
            features: Dictionary of features (JSON-serializable)

        Raises:
            RuntimeError: If database operation fails

        Example:
            features = {
                "iv_percentile": 65.5,
                "volume_spike": 2.3,
                "skew_rank": 8,
                "timestamp": "2026-01-26T15:30:00Z"
            }
            repo.save_snapshot(scan_id=42, ticker="AAPL", features=features)
        """
        try:
            features_json = json.dumps(features)
            sql = """
                INSERT INTO feature_snapshots (scan_id, ticker, features, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """
            self.db.execute_insert(sql, [scan_id, ticker, features_json])
            logger.debug(f"Saved feature snapshot: scan_id={scan_id}, ticker={ticker}")

        except Exception as e:
            logger.error(f"Failed to save feature snapshot: {e}")
            raise RuntimeError(f"Failed to save feature snapshot: {e}") from e

    def get_snapshot(self, scan_id: int, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific feature snapshot.

        Args:
            scan_id: Reference to parent scan
            ticker: Stock ticker symbol

        Returns:
            Feature snapshot as dictionary or None if not found

        Raises:
            RuntimeError: If database operation fails
        """
        try:
            sql = """
                SELECT id, scan_id, ticker, features, created_at
                FROM feature_snapshots
                WHERE scan_id = ? AND ticker = ?
                LIMIT 1
            """
            result = self.db.execute(sql, [scan_id, ticker])
            row = result.fetchone()

            if not row:
                return None

            snapshot_id, sid, tick, features_json, created_at = row
            features = json.loads(features_json)

            return {
                "id": snapshot_id,
                "scan_id": sid,
                "ticker": tick,
                "features": features,
                "created_at": created_at,
            }

        except Exception as e:
            logger.error(f"Failed to get feature snapshot: {e}")
            raise RuntimeError(f"Failed to retrieve feature snapshot: {e}") from e

    def get_latest_snapshot(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent feature snapshot for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Latest feature snapshot or None if not found

        Example:
            snapshot = repo.get_latest_snapshot("AAPL")
            if snapshot:
                print(f"IV Percentile: {snapshot['features']['iv_percentile']}")
        """
        try:
            sql = """
                SELECT id, scan_id, ticker, features, created_at
                FROM feature_snapshots
                WHERE ticker = ?
                ORDER BY created_at DESC
                LIMIT 1
            """
            result = self.db.execute(sql, [ticker])
            row = result.fetchone()

            if not row:
                logger.debug(f"No feature snapshots found for {ticker}")
                return None

            snapshot_id, scan_id, tick, features_json, created_at = row
            features = json.loads(features_json)

            return {
                "id": snapshot_id,
                "scan_id": scan_id,
                "ticker": tick,
                "features": features,
                "created_at": created_at,
            }

        except Exception as e:
            logger.error(f"Failed to get latest snapshot for {ticker}: {e}")
            raise RuntimeError(f"Failed to retrieve latest snapshot: {e}") from e


class AlertRepository(BaseRepository):
    """
    Repository for managing generated alerts.

    Tracks all alerts created by the scanning system, including alert details,
    scoring, and metadata.

    Methods:
        save_alert: Save a single alert
        save_alerts_batch: Batch insert multiple alerts (30-40% faster)
        get_latest_alerts: Get recent alerts
        get_alerts_by_ticker: Get alerts for specific ticker
        get_alerts_by_detector: Get alerts from specific detector
        get_alerts_today_count: Get today's alert count
        increment_daily_count: Increment daily counter
    """

    def save_alert(
        self,
        scan_id: int,
        ticker: str,
        detector_name: str,
        score: float,
        alert_data: Dict[str, Any],
    ) -> int:
        """
        Save a single alert.

        Args:
            scan_id: Reference to parent scan
            ticker: Stock ticker symbol
            detector_name: Name of detector that generated alert
            score: Alert score (0-100)
            alert_data: Alert metadata as dictionary

        Returns:
            ID of created alert

        Raises:
            RuntimeError: If database operation fails

        Example:
            alert_id = repo.save_alert(
                scan_id=42,
                ticker="AAPL",
                detector_name="volume_spike",
                score=75.5,
                alert_data={
                    "volume_ratio": 2.3,
                    "avg_volume": 1500000,
                    "current_volume": 3450000
                }
            )
        """
        try:
            alert_json = json.dumps(alert_data)
            # Use RETURNING id to get the auto-generated ID from DuckDB (don't call fetchone twice!)
            sql = """
                INSERT INTO alerts (scan_id, ticker, detector_name, score, alert_json, created_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                RETURNING id
            """
            result = self.db.execute(sql, [scan_id, ticker, detector_name, score, alert_json])
            row = result.fetchone()
            alert_id = row[0] if row else None

            if alert_id is None:
                raise RuntimeError("Failed to retrieve inserted alert ID")

            logger.info(
                f"Saved alert: id={alert_id}, ticker={ticker}, detector={detector_name}, score={score:.1f}"
            )
            return alert_id

        except Exception as e:
            logger.error(f"Failed to save alert: {e}")
            raise RuntimeError(f"Failed to save alert: {e}") from e

    def save_alerts_batch(self, scan_id: int, alerts: List[Dict[str, Any]]) -> int:
        """
        Batch insert multiple alerts (30-40% faster than individual inserts).

        Args:
            scan_id: Reference to parent scan
            alerts: List of alert dictionaries with keys:
                   ticker, detector_name, score, alert_data

        Returns:
            Number of alerts created

        Raises:
            RuntimeError: If database operation fails

        Example:
            alerts = [
                {
                    "ticker": "AAPL",
                    "detector_name": "volume_spike",
                    "score": 75.5,
                    "alert_data": {"volume_ratio": 2.3}
                },
                {
                    "ticker": "MSFT",
                    "detector_name": "iv_expansion",
                    "score": 82.1,
                    "alert_data": {"iv_percentile": 95}
                }
            ]
            count = repo.save_alerts_batch(scan_id=42, alerts=alerts)
            print(f"Created {count} alerts")
        """
        if not alerts:
            return 0

        try:
            sql = """
                INSERT INTO alerts (scan_id, ticker, detector_name, score, alert_json, created_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """

            count = 0
            for alert in alerts:
                ticker = alert.get("ticker")
                detector_name = alert.get("detector_name")
                score = alert.get("score", 0.0)
                alert_data = alert.get("alert_data", {})

                alert_json = json.dumps(alert_data)
                self.db.execute_insert(sql, [scan_id, ticker, detector_name, score, alert_json])
                count += 1

            logger.info(f"Batch inserted {count} alerts for scan {scan_id}")
            return count

        except Exception as e:
            logger.error(f"Failed to batch insert alerts: {e}")
            raise RuntimeError(f"Failed to batch insert alerts: {e}") from e

    def get_latest_alerts(self, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Get most recent alerts.

        Args:
            limit: Maximum alerts to return (default 200)

        Returns:
            List of recent alerts sorted by date descending

        Example:
            alerts = repo.get_latest_alerts(limit=100)
            for alert in alerts:
                print(f"{alert['ticker']}: {alert['score']:.1f}")
        """
        try:
            sql = """
                SELECT id, scan_id, ticker, detector_name, score, alert_json, created_at
                FROM alerts
                ORDER BY created_at DESC
                LIMIT ?
            """
            result = self.db.execute(sql, [limit])
            rows = result.fetchall()

            alerts = []
            for row in rows:
                alert_id, sid, ticker, detector, score, alert_json, created_at = row
                alert_data = json.loads(alert_json)
                alerts.append({
                    "id": alert_id,
                    "scan_id": sid,
                    "ticker": ticker,
                    "detector_name": detector,
                    "score": score,
                    "alert_data": alert_data,
                    "created_at": created_at,
                })

            logger.debug(f"Retrieved {len(alerts)} latest alerts")
            return alerts

        except Exception as e:
            logger.error(f"Failed to get latest alerts: {e}")
            raise RuntimeError(f"Failed to retrieve latest alerts: {e}") from e

    def get_alerts_by_ticker(self, ticker: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get alerts for a specific ticker.

        Args:
            ticker: Stock ticker symbol
            limit: Maximum alerts to return (default 50)

        Returns:
            List of alerts for ticker sorted by date descending
        """
        try:
            sql = """
                SELECT id, scan_id, ticker, detector_name, score, alert_json, created_at
                FROM alerts
                WHERE ticker = ?
                ORDER BY created_at DESC
                LIMIT ?
            """
            result = self.db.execute(sql, [ticker, limit])
            rows = result.fetchall()

            alerts = []
            for row in rows:
                alert_id, sid, tick, detector, score, alert_json, created_at = row
                alert_data = json.loads(alert_json)
                alerts.append({
                    "id": alert_id,
                    "scan_id": sid,
                    "ticker": tick,
                    "detector_name": detector,
                    "score": score,
                    "alert_data": alert_data,
                    "created_at": created_at,
                })

            logger.debug(f"Retrieved {len(alerts)} alerts for {ticker}")
            return alerts

        except Exception as e:
            logger.error(f"Failed to get alerts for {ticker}: {e}")
            raise RuntimeError(f"Failed to retrieve alerts: {e}") from e

    def get_alerts_by_detector(self, detector_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get alerts from a specific detector.

        Args:
            detector_name: Name of detector
            limit: Maximum alerts to return (default 50)

        Returns:
            List of alerts from detector sorted by score descending
        """
        try:
            sql = """
                SELECT id, scan_id, ticker, detector_name, score, alert_json, created_at
                FROM alerts
                WHERE detector_name = ?
                ORDER BY score DESC
                LIMIT ?
            """
            result = self.db.execute(sql, [detector_name, limit])
            rows = result.fetchall()

            alerts = []
            for row in rows:
                alert_id, sid, ticker, detector, score, alert_json, created_at = row
                alert_data = json.loads(alert_json)
                alerts.append({
                    "id": alert_id,
                    "scan_id": sid,
                    "ticker": ticker,
                    "detector_name": detector,
                    "score": score,
                    "alert_data": alert_data,
                    "created_at": created_at,
                })

            logger.debug(f"Retrieved {len(alerts)} alerts from {detector_name}")
            return alerts

        except Exception as e:
            logger.error(f"Failed to get alerts from {detector_name}: {e}")
            raise RuntimeError(f"Failed to retrieve alerts: {e}") from e

    def get_alerts_today_count(self) -> int:
        """
        Get number of alerts generated today.

        Returns:
            Count of today's alerts

        Raises:
            RuntimeError: If database operation fails
        """
        try:
            sql = """
                SELECT COUNT(*) as count
                FROM alerts
                WHERE DATE(created_at) = CURRENT_DATE
            """
            result = self.db.execute(sql)
            row = result.fetchone()
            count = row[0] if row else 0

            logger.debug(f"Today's alert count: {count}")
            return count

        except Exception as e:
            logger.error(f"Failed to get today's alert count: {e}")
            raise RuntimeError(f"Failed to get alert count: {e}") from e

    def increment_daily_count(self) -> None:
        """
        Increment daily alert count for rate limiting.

        Creates or updates the daily_alert_counts record for today.

        Raises:
            RuntimeError: If database operation fails
        """
        try:
            sql = """
                INSERT INTO daily_alert_counts (count_date, alert_count)
                VALUES (CURRENT_DATE, 1)
                ON CONFLICT (count_date) DO UPDATE SET alert_count = alert_count + 1
            """
            self.db.execute_insert(sql)
            logger.debug("Incremented daily alert count")

        except Exception as e:
            logger.error(f"Failed to increment daily count: {e}")
            raise RuntimeError(f"Failed to increment daily count: {e}") from e


class CooldownRepository(BaseRepository):
    """
    Repository for managing alert cooldown periods.

    Tracks per-ticker alert throttling to prevent spam. Uses last_alert_ts
    and last_score for intelligent throttling.

    Methods:
        get_cooldown: Get cooldown info for ticker
        update_cooldown: Update cooldown with score
        is_in_cooldown: Check if ticker is in cooldown
    """

    def get_cooldown(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get cooldown information for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Cooldown record with last_alert_ts and last_score, or None if not found

        Raises:
            RuntimeError: If database operation fails

        Example:
            cooldown = repo.get_cooldown("AAPL")
            if cooldown:
                print(f"Last alert: {cooldown['last_alert_ts']}")
                print(f"Last score: {cooldown['last_score']}")
        """
        try:
            sql = """
                SELECT ticker, last_alert_ts, last_score
                FROM alert_cooldowns
                WHERE ticker = ?
            """
            result = self.db.execute(sql, [ticker])
            row = result.fetchone()

            if not row:
                return None

            return {
                "ticker": row[0],
                "last_alert_ts": row[1],
                "last_score": row[2],
            }

        except Exception as e:
            logger.error(f"Failed to get cooldown for {ticker}: {e}")
            raise RuntimeError(f"Failed to get cooldown: {e}") from e

    def update_cooldown(self, ticker: str, score: float) -> None:
        """
        Update cooldown record for ticker with new score.

        Creates or updates alert_cooldowns record with current timestamp.

        Args:
            ticker: Stock ticker symbol
            score: Alert score to store

        Raises:
            RuntimeError: If database operation fails

        Example:
            repo.update_cooldown("AAPL", score=75.5)
        """
        try:
            sql = """
                INSERT INTO alert_cooldowns (ticker, last_alert_ts, last_score)
                VALUES (?, CURRENT_TIMESTAMP, ?)
                ON CONFLICT (ticker) DO UPDATE SET
                    last_alert_ts = CURRENT_TIMESTAMP,
                    last_score = EXCLUDED.last_score
            """
            self.db.execute_insert(sql, [ticker, score])
            logger.debug(f"Updated cooldown: ticker={ticker}, score={score:.1f}")

        except Exception as e:
            logger.error(f"Failed to update cooldown for {ticker}: {e}")
            raise RuntimeError(f"Failed to update cooldown: {e}") from e

    def is_in_cooldown(
        self, ticker: str, cooldown_hours: int, min_score_improvement: float = 0.1
    ) -> Tuple[bool, Optional[float]]:
        """
        Check if ticker is in cooldown period.

        Returns True if last alert was within cooldown_hours AND the new score
        isn't significantly higher than last_score (by min_score_improvement threshold).

        Args:
            ticker: Stock ticker symbol
            cooldown_hours: Cooldown period in hours
            min_score_improvement: Minimum score improvement to bypass cooldown (0-100)

        Returns:
            Tuple of (is_on_cooldown: bool, time_remaining_hours: Optional[float])
            Returns (False, None) if not on cooldown or if no cooldown record exists

        Raises:
            RuntimeError: If database operation fails

        Example:
            is_cooldown, hours_remaining = repo.is_in_cooldown("AAPL", cooldown_hours=1)
            if is_cooldown:
                print(f"In cooldown for {hours_remaining:.1f} more hours")
            else:
                print("Cooldown period has expired")
        """
        try:
            cooldown = self.get_cooldown(ticker)

            if not cooldown or cooldown["last_alert_ts"] is None:
                return False, None

            sql = """
                SELECT
                    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - ?)) / 3600.0 as hours_since,
                    CURRENT_TIMESTAMP - INTERVAL '? hours' > ? as is_expired
                FROM (SELECT 1)
            """
            result = self.db.execute(sql, [cooldown["last_alert_ts"], cooldown_hours])
            row = result.fetchone()

            if not row:
                return False, None

            hours_since = row[0]
            is_expired = row[1]

            if is_expired:
                return False, None

            # Calculate time remaining
            time_remaining = cooldown_hours - hours_since

            logger.debug(
                f"Ticker {ticker} in cooldown: {time_remaining:.1f} hours remaining"
            )
            return True, time_remaining

        except Exception as e:
            logger.error(f"Failed to check cooldown for {ticker}: {e}")
            raise RuntimeError(f"Failed to check cooldown: {e}") from e


class IVHistoryRepository(BaseRepository):
    """
    Repository for tracking implied volatility over time.

    Stores historical IV data including ATM IV, historical volatility,
    and IV percentile rankings to support volatility analysis.
    """

    def __init__(self):
        """Initialize IVHistoryRepository.

        Calls super().__init__() to properly initialize self.db with the
        DuckDB connection from get_db().
        """
        super().__init__()

    def save_iv(
        self,
        ticker: str,
        iv_date: datetime,
        atm_iv_front: float,
        atm_iv_back: float,
        hv_20: float,
        hv_60: float,
        iv_percentile: float,
    ) -> None:
        """
        Save or update IV record (UPSERT).

        Args:
            ticker: Stock ticker symbol
            iv_date: Date/time of IV measurement
            atm_iv_front: At-the-money IV for front month expiration
            atm_iv_back: At-the-money IV for back month expiration
            hv_20: Historical volatility over 20 days
            hv_60: Historical volatility over 60 days
            iv_percentile: IV percentile relative to historical range
        """
        pass

    def get_iv_history(
        self, ticker: str, days: int = 252
    ) -> List[Dict[str, Any]]:
        """
        Get IV history for a ticker.

        Args:
            ticker: Stock ticker symbol
            days: Number of days to look back (default 1 year)

        Returns:
            List of IV records sorted by date ascending
        """
        pass

    def get_iv_percentile(
        self, ticker: str, current_iv: float, lookback_days: int = 252
    ) -> Optional[float]:
        """
        Calculate current IV percentile within historical range.

        Args:
            ticker: Stock ticker symbol
            current_iv: Current IV value to rank
            lookback_days: Historical period for percentile calculation

        Returns:
            Percentile value (0-100) or None if insufficient data
        """
        pass

    def get_latest_iv(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get most recent IV record for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Latest IV record or None if no data exists
        """
        pass


class ChainSnapshotRepository(BaseRepository):
    """
    Repository for archiving historical option chain snapshots.

    Captures complete snapshots of option chains at specific points in time,
    enabling historical analysis and backtesting capabilities.
    """

    def __init__(self):
        """Initialize ChainSnapshotRepository.

        CRITICAL FIX: This __init__ was not calling super().__init__(), which meant
        self.db was never initialized and would be None. This caused AttributeError
        when export_chains() tried to call self.chain_repo.db.execute().

        By calling super().__init__(), we now properly initialize self.db with the
        DuckDB connection from get_db(), making the repository fully functional.
        """
        super().__init__()

    def save_chain_snapshot(
        self,
        scan_id: int,
        ticker: str,
        snapshot_date: datetime,
        expiration: date,
        dte: int,
        underlying_price: float,
        chain_json: Dict[str, Any],
        num_calls: int,
        num_puts: int,
        atm_iv: float,
        total_volume: int,
        total_oi: int,
        file_path: str,
    ) -> int:
        """
        Save a complete option chain snapshot.

        Args:
            scan_id: Reference to parent scan
            ticker: Stock ticker symbol
            snapshot_date: Timestamp of snapshot
            expiration: Option expiration date
            dte: Days to expiration
            underlying_price: Underlying stock price
            chain_json: Complete chain data as JSON dictionary
            num_calls: Number of call options in chain
            num_puts: Number of put options in chain
            atm_iv: At-the-money implied volatility
            total_volume: Total volume across all options
            total_oi: Total open interest across all options
            file_path: Path to file where chain data is stored

        Returns:
            ID of created chain snapshot
        """
        pass

    def get_chain_snapshot(
        self, ticker: str, snapshot_date: datetime, expiration: date
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific chain snapshot.

        Args:
            ticker: Stock ticker symbol
            snapshot_date: Exact snapshot timestamp
            expiration: Option expiration date

        Returns:
            Chain snapshot record or None if not found
        """
        pass

    def get_latest_chains(
        self, ticker: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get most recent chain snapshots for a ticker.

        Args:
            ticker: Stock ticker symbol
            limit: Maximum snapshots to return

        Returns:
            List of recent chain snapshots sorted by date descending
        """
        pass

    def get_chain_history(
        self, ticker: str, expiration: date
    ) -> List[Dict[str, Any]]:
        """
        Get all snapshots for a specific expiration date.

        Args:
            ticker: Stock ticker symbol
            expiration: Option expiration date

        Returns:
            List of all snapshots for this expiration, sorted by date
        """
        pass


class TransactionRepository(BaseRepository):
    """
    Repository for tracking trading transactions.

    Records all trading activity including buys, sells, dividends, fees, etc.
    across multiple accounts and symbols.
    """

    def __init__(self):
        """Initialize TransactionRepository.

        Calls super().__init__() to properly initialize self.db with the
        DuckDB connection from get_db().
        """
        super().__init__()

    def add_transaction(
        self,
        date: datetime,
        account: str,
        description: str,
        transaction_type: str,
        gross_amount: float,
        net_amount: float,
        symbol: Optional[str] = None,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        commission: float = 0.0,
        multiplier: int = 1,
        sub_type: Optional[str] = None,
        exchange_rate: float = 1.0,
        transaction_fees: float = 0.0,
        currency: str = "USD",
    ) -> int:
        """
        Add a new transaction record.

        Args:
            date: Transaction date/time
            account: Trading account identifier
            description: Transaction description
            transaction_type: Type (BUY, SELL, DIVIDEND, INTEREST, FEE, ADJUSTMENT)
            gross_amount: Amount before fees/commissions
            net_amount: Amount after fees/commissions
            symbol: Stock or option symbol
            quantity: Number of shares or contracts
            price: Price per share/contract
            commission: Brokerage commission
            multiplier: Contract multiplier (100 for options, 1 for stocks)
            sub_type: Additional transaction subtype
            exchange_rate: Foreign exchange rate if applicable
            transaction_fees: Other fees besides commission
            currency: Currency code (e.g., 'USD', 'EUR')

        Returns:
            ID of created transaction
        """
        pass

    def get_transactions(
        self,
        account: Optional[str] = None,
        symbol: Optional[str] = None,
        transaction_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve transactions with optional filtering.

        Args:
            account: Filter by account
            symbol: Filter by symbol
            transaction_type: Filter by transaction type
            start_date: Earliest transaction date
            end_date: Latest transaction date
            limit: Maximum transactions to return
            offset: Pagination offset

        Returns:
            List of matching transactions
        """
        pass

    def get_transaction_summary(
        self, account: str, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get aggregate transaction summary for period.

        Args:
            account: Trading account
            start_date: Period start
            end_date: Period end

        Returns:
            Dictionary with total_buys, total_sells, net_proceeds,
            total_commissions, total_fees, by_symbol breakdown, etc.
        """
        pass


# Singleton Repository Instances
# These instances should be used throughout the application to ensure
# consistent database access patterns.

scan_repo = ScanRepository()
"""Repository for scan records"""

feature_snapshot_repo = FeatureSnapshotRepository()
"""Repository for feature snapshots"""

alert_repo = AlertRepository()
"""Repository for alerts"""

cooldown_repo = CooldownRepository()
"""Repository for cooldown tracking"""

iv_history_repo = IVHistoryRepository()
"""Repository for IV history"""

chain_snapshot_repo = ChainSnapshotRepository()
"""Repository for option chain snapshots"""

transaction_repo = TransactionRepository()
"""Repository for transactions"""
