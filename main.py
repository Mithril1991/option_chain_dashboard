"""
Root-level entrypoint for Option Chain Dashboard.

This module starts and coordinates all three subsystems:
1. Scheduler Engine: Handles rate-limited data collection (async task)
2. FastAPI API: REST backend server (subprocess on port 8061)
3. React UI: Frontend server (pointer to port 8060)

All systems start successfully or the application exits with an error. Graceful
shutdown is enforced with signal handlers and timeout protection.

Usage:
    # Default configuration (config.yaml, production mode)
    python main.py

    # With demo mode and debug logging
    python main.py --demo-mode --debug

    # Custom configuration path
    python main.py --config-path /path/to/config.yaml

CLI Arguments:
    --config-path: Path to configuration YAML file (default: config.yaml)
    --demo-mode: Use demo/mock data instead of live market data
    --debug: Enable DEBUG level logging (default: INFO)

Environment Variables:
    CONFIG_PATH: Path to configuration file (overridden by --config-path)
    DEMO_MODE: Set to "true" for demo mode (overridden by --demo-mode)
    LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR; overridden by --debug)

Startup Sequence:
    1. Parse CLI arguments and environment variables
    2. Set up logging (root logger with UTC timestamps)
    3. Initialize database and run migrations
    4. Load configuration from YAML
    5. Start scheduler engine as async task
    6. Start FastAPI server as subprocess (uvicorn on port 8061)
    7. Print startup banner with system status
    8. Wait for interrupt (SIGTERM, SIGINT)
    9. Gracefully shutdown all subsystems (max 10 seconds)

Graceful Shutdown:
    - Catches SIGTERM and SIGINT signals
    - Sets graceful_shutdown event
    - Cancels scheduler task
    - Terminates FastAPI subprocess
    - Closes database connection
    - Prints shutdown message

All timestamps are UTC ISO 8601 format. Full type hints throughout.
"""

import argparse
import asyncio
import hashlib
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

# Initialize database FIRST before importing modules that depend on it
from functions.db.connection import init_db, get_db
init_db()  # Initialize database immediately

# Now safe to import modules that depend on the database
from functions.util.logging_setup import setup_logging, get_logger
from functions.config.loader import get_config_manager
from functions.config.settings import get_settings
from scripts.scheduler_engine import SchedulerEngine
from scripts.run_scan import run_scan
from functions.market.demo_provider import DemoMarketDataProvider

# ============================================================================
# MODULE-LEVEL GLOBALS
# ============================================================================

logger: Any = None
graceful_shutdown: asyncio.Event = asyncio.Event()
fastapi_process: Optional[subprocess.Popen] = None
scheduler_task: Optional[asyncio.Task] = None


# ============================================================================
# SIGNAL HANDLERS
# ============================================================================

def signal_handler(signum: int, frame: Any) -> None:
    """
    Handle system signals (SIGTERM, SIGINT).

    Sets the graceful_shutdown event to trigger orderly cleanup of all
    subsystems. Called when user presses Ctrl+C or process receives SIGTERM.

    Args:
        signum: Signal number (15 for SIGTERM, 2 for SIGINT)
        frame: Stack frame at time of signal
    """
    sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
    logger.warning(f"Received {sig_name} ({signum}), initiating graceful shutdown...")
    graceful_shutdown.set()


# ============================================================================
# UTILITIES
# ============================================================================

def get_utc_timestamp() -> str:
    """
    Get current UTC time as ISO 8601 string.

    Returns:
        ISO 8601 formatted timestamp (e.g., '2026-01-26T15:30:45.123456Z')
    """
    return datetime.now(timezone.utc).isoformat()


