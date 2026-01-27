"""
Pydantic models for configuration file (config.yaml) structure.

These models validate and parse the YAML configuration file, ensuring
all required fields are present and properly typed.

Configuration File Structure:
    config.yaml (main configuration)
    watchlist.txt (list of ticker symbols)
    account.yaml (account-specific settings)
    theses/ (directory of thesis YAML files)

Usage:
    from functions.config.models import AppConfig
    import yaml

    with open("config.yaml") as f:
        config_data = yaml.safe_load(f)

    config = AppConfig(**config_data)
    print(config.scan.symbols)
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator


# ============================================================================
# Liquidity Filter Configuration
# ============================================================================
class LiquidityFilterConfig(BaseModel):
    """Configuration for option liquidity filtering."""

    min_bid_ask_spread_pct: float = Field(
        default=1.0, description="Maximum bid-ask spread as % of mid-price"
    )
    min_option_volume: int = Field(
        default=10, description="Minimum daily option volume required"
    )
    min_open_interest: int = Field(
        default=50, description="Minimum open interest required"
    )

    class Config:
        extra = "allow"


# ============================================================================
# Technical Analysis Configuration
# ============================================================================
class TechnicalsConfig(BaseModel):
    """Configuration for technical analysis indicators."""

    sma_periods: List[int] = Field(
        default=[20, 50, 200], description="Simple Moving Average periods"
    )
    rsi_period: int = Field(default=14, description="RSI (Relative Strength Index) period")
    rsi_overbought: float = Field(default=70.0, description="RSI overbought threshold")
    rsi_oversold: float = Field(default=30.0, description="RSI oversold threshold")
    macd_fast: int = Field(default=12, description="MACD fast EMA period")
    macd_slow: int = Field(default=26, description="MACD slow EMA period")
    macd_signal: int = Field(default=9, description="MACD signal line period")
    atr_period: int = Field(default=14, description="ATR (Average True Range) period")

    class Config:
        extra = "allow"


# ============================================================================
# Options Chain Configuration
# ============================================================================
class OptionsConfig(BaseModel):
    """Configuration for options chain filtering and analysis."""

    dte_min: int = Field(default=7, description="Minimum days to expiration")
    dte_max: int = Field(default=60, description="Maximum days to expiration")
    strike_delta_min: float = Field(
        default=0.15, description="Minimum delta for ATM strikes"
    )
    strike_delta_max: float = Field(
        default=0.85, description="Maximum delta for ATM strikes"
    )
    volume_threshold: int = Field(
        default=20, description="Minimum daily volume"
    )
    open_interest_threshold: int = Field(
        default=100, description="Minimum open interest"
    )

    class Config:
        extra = "allow"


# ============================================================================
# Anomaly/Pattern Detection Configuration
# ============================================================================
class DetectorsEnabledConfig(BaseModel):
    """Which anomaly detectors to enable."""

    volume_spike: bool = Field(default=True, description="Enable volume spike detection")
    volatility_expansion: bool = Field(
        default=True, description="Enable volatility expansion detection"
    )
    unusual_activity: bool = Field(
        default=True, description="Enable unusual activity detection"
    )
    put_call_ratio_anomaly: bool = Field(
        default=True, description="Enable put/call ratio anomaly detection"
    )

    class Config:
        extra = "allow"


class DetectorThresholdsConfig(BaseModel):
    """Thresholds for anomaly detectors."""

    volume_spike_pct: float = Field(
        default=150.0, description="Volume spike threshold as % of average"
    )
    volatility_expansion_pct: float = Field(
        default=25.0, description="Volatility expansion threshold as %"
    )
    unusual_activity_zscore: float = Field(
        default=2.5, description="Z-score threshold for unusual activity"
    )
    put_call_ratio_threshold: float = Field(
        default=1.5, description="Put/call ratio threshold"
    )

    class Config:
        extra = "allow"


# ============================================================================
# Scoring Configuration
# ============================================================================
class ScoringConfig(BaseModel):
    """Configuration for opportunity scoring and ranking."""

    # Weighting for different factors (should sum to ~100)
    probability_weight: float = Field(
        default=0.30, description="Weight for success probability"
    )
    liquidity_weight: float = Field(
        default=0.20, description="Weight for liquidity quality"
    )
    volatility_weight: float = Field(
        default=0.25, description="Weight for volatility metrics"
    )
    risk_reward_weight: float = Field(
        default=0.25, description="Weight for risk/reward ratio"
    )

    # Minimum thresholds for opportunities
    min_probability: float = Field(
        default=0.55, description="Minimum success probability"
    )
    min_risk_reward_ratio: float = Field(
        default=1.5, description="Minimum risk/reward ratio"
    )

    class Config:
        extra = "allow"


# ============================================================================
# Risk Management Configuration
# ============================================================================
class RiskGateConfig(BaseModel):
    """Configuration for risk management gates and limits."""

    max_position_size_pct: float = Field(
        default=2.0, description="Maximum position size as % of portfolio"
    )
    max_portfolio_risk_pct: float = Field(
        default=5.0, description="Maximum portfolio risk as %"
    )
    stop_loss_pct: float = Field(
        default=50.0, description="Stop loss threshold as % of premium paid"
    )
    profit_target_pct: float = Field(
        default=75.0, description="Profit target as % of max profit"
    )

    class Config:
        extra = "allow"


# ============================================================================
# Alerting Configuration
# ============================================================================
class AlertingConfig(BaseModel):
    """Configuration for alerts and notifications."""

    enabled: bool = Field(default=True, description="Enable alerts")
    alert_on_new_opportunities: bool = Field(
        default=True, description="Alert on new high-quality opportunities"
    )
    alert_on_risk_breach: bool = Field(
        default=True, description="Alert when risk limits are breached"
    )
    alert_on_anomalies: bool = Field(
        default=True, description="Alert on detected anomalies"
    )
    min_score_threshold: float = Field(
        default=0.70, description="Minimum score to trigger alert"
    )

    class Config:
        extra = "allow"


# ============================================================================
# Scan Configuration
# ============================================================================
class ScanConfig(BaseModel):
    """Configuration for market scanning parameters."""

    symbols: List[str] = Field(
        default=[], description="List of ticker symbols to scan"
    )
    update_interval_minutes: int = Field(
        default=5, description="Update interval for scans in minutes"
    )
    max_retries: int = Field(
        default=3, description="Maximum retries for failed requests"
    )
    retry_delay_seconds: int = Field(
        default=5, description="Delay between retries in seconds"
    )

    liquidity: LiquidityFilterConfig = Field(
        default_factory=LiquidityFilterConfig, description="Liquidity filter settings"
    )
    technicals: TechnicalsConfig = Field(
        default_factory=TechnicalsConfig, description="Technical analysis settings"
    )
    options: OptionsConfig = Field(
        default_factory=OptionsConfig, description="Options chain settings"
    )

    class Config:
        extra = "allow"


# ============================================================================
# Main Application Configuration
# ============================================================================
class AppConfig(BaseModel):
    """
    Main application configuration.

    This is the top-level configuration model that encompasses all
    application settings.
    """

    version: str = Field(default="1.0.0", description="Configuration version")
    app_name: str = Field(
        default="Option Chain Dashboard", description="Application name"
    )

    scan: ScanConfig = Field(
        default_factory=ScanConfig, description="Market scanning configuration"
    )
    detectors: DetectorsEnabledConfig = Field(
        default_factory=DetectorsEnabledConfig, description="Detector settings"
    )
    detector_thresholds: DetectorThresholdsConfig = Field(
        default_factory=DetectorThresholdsConfig, description="Detector thresholds"
    )
    scoring: ScoringConfig = Field(
        default_factory=ScoringConfig, description="Scoring configuration"
    )
    risk_gates: RiskGateConfig = Field(
        default_factory=RiskGateConfig, description="Risk management configuration"
    )
    alerting: AlertingConfig = Field(
        default_factory=AlertingConfig, description="Alerting configuration"
    )

    # Allow extra fields for extensibility
    class Config:
        extra = "allow"

    @validator("version")
    def validate_version(cls, v):
        """Ensure version follows semantic versioning."""
        parts = v.split(".")
        if len(parts) < 2:
            raise ValueError("Version must be in format X.Y or X.Y.Z")
        return v
