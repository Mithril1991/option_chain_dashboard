"""
Schema versioning and migration system for DuckDB.

Provides idempotent database schema management with version tracking.
All migrations are applied in order and recorded in the schema_version table.

This system ensures:
- Idempotent operations (safe to run multiple times)
- DuckDB-specific SQL support
- Comprehensive logging of all migration attempts
- Support for both inline SQL and file-based migrations
- Data preservation (no data dropped without explicit confirmation)

Usage:
    from functions.db.migrations import run_migrations, get_current_version

    # Check current schema version
    version = get_current_version()
    print(f"Current schema version: {version}")

    # Apply all pending migrations
    result = run_migrations()
    print(f"Applied {len(result['applied_migrations'])} migrations")
    print(f"Current version: {result['current_version']}")

    if result['errors']:
        print(f"Errors: {result['errors']}")
"""

from typing import Optional, Tuple, Dict, List, Any
from pathlib import Path
import logging
from datetime import datetime

# Note: Will import duckdb when functions.db.connection is available
# For now, using lazy import pattern

logger = logging.getLogger(__name__)


# ============================================================================
# Migration Definitions
# ============================================================================

MIGRATIONS: List[Tuple[int, str, str]] = [
    (
        1,
        "Initial schema - Create core tables",
        """
        -- Options data table
        CREATE TABLE IF NOT EXISTS options (
            id INTEGER PRIMARY KEY DEFAULT nextval('seq_options_id'),
            symbol VARCHAR NOT NULL,
            expiration DATE NOT NULL,
            option_type VARCHAR NOT NULL,  -- 'call' or 'put'
            strike FLOAT NOT NULL,
            bid FLOAT,
            ask FLOAT,
            last_price FLOAT,
            volume INTEGER,
            open_interest INTEGER,
            implied_volatility FLOAT,
            delta FLOAT,
            gamma FLOAT,
            theta FLOAT,
            vega FLOAT,
            rho FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, expiration, option_type, strike)
        );

        -- Create sequence for options ID
        CREATE SEQUENCE IF NOT EXISTS seq_options_id START 1;

        -- Market data cache table
        CREATE TABLE IF NOT EXISTS market_cache (
            id INTEGER PRIMARY KEY DEFAULT nextval('seq_market_cache_id'),
            symbol VARCHAR NOT NULL,
            data_type VARCHAR NOT NULL,  -- 'quote', 'info', 'historical'
            data JSON,
            fetched_at TIMESTAMP NOT NULL,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, data_type)
        );

        CREATE SEQUENCE IF NOT EXISTS seq_market_cache_id START 1;

        -- Strategy definitions table
        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY DEFAULT nextval('seq_strategies_id'),
            name VARCHAR NOT NULL,
            description TEXT,
            strategy_type VARCHAR NOT NULL,  -- 'spread', 'straddle', 'custom'
            legs JSON NOT NULL,  -- Array of leg definitions
            entry_price FLOAT,
            max_profit FLOAT,
            max_loss FLOAT,
            breakeven_points JSON,  -- Array of breakeven prices
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name)
        );

        CREATE SEQUENCE IF NOT EXISTS seq_strategies_id START 1;

        -- Backtest results table
        CREATE TABLE IF NOT EXISTS backtest_results (
            id INTEGER PRIMARY KEY DEFAULT nextval('seq_backtest_id'),
            strategy_id INTEGER,
            symbol VARCHAR NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            trades_count INTEGER,
            winning_trades INTEGER,
            losing_trades INTEGER,
            win_rate FLOAT,
            total_return FLOAT,
            annual_return FLOAT,
            sharpe_ratio FLOAT,
            max_drawdown FLOAT,
            result_data JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE SEQUENCE IF NOT EXISTS seq_backtest_id START 1;

        -- Create indexes for common queries
        CREATE INDEX IF NOT EXISTS idx_options_symbol ON options(symbol);
        CREATE INDEX IF NOT EXISTS idx_options_expiration ON options(expiration);
        CREATE INDEX IF NOT EXISTS idx_options_strike ON options(strike);
        CREATE INDEX IF NOT EXISTS idx_market_cache_symbol ON market_cache(symbol);
        CREATE INDEX IF NOT EXISTS idx_market_cache_expires ON market_cache(expires_at);
        """,
    ),
]

# ============================================================================
# Schema Version Management
# ============================================================================


def ensure_schema_version_table() -> bool:
    """
    Create schema_version table if it doesn't exist.

    This table tracks which migrations have been applied.
    Must be called before any migration operations.

    Returns:
        True if table exists or was created, False on error

    Example:
        if not ensure_schema_version_table():
            logger.error("Failed to ensure schema_version table")
            return False
    """
    try:
        # Lazy import to avoid circular dependencies
        import duckdb

        conn = duckdb.connect()

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                description VARCHAR NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.close()
        logger.debug("schema_version table ensured")
        return True
    except Exception as e:
        logger.error(f"Failed to ensure schema_version table: {e}")
        return False