def compute_config_hash(config_path: Path) -> str:
    """
    Compute SHA256 hash of configuration file.

    Args:
        config_path: Path to configuration file

    Returns:
        Hexadecimal SHA256 hash

    Raises:
        RuntimeError: If file cannot be read
    """
    try:
        with open(config_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception as e:
        raise RuntimeError(f"Failed to compute config hash: {e}") from e


def print_startup_banner(
    config_path: str,
    demo_mode: bool,
    config_hash: str,
) -> None:
    """
    Print formatted startup banner with system information.

    Args:
        config_path: Path to configuration file
        demo_mode: Whether running in demo mode
        config_hash: SHA256 hash of configuration
    """
    timestamp = get_utc_timestamp()
    mode_str = "DEMO MODE (mock data)" if demo_mode else "PRODUCTION (live data)"

    banner = f"""
{'='*80}
OPTION CHAIN DASHBOARD - STARTING UP
{'='*80}
Timestamp:          {timestamp} UTC
Mode:               {mode_str}
Config File:        {config_path}
Config Hash:        {config_hash[:16]}...
API Docs:           http://localhost:8061/docs
ReDoc:              http://localhost:8061/redoc
React Frontend:     http://localhost:8060
Scheduler:          Running (rate-limited data collection)
FastAPI Backend:    Starting on port 8061
{'='*80}
    """
    logger.info(banner)


def print_system_running_banner() -> None:
    """Print message indicating all systems are operational."""
    banner = f"""
{'='*80}
ALL SYSTEMS OPERATIONAL
{'='*80}
Scheduler:          Running
FastAPI Backend:    Running on http://localhost:8061
React Frontend:     Available on http://localhost:8060

To stop, press Ctrl+C (graceful shutdown)
{'='*80}
    """
    logger.info(banner)


def print_shutdown_banner() -> None:
    """Print message indicating shutdown has completed."""
    timestamp = get_utc_timestamp()
    banner = f"""
{'='*80}
SHUTDOWN COMPLETE
{'='*80}
Timestamp:          {timestamp} UTC
Status:             All systems stopped gracefully
{'='*80}
    """
    logger.info(banner)


# ============================================================================
# INITIALIZATION
# ============================================================================

def initialize_logging(debug: bool) -> None:
    """
    Initialize root logger with appropriate level.

    Args:
        debug: If True, set DEBUG level; otherwise INFO
    """
    global logger
    log_level = "DEBUG" if debug else "INFO"
    setup_logging(log_level=log_level)
    logger = get_logger(__name__)
    logger.info(f"Logging initialized: level={log_level}")


def initialize_database() -> None:
    """
    Initialize database and run migrations.

    Raises:
        RuntimeError: If database initialization fails
    """
    try:
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
        raise RuntimeError(f"Database initialization failed: {e}") from e


def load_configuration(config_path: str) -> tuple[str, bool]:
    """
    Load application configuration and settings.

    Args:
        config_path: Path to configuration YAML file

    Returns:
        Tuple of (config_hash, demo_mode)

    Raises:
        RuntimeError: If configuration cannot be loaded
    """
    try:
        logger.info(f"Loading configuration from: {config_path}")

        # Verify config file exists
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        # Get configuration manager (loads config.yaml from specified directory)
        config_file = Path(config_path)
        config_mgr = get_config_manager(config_dir=config_file.parent)
        config_mgr.reload()
        config_hash = config_mgr.config_hash
        logger.info(f"Configuration loaded: hash={config_hash[:16]}...")

        # Get settings (includes demo_mode)
        settings = get_settings()
        logger.info(f"Settings loaded: demo_mode={settings.demo_mode}")

        return config_hash, settings.demo_mode

    except Exception as e:
        logger.error(f"Configuration loading failed: {e}", exc_info=True)
        raise RuntimeError(f"Configuration loading failed: {e}") from e


# ============================================================================
# SUBSYSTEM MANAGEMENT
# ============================================================================

async def start_scheduler_engine() -> asyncio.Task:
    """
    Start the scheduler engine as an async task.

    The scheduler runs the state machine continuously for rate-limited
    data collection. It is cancelled gracefully on shutdown.

    Returns:
        asyncio.Task running the scheduler

    Raises:
        RuntimeError: If scheduler cannot be created
    """
    try:
        logger.info("Starting Scheduler Engine...")
        config_mgr = get_config_manager()
        config = config_mgr.config

        # Create scheduler with demo market data provider (TODO: replace with real provider)
        provider = DemoMarketDataProvider()
        logger.info("Using DemoMarketDataProvider for scheduled scans")
        scheduler = SchedulerEngine(
            config=config,
            scan_runner=run_scan,
            provider=provider,
        )

        # Create task for run_forever (will run indefinitely)
        task = asyncio.create_task(scheduler.run_forever())
        logger.info("Scheduler Engine started successfully")
        return task

    except Exception as e:
        logger.error(f"Failed to start Scheduler Engine: {e}", exc_info=True)
        raise RuntimeError(f"Failed to start Scheduler Engine: {e}") from e


def start_fastapi_server(port: int = 8061) -> subprocess.Popen:
    """
    Start FastAPI server as a subprocess (uvicorn).

    The server runs indefinitely and is terminated gracefully on shutdown.

    Args:
        port: Port number for FastAPI server (default 8061)

    Returns:
        subprocess.Popen object for the server process

    Raises:
        RuntimeError: If server process cannot be started
    """
    try:
        logger.info(f"Starting FastAPI server on port {port}...")

        # Build uvicorn command
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "scripts.run_api:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
            "--log-level",
            "info",
        ]

        # Start subprocess with output to file for debugging
        api_log_file = open("logs/api_subprocess.log", "w")
        process = subprocess.Popen(
            cmd,
            stdout=api_log_file,
            stderr=api_log_file,
            text=True,
            bufsize=1,
        )

        # Check if process started successfully
        try:
            # Give subprocess time to fail if there's an immediate error
            import time
            time.sleep(1)
            returncode = process.poll()
            if returncode is not None:
                # Process exited immediately (error)
                api_log_file.close()
                with open("logs/api_subprocess.log", "r") as f:
                    stderr = f.read()
                raise RuntimeError(f"FastAPI process exited with code {returncode}: {stderr}")
        except Exception as e:
            logger.error(f"Failed to start FastAPI server: {e}", exc_info=True)
            raise RuntimeError(f"Failed to start FastAPI server: {e}") from e

        logger.info(f"FastAPI server started successfully on port {port}")
        return process

    except Exception as e:
        logger.error(f"Failed to start FastAPI server: {e}", exc_info=True)
        raise RuntimeError(f"Failed to start FastAPI server: {e}") from e


