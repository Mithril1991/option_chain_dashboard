"""
Configuration manager for loading and managing application configuration.

Handles loading configuration from YAML files, watchlist files, and account
settings. Provides singleton access and configuration change detection.

Configuration Sources:
    - config.yaml: Main application configuration
    - watchlist.txt: List of ticker symbols (one per line)
    - account.yaml: Account-specific settings (optional)
    - theses/: Directory of trading thesis files

Usage:
    from functions.config.loader import ConfigManager

    config_mgr = ConfigManager()
    config = config_mgr.config
    print(config.scan.symbols)

    # Reload configuration if files change
    config_mgr.reload()
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from functools import lru_cache
import yaml

from functions.util.logging_setup import get_logger
from functions.config.models import AppConfig

logger = get_logger(__name__)


class ConfigManager:
    """
    Manages loading and tracking application configuration.

    Singleton pattern ensures consistent configuration across the application.
    Tracks configuration changes for cache invalidation and scan metadata.
    """

    _instance: Optional["ConfigManager"] = None

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize ConfigManager.

        Args:
            config_dir: Directory containing configuration files.
                       Defaults to project root.
        """
        if config_dir is None:
            # Assume this module is at functions/config/loader.py
            config_dir = Path(__file__).parent.parent.parent

        self.config_dir = Path(config_dir)
        self._config: Optional[AppConfig] = None
        self._config_hash: str = ""
        self._loaded_files: Dict[str, float] = {}  # filename -> mtime

        # Load configuration
        self.reload()

    @classmethod
    def get_instance(cls, config_dir: Optional[Path] = None) -> "ConfigManager":
        """
        Get singleton ConfigManager instance.

        Args:
            config_dir: Configuration directory (only used on first instantiation)

        Returns:
            Singleton ConfigManager instance
        """
        if cls._instance is None:
            cls._instance = cls(config_dir)
        return cls._instance

    @property
    def config(self) -> AppConfig:
        """
        Get the current application configuration.

        Returns:
            Loaded AppConfig instance
        """
        if self._config is None:
            raise RuntimeError(
                "Configuration not loaded. Call reload() to load configuration."
            )
        return self._config

    @property
    def config_hash(self) -> str:
        """
        Get hash of current configuration.

        Useful for cache invalidation and scan metadata.
        Changes when any configuration file changes.

        Returns:
            Hex digest of configuration hash
        """
        return self._config_hash

    def reload(self) -> None:
        """
        Reload configuration from files.

        Loads configuration from:
        1. config.yaml (main config)
        2. watchlist.txt (symbols)
        3. account.yaml (account settings, optional)
        4. theses/*.yaml (trading theses, optional)

        Updates internal configuration hash.

        Raises:
            FileNotFoundError: If required config files are missing
            yaml.YAMLError: If YAML parsing fails
            ValueError: If configuration validation fails
        """
        logger.info(f"Loading configuration from {self.config_dir}")

        # Load main config
        config_data = self._load_yaml("config.yaml", required=True)

        # Load watchlist from config file first
        watchlist_symbols = config_data.get("watchlist")
        if isinstance(watchlist_symbols, list) and watchlist_symbols:
            logger.info(f"Using {len(watchlist_symbols)} symbols from config watchlist")
            config_data.setdefault("scan", {})["symbols"] = [
                sym.upper() for sym in watchlist_symbols if isinstance(sym, str)
            ]
        else:
            symbols = self._load_watchlist("watchlist.txt", required=False)
            if symbols:
                config_data.setdefault("scan", {})["symbols"] = symbols
                logger.info(f"Loaded {len(symbols)} symbols from watchlist.txt")

        # Map scheduler settings from nested section to top-level attributes
        scheduler_cfg = config_data.get("scheduler", {})
        if isinstance(scheduler_cfg, dict):
            for key in ["max_calls_per_hour", "max_calls_per_day", "flush_threshold", "check_interval_sec"]:
                value = scheduler_cfg.get(key)
                if value is not None:
                    config_data[key] = value
            collection_times = scheduler_cfg.get("collection_times_et")
            if collection_times is not None:
                config_data["collection_times_et"] = collection_times

        # Map risk settings to attributes expected by RiskGate
        risk_cfg = config_data.get("risk", {})
        if isinstance(risk_cfg, dict):
            if "max_concentration_pct" in risk_cfg:
                config_data["max_concentration_pct"] = risk_cfg["max_concentration_pct"]
            if "max_margin_usage_pct" in risk_cfg:
                config_data["margin_gate_threshold_pct"] = risk_cfg["max_margin_usage_pct"]
            if "min_cash_buffer_pct" in risk_cfg:
                config_data["cash_gate_threshold_pct"] = risk_cfg["min_cash_buffer_pct"]

        # Load account settings (optional)
        account_data = self._load_yaml("account.yaml", required=False)
        if account_data:
            logger.info("Loaded account settings from account.yaml")
            # Merge account settings into config
            config_data = self._deep_merge(config_data, account_data)

        # Load theses (optional)
        theses = self._load_theses()
        if theses:
            config_data["theses"] = theses
            logger.info(f"Loaded {len(theses)} trading theses")

        # Validate and create AppConfig
        try:
            self._config = AppConfig(**config_data)
            logger.info("Configuration loaded and validated successfully")
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            raise ValueError(f"Invalid configuration: {e}") from e

        # Compute configuration hash
        self._compute_config_hash()

    def _load_yaml(self, filename: str, required: bool = True) -> Dict[str, Any]:
        """
        Load YAML configuration file.

        Args:
            filename: Name of the YAML file to load
            required: Whether file must exist

        Returns:
            Dictionary of loaded configuration

        Raises:
            FileNotFoundError: If required file doesn't exist
        """
        file_path = self.config_dir / filename
        if not file_path.exists():
            if required:
                raise FileNotFoundError(
                    f"Required configuration file not found: {file_path}"
                )
            logger.debug(f"Optional configuration file not found: {file_path}")
            return {}

        try:
            with open(file_path, "r") as f:
                data = yaml.safe_load(f) or {}
            self._loaded_files[filename] = file_path.stat().st_mtime
            logger.debug(f"Loaded {filename}: {len(str(data))} bytes")
            return data
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Failed to parse {filename}: {e}") from e
        except IOError as e:
            raise IOError(f"Failed to read {filename}: {e}") from e

    def _load_watchlist(self, filename: str, required: bool = True) -> List[str]:
        """
        Load watchlist from text file.

        Expected format: One ticker symbol per line, comments start with #

        Args:
            filename: Name of the watchlist file
            required: Whether file must exist

        Returns:
            List of ticker symbols

        Raises:
            FileNotFoundError: If required file doesn't exist
        """
        file_path = self.config_dir / filename
        if not file_path.exists():
            if required:
                raise FileNotFoundError(f"Required watchlist file not found: {file_path}")
            logger.debug(f"Optional watchlist file not found: {file_path}")
            return []

        try:
            with open(file_path, "r") as f:
                lines = f.readlines()

            symbols = []
            for line in lines:
                # Remove comments and whitespace
                line = line.split("#")[0].strip()
                if line:  # Skip empty lines
                    symbols.append(line.upper())

            self._loaded_files[filename] = file_path.stat().st_mtime
            logger.debug(f"Loaded {len(symbols)} symbols from watchlist")
            return symbols
        except IOError as e:
            raise IOError(f"Failed to read {filename}: {e}") from e

    def _load_theses(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all trading thesis files from theses/ directory.

        Files should be named: thesis_name.yaml
        Each thesis becomes: theses["thesis_name"] = {...}

        Returns:
            Dictionary of loaded theses (empty dict if no theses found)
        """
        theses_dir = self.config_dir / "theses"
        if not theses_dir.exists():
            logger.debug("Theses directory not found")
            return {}

        theses = {}
        try:
            for thesis_file in theses_dir.glob("*.yaml"):
                thesis_name = thesis_file.stem  # filename without extension
                with open(thesis_file, "r") as f:
                    thesis_data = yaml.safe_load(f) or {}
                theses[thesis_name] = thesis_data
                self._loaded_files[f"theses/{thesis_file.name}"] = thesis_file.stat().st_mtime

            if theses:
                logger.debug(f"Loaded {len(theses)} theses from theses/ directory")
            return theses
        except Exception as e:
            logger.warning(f"Failed to load theses: {e}")
            return {}

    def _deep_merge(
        self, base: Dict[str, Any], updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Deep merge updates into base dictionary.

        Nested dictionaries are recursively merged. Lists are replaced, not merged.

        Args:
            base: Base dictionary
            updates: Dictionary of updates

        Returns:
            Merged dictionary
        """
        result = base.copy()
        for key, value in updates.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _compute_config_hash(self) -> None:
        """
        Compute hash of current configuration.

        Hash is computed from configuration dictionary and loaded file mtimes.
        Changes when any configuration changes.
        """
        hash_input = {
            "config": json.dumps(self._config.dict(), sort_keys=True, default=str),
            "files": sorted(
                [(k, v) for k, v in self._loaded_files.items()], key=lambda x: x[0]
            ),
        }
        hash_bytes = json.dumps(hash_input, sort_keys=True).encode("utf-8")
        self._config_hash = hashlib.sha256(hash_bytes).hexdigest()
        logger.debug(f"Configuration hash: {self._config_hash[:16]}...")

    def compute_config_hash_for_scan_metadata(self) -> str:
        """
        Get configuration hash for scan metadata.

        Used in scan results to identify which configuration was used.
        Helps track configuration changes over time.

        Returns:
            Configuration hash
        """
        return self._config_hash

    def has_changed(self) -> bool:
        """
        Check if configuration files have been modified on disk.

        Compares current file modification times with loaded times.
        Does NOT reload configuration automatically.

        Returns:
            True if any configuration file has changed
        """
        try:
            for filename in self._loaded_files.keys():
                file_path = self.config_dir / filename
                if not file_path.exists():
                    return True  # File was deleted
                if file_path.stat().st_mtime != self._loaded_files[filename]:
                    logger.info(f"Configuration file changed: {filename}")
                    return True
            return False
        except Exception as e:
            logger.warning(f"Failed to check configuration change: {e}")
            return False


@lru_cache(maxsize=1)
def get_config_manager(config_dir: Optional[Path] = None) -> ConfigManager:
    """
    Get the singleton ConfigManager instance.

    This function uses LRU cache to ensure only one instance is created.
    Additional calls return the cached instance.

    Args:
        config_dir: Configuration directory (only used on first call)

    Returns:
        Singleton ConfigManager instance

    Example:
        from functions.config.loader import get_config_manager

        config_mgr = get_config_manager()
        config = config_mgr.config
        print(config.scan.symbols)
    """
    return ConfigManager.get_instance(config_dir)


def get_config(config_dir: Optional[Path] = None) -> AppConfig:
    """
    Convenience function to get application configuration directly.

    Args:
        config_dir: Configuration directory (optional)

    Returns:
        Current AppConfig instance

    Example:
        from functions.config.loader import get_config

        config = get_config()
        print(config.scan.symbols)
    """
    return get_config_manager(config_dir).config