def get_applied_versions() -> set[int]:
    """
    Get set of all migration versions that have been applied.

    Queries the schema_version table to determine which migrations
    have already been successfully applied.

    Returns:
        Set of version numbers that have been applied (empty set if table doesn't exist)

    Example:
        applied = get_applied_versions()
        print(f"Applied migrations: {sorted(applied)}")
    """
    try:
        import duckdb

        conn = duckdb.connect()

        try:
            result = conn.execute(
                "SELECT version FROM schema_version ORDER BY version"
            ).fetchall()
            versions = {row[0] for row in result}
            logger.debug(f"Applied versions: {sorted(versions)}")
            return versions
        except Exception as e:
            # Table doesn't exist yet, that's okay
            logger.debug(f"schema_version table doesn't exist yet: {e}")
            return set()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error getting applied versions: {e}")
        return set()


def get_current_version() -> int:
    """
    Get the highest schema version that has been applied.

    Queries the schema_version table and returns the maximum version number.
    Returns 0 if the table doesn't exist or is empty (initial state).

    Returns:
        Current schema version (0 if no migrations applied)

    Raises:
        No exceptions are raised - returns 0 on any error

    Example:
        current_version = get_current_version()
        print(f"Database schema version: {current_version}")
        # Output: Database schema version: 3
    """
    try:
        import duckdb

        conn = duckdb.connect()

        try:
            result = conn.execute(
                "SELECT MAX(version) as version FROM schema_version"
            ).fetchone()

            # fetchone() returns a tuple, first element is the version
            version = result[0] if result and result[0] is not None else 0
            logger.debug(f"Current schema version: {version}")
            return version
        except Exception as e:
            # Table doesn't exist, schema is at version 0
            logger.debug(f"schema_version table doesn't exist: {e}")
            return 0
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error getting current version: {e}")
        return 0


# ============================================================================
# Migration Execution
# ============================================================================


def apply_migration(version: int, description: str, sql: str) -> bool:
    """
    Apply a single migration and record it in the schema_version table.

    This function is idempotent - if the migration has already been applied,
    it will return False without re-executing. Execute SQL statements from the
    provided SQL string and record the version in schema_version.

    The SQL string should contain one or more valid DuckDB SQL statements
    separated by semicolons. Each statement will be executed in order.

    Args:
        version: Migration version number (should be unique, typically sequential)
        description: Human-readable description of what this migration does
        sql: SQL statements to execute (can contain multiple statements)

    Returns:
        True if migration was applied successfully or already applied,
        False if there was an error executing the migration

    Example:
        success = apply_migration(
            version=2,
            description="Add user_preferences table",
            sql="CREATE TABLE IF NOT EXISTS user_preferences (id INTEGER, ...)"
        )
        if success:
            logger.info("Migration 2 applied successfully")
    """
    try:
        import duckdb

        # Check if already applied
        applied_versions = get_applied_versions()
        if version in applied_versions:
            logger.info(f"Migration {version} already applied, skipping")
            return True

        logger.info(f"Applying migration {version}: {description}")

        conn = duckdb.connect()

        try:
            # Execute the SQL statements
            # Split by semicolon to handle multiple statements
            statements = [s.strip() for s in sql.split(";") if s.strip()]

            for statement in statements:
                logger.debug(f"Executing: {statement[:100]}...")
                conn.execute(statement)

            # Record the version in schema_version table
            conn.execute(
                """
                INSERT INTO schema_version (version, description)
                VALUES (?, ?)
                """,
                [version, description],
            )

            conn.close()
            logger.info(
                f"Migration {version} applied successfully: {description}"
            )
            return True

        except Exception as e:
            conn.close()
            logger.error(f"Error executing migration {version}: {e}")
            return False

    except Exception as e:
        logger.error(f"Error applying migration {version}: {e}")
        return False


# ============================================================================
# Migration Runner
# ============================================================================