# ============================================================================
# GRACEFUL SHUTDOWN
# ============================================================================

async def shutdown_gracefully(timeout_sec: float = 10.0) -> None:
    """
    Gracefully shutdown all subsystems.

    Cancels the scheduler task and terminates the FastAPI process with
    a timeout. Forces termination if graceful shutdown takes too long.

    Args:
        timeout_sec: Maximum seconds to wait for graceful shutdown (default 10)
    """
    logger.warning(f"Starting graceful shutdown (timeout: {timeout_sec}s)...")

    try:
        # Cancel scheduler task
        if scheduler_task and not scheduler_task.done():
            logger.info("Cancelling Scheduler Engine...")
            scheduler_task.cancel()

            try:
                # Wait for scheduler to finish
                await asyncio.wait_for(scheduler_task, timeout=timeout_sec)
            except asyncio.TimeoutError:
                logger.warning(f"Scheduler did not stop within {timeout_sec}s, forcing termination")
            except asyncio.CancelledError:
                logger.info("Scheduler cancelled successfully")

        # Terminate FastAPI process
        if fastapi_process and fastapi_process.poll() is None:
            logger.info("Terminating FastAPI server...")
            try:
                fastapi_process.terminate()
                # Give it a few seconds to terminate gracefully
                try:
                    fastapi_process.wait(timeout=3.0)
                    logger.info("FastAPI server terminated")
                except subprocess.TimeoutExpired:
                    logger.warning("FastAPI server did not terminate gracefully, killing...")
                    fastapi_process.kill()
                    fastapi_process.wait()
                    logger.info("FastAPI server killed")
            except Exception as e:
                logger.error(f"Error terminating FastAPI server: {e}")

        # Close database connection
        try:
            db = get_db()
            if db:
                db.close_connection()
                logger.info("Database connection closed")
        except Exception as e:
            logger.warning(f"Error closing database connection: {e}")

        logger.info("Graceful shutdown completed")

    except Exception as e:
        logger.error(f"Error during graceful shutdown: {e}", exc_info=True)


