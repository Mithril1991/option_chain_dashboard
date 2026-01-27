"""
Structured logging configuration for the Option Chain Dashboard.

Provides centralized logging setup with both console and rotating file handlers.
All timestamps use UTC for consistency across distributed systems.

Usage:
    from functions.util.logging_setup import setup_logging, get_logger

    # Setup logging once at application startup
    setup_logging(log_level="INFO")

    # Get logger in any module
    logger = get_logger(__name__)
    logger.info("Application started")
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
import pytz


# Module-level logger registry
_loggers: dict[str, logging.Logger] = {}


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
    log_file: str = "option_chain_dashboard.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """
    Configure logging for the application.

    Sets up both console and rotating file handlers with UTC timestamps.
    All timestamps use ISO 8601 format with UTC timezone.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory to store log files. Defaults to ./logs
        log_file: Name of the log file. Defaults to option_chain_dashboard.log
        max_bytes: Max size per log file in bytes. Defaults to 10MB
        backup_count: Number of backup log files to keep. Defaults to 5

    Raises:
        ValueError: If log_level is invalid
        OSError: If log_dir cannot be created
    """
    # Validate log level
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if log_level.upper() not in valid_levels:
        raise ValueError(
            f"Invalid log level '{log_level}'. Must be one of: {valid_levels}"
        )

    # Setup log directory
    if log_dir is None:
        log_dir = Path(__file__).parent.parent.parent / "logs"
    else:
        log_dir = Path(log_dir)

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise OSError(f"Failed to create log directory '{log_dir}': {e}") from e

    log_path = log_dir / log_file

    # Create formatter with UTC timestamps
    # Format: 2026-01-26T15:30:45.123Z [LEVEL] module.function:line - message
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",  # ISO format
    )

    # Custom formatter to add Z suffix for UTC
    class UTCFormatter(logging.Formatter):
        """Logging formatter that adds 'Z' suffix to indicate UTC timezone."""

        converter = lambda *args: datetime.now(pytz.UTC).timetuple()

        def formatTime(self, record, datefmt=None):
            """Format time with UTC timezone indicator."""
            dt = datetime.fromtimestamp(record.created, tz=pytz.UTC)
            if datefmt:
                s = dt.strftime(datefmt)
            else:
                s = dt.isoformat()
            return f"{s}Z" if not s.endswith("Z") else s

    utc_formatter = UTCFormatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Console handler (stderr for errors, stdout for info)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level.upper())
    console_handler.setFormatter(utc_formatter)
    root_logger.addHandler(console_handler)

    # Rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level.upper())
    file_handler.setFormatter(utc_formatter)
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger instance for the given name.

    This function caches loggers to avoid creating duplicates.
    It's recommended to use __name__ as the logger name.

    Args:
        name: The name of the logger (typically __name__)

    Returns:
        A configured Logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Application started")
    """
    if name not in _loggers:
        _loggers[name] = logging.getLogger(name)
    return _loggers[name]


def reset_loggers() -> None:
    """
    Clear all cached loggers and reset logging configuration.

    Useful for testing or when you need to reconfigure logging.
    """
    global _loggers
    _loggers.clear()
    logging.shutdown()


# Default setup on module import
# This ensures basic logging is available even if setup_logging() is not called
if not logging.getLogger().handlers:
    try:
        setup_logging(log_level="INFO")
    except Exception:
        # Fallback to basic configuration if setup fails
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        )