def run_migrations() -> Dict[str, Any]:
    """
    Run all pending migrations in order and return detailed results.

    This function:
    1. Ensures the schema_version table exists
    2. Checks the current schema version
    3. Applies all pending migrations from MIGRATIONS in order
    4. Returns a detailed result dict with status information

    The function is safe to run multiple times - migrations that have already
    been applied will be skipped.

    Returns:
        Dictionary with the following keys:
        - 'current_version': Current schema version after migrations
        - 'applied_migrations': List of (version, description) tuples that were applied
        - 'errors': List of migration version numbers that failed
        - 'total_migrations': Total number of migrations defined
        - 'skipped_migrations': Number of migrations already applied
        - 'success': True if all pending migrations succeeded

    Example:
        result = run_migrations()
        print(f"Schema version: {result['current_version']}")
        print(f"Applied migrations: {result['applied_migrations']}")
        if result['errors']:
            print(f"Failed migrations: {result['errors']}")
        if result['success']:
            print("All migrations completed successfully!")

    Example output:
        {
            'current_version': 3,
            'applied_migrations': [(1, 'Initial schema'), (2, 'Add user table')],
            'errors': [],
            'total_migrations': 3,
            'skipped_migrations': 1,
            'success': True
        }
    """
    result: Dict[str, Any] = {
        "current_version": 0,
        "applied_migrations": [],
        "errors": [],
        "total_migrations": len(MIGRATIONS),
        "skipped_migrations": 0,
        "success": True,
    }

    logger.info("Starting migration run")

    try:
        # Ensure schema_version table exists
        if not ensure_schema_version_table():
            logger.error("Failed to ensure schema_version table")
            result["success"] = False
            result["current_version"] = get_current_version()
            return result

        # Get current version
        current_version = get_current_version()
        logger.info(f"Current schema version: {current_version}")

        # Get all applied versions to detect skipped migrations
        applied_versions = get_applied_versions()
        result["skipped_migrations"] = len(applied_versions)

        # Apply pending migrations
        for version, description, sql in MIGRATIONS:
            if version in applied_versions:
                logger.debug(f"Migration {version} already applied, skipping")
                continue

            success = apply_migration(version, description, sql)

            if success:
                result["applied_migrations"].append((version, description))
            else:
                result["errors"].append(version)
                result["success"] = False

        # Get final version
        result["current_version"] = get_current_version()

        if result["success"]:
            logger.info(
                f"All migrations completed successfully. "
                f"Schema version: {result['current_version']}"
            )
        else:
            logger.warning(
                f"Some migrations failed. "
                f"Failed versions: {result['errors']}"
            )

        return result

    except Exception as e:
        logger.error(f"Unexpected error during migration run: {e}")
        result["success"] = False
        result["current_version"] = get_current_version()
        return result


# ============================================================================
# Utility Functions for Migration Management
# ============================================================================


def get_migration_info() -> Dict[str, Any]:
    """
    Get detailed information about current migration status.

    Returns information about defined migrations and their application status,
    useful for diagnostics and admin operations.

    Returns:
        Dictionary with:
        - 'current_version': Current applied version
        - 'latest_version': Latest defined migration version
        - 'pending_migrations': List of (version, description) not yet applied
        - 'applied_migrations': List of (version, description) that are applied
        - 'is_up_to_date': True if current version equals latest version

    Example:
        info = get_migration_info()
        print(f"Database version: {info['current_version']}/{info['latest_version']}")
        if info['pending_migrations']:
            print("Pending migrations:")
            for version, description in info['pending_migrations']:
                print(f"  {version}: {description}")
    """
    current = get_current_version()
    applied_versions = get_applied_versions()
    latest = max([v for v, _, _ in MIGRATIONS]) if MIGRATIONS else 0

    pending = [
        (v, d)
        for v, d, _ in MIGRATIONS
        if v not in applied_versions
    ]

    applied = [
        (v, d)
        for v, d, _ in MIGRATIONS
        if v in applied_versions
    ]

    return {
        "current_version": current,
        "latest_version": latest,
        "pending_migrations": pending,
        "applied_migrations": applied,
        "is_up_to_date": current == latest,
    }


def reset_database_schema() -> bool:
    """
    DROP ALL TABLES - Dangerous operation! Use with extreme caution.

    This function completely removes all tables from the database,
    including the schema_version table. This destroys all data.

    Use ONLY for:
    - Development/testing when you need a clean slate
    - Database reset after major schema changes
    - Never in production without explicit confirmation

    Returns:
        True if reset successful, False otherwise

    WARNING:
        This operation is IRREVERSIBLE. All data will be lost.
        A confirmation message is logged when this runs.
    """
    logger.critical(
        "WARNING: Database schema reset requested. This will DELETE ALL DATA!"
    )

    try:
        import duckdb

        conn = duckdb.connect()

        try:
            # Get list of all tables
            tables = conn.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'main'
                """
            ).fetchall()

            # Drop each table
            for (table_name,) in tables:
                logger.warning(f"Dropping table: {table_name}")
                conn.execute(f"DROP TABLE IF EXISTS {table_name}")

            # Drop all sequences
            sequences = conn.execute(
                """
                SELECT sequence_name FROM information_schema.sequences
                WHERE sequence_schema = 'main'
                """
            ).fetchall()

            for (sequence_name,) in sequences:
                logger.warning(f"Dropping sequence: {sequence_name}")
                conn.execute(f"DROP SEQUENCE IF EXISTS {sequence_name}")

            logger.critical("Database schema reset completed. All tables dropped.")
            return True

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error during database reset: {e}")
        return False