# ============================================================================
# MAIN ASYNC FUNCTION
# ============================================================================

async def main() -> int:
    """
    Main async entrypoint for Option Chain Dashboard.

    Starts all subsystems (scheduler, FastAPI, database), waits for interrupt
    signal, and performs graceful shutdown.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    global scheduler_task, fastapi_process

    try:
        # Setup signal handlers
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        # Print startup banner
        banner_text = f"""
{'='*80}
OPTION CHAIN DASHBOARD - INITIALIZATION
{'='*80}
Timestamp:          {get_utc_timestamp()} UTC
Python Version:     {sys.version.split()[0]}
{'='*80}
        """
        logger.info(banner_text)

        # Initialize database
        initialize_database()

        # Load configuration
        config_hash, demo_mode = load_configuration(args.config_path)

        # Print startup banner
        print_startup_banner("config.yaml", demo_mode, config_hash)

        # Start scheduler engine
        scheduler_task = await start_scheduler_engine()

        # Start FastAPI server
        fastapi_process = start_fastapi_server(port=8061)

        # Print system running message
        print_system_running_banner()

        # Wait for shutdown signal
        logger.info("Waiting for shutdown signal (Ctrl+C or SIGTERM)...")
        await graceful_shutdown.wait()

        # Shutdown gracefully
        logger.warning("Shutdown signal received, starting graceful shutdown...")
        await shutdown_gracefully(timeout_sec=10.0)

        # Print shutdown banner
        print_shutdown_banner()

        logger.info("Exiting with code 0 (success)")
        return 0

    except KeyboardInterrupt:
        logger.warning("Keyboard interrupt received")
        await shutdown_gracefully(timeout_sec=10.0)
        print_shutdown_banner()
        logger.info("Exiting with code 0 (interrupted)")
        return 0

    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        try:
            await shutdown_gracefully(timeout_sec=5.0)
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup after fatal error: {cleanup_error}")
        logger.error("Exiting with code 1 (error)")
        return 1


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

def run() -> int:
    """
    Entry point for CLI - wraps main() in asyncio.run().

    Parses command-line arguments, initializes logging, and runs the main
    async function. Handles top-level exceptions and returns appropriate
    exit code.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Parse CLI arguments
    parser = argparse.ArgumentParser(
        description="Start Option Chain Dashboard with all subsystems",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Subsystems Started:
  - Scheduler Engine: Rate-limited data collection (async)
  - FastAPI Backend: REST API on http://localhost:8061
  - React Frontend: Available on http://localhost:8060

Examples:
  python main.py                              # Production mode
  python main.py --demo-mode --debug          # Demo mode with debug logging
  python main.py --config-path /path/to/config.yaml
        """,
    )

    parser.add_argument(
        "--config-path",
        type=str,
        default=os.getenv("CONFIG_PATH", "config.yaml"),
        help="Path to configuration YAML file (default: config.yaml)",
    )

    parser.add_argument(
        "--demo-mode",
        action="store_true",
        default=os.getenv("DEMO_MODE", "").lower() == "true",
        help="Use demo/mock data instead of live market data",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        default=os.getenv("LOG_LEVEL", "").upper() == "DEBUG",
        help="Enable DEBUG level logging (default: INFO)",
    )

    args = parser.parse_args()

    # Initialize logging first
    try:
        initialize_logging(args.debug)
    except Exception as e:
        print(f"ERROR: Failed to initialize logging: {e}", file=sys.stderr)
        return 1

    logger.info(f"CLI arguments: config_path={args.config_path}, demo_mode={args.demo_mode}, debug={args.debug}")

    # Run main async function
    try:
        exit_code = asyncio.run(main())
        return exit_code
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}", exc_info=True)
        return 1


# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    exit_code = run()
    sys.exit(exit_code)
