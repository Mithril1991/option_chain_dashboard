"""
Pydantic-based settings configuration for the Option Chain Dashboard.

Loads configuration from environment variables (.env file) and provides
a singleton instance for application-wide access.

Configuration hierarchy (highest to lowest priority):
1. Environment variables
2. .env file
3. Hardcoded defaults

Usage:
    from functions.config.settings import get_settings

    settings = get_settings()
    print(settings.backend_url)
    print(settings.log_level)
"""

from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.

    All settings are validated at initialization time. Optional settings can be None.

    Attributes:
        demo_mode: Use simulated data instead of real Yahoo Finance data
        backend_url: Base URL of the backend API server
        log_level: Logging verbosity level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        anthropic_api_key: Optional API key for Claude LLM
        openai_api_key: Optional API key for OpenAI LLM
        risk_free_rate: Annual risk-free rate for options pricing (0.05 = 5%)
        cache_ttl_minutes: Cache duration for market data in minutes
        intraday_cache_ttl_minutes: Cache duration for intraday data in minutes
    """

    # ========================================================================
    # Application Mode
    # ========================================================================
    demo_mode: bool = True
    """Use simulated data for testing/demo mode. Default: True"""

    # ========================================================================
    # Server Configuration
    # ========================================================================
    backend_url: str = "http://192.168.1.16:8061"
    """Base URL of the backend API server. Default: http://192.168.1.16:8061"""

    # ========================================================================
    # Logging Configuration
    # ========================================================================
    log_level: str = "INFO"
    """Logging verbosity. Default: INFO"""

    # ========================================================================
    # LLM Integration (Optional)
    # ========================================================================
    anthropic_api_key: Optional[str] = None
    """Optional API key for Claude LLM"""

    openai_api_key: Optional[str] = None
    """Optional API key for OpenAI LLM"""

    # ========================================================================
    # Financial Calculations
    # ========================================================================
    risk_free_rate: float = 0.05
    """Annual risk-free rate for options pricing. Default: 0.05 (5%)"""

    # ========================================================================
    # Cache Configuration
    # ========================================================================
    cache_ttl_minutes: int = 60
    """Cache duration for historical market data in minutes. Default: 60"""

    intraday_cache_ttl_minutes: int = 5
    """Cache duration for intraday market data in minutes. Default: 5"""

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        case_sensitive = False
        # Allow extra environment variables but don't fail
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get the singleton Settings instance.

    Returns cached instance on subsequent calls. This ensures that settings
    are loaded once and reused throughout the application.

    Returns:
        Singleton Settings instance

    Example:
        settings = get_settings()
        print(settings.backend_url)

    Note:
        To reset the cache (mainly for testing), use:
        get_settings.cache_clear()
    """
    return Settings()


def reload_settings() -> Settings:
    """
    Force reload of settings from environment.

    Clears the singleton cache and returns a fresh Settings instance.
    Useful for testing or when environment variables change at runtime.

    Returns:
        Fresh Settings instance

    Warning:
        This operation is not thread-safe. Only use in single-threaded
        contexts or ensure proper synchronization.
    """
    get_settings.cache_clear()
    return get_settings()
