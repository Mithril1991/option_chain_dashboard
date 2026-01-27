"""
Feature computation orchestrator for options chain analysis.

This module provides the FeatureSet dataclass and compute_features() function
to extract and compute all technical, volatility, and options-based features
from market data snapshots.

The feature engine serves as the central hub for feature engineering, taking
raw market data and producing a comprehensive feature set for downstream
scoring, detection, and strategy modules.

Models:
    - FeatureSet: Comprehensive dataclass containing all computed features
    - Includes price data, technicals, volatility, options metrics, and liquidity info

Functions:
    - compute_features(): Main orchestrator that computes all features from a snapshot
    - convert_numpy_types(): Recursively converts NumPy types to native Python types
    - to_dict() on FeatureSet: Converts feature set to JSON-serializable dict

Usage:
    from functions.market.models import MarketSnapshot
    from functions.compute.feature_engine import compute_features
    from datetime import datetime, timezone

    # Assume we have a snapshot from market data provider
    snapshot = MarketSnapshot(...)

    # Compute features
    features = compute_features(snapshot, config_hash="v1_baseline")

    # Convert to dict for JSON serialization
    features_dict = features.to_dict()
    print(features_dict["ticker"])
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timezone
from typing import Optional, Any, Dict, List
import numpy as np

from functions.util.logging_setup import get_logger
from functions.config.settings import get_settings
from functions.market.models import MarketSnapshot, OptionsChain

logger = get_logger(__name__)


# ============================================================================
# TYPE CONVERTERS
# ============================================================================


def convert_numpy_types(obj: Any) -> Any:
    """
    Recursively convert NumPy types to native Python types for JSON serialization.

    Handles conversion of:
    - np.float64 -> float
    - np.int64 -> int
    - np.bool_ -> bool
    - np.ndarray -> list
    - dict, list, tuple recursively
    - Other types pass through unchanged

    Args:
        obj: The object to convert (can be scalar, dict, list, or tuple)

    Returns:
        The converted object with all NumPy types replaced by native Python types

    Raises:
        None - all conversions are graceful with no exceptions

    Example:
        >>> result = convert_numpy_types({
        ...     "delta": np.float64(0.5),
        ...     "count": np.int64(100),
        ...     "values": np.array([1.0, 2.0, 3.0])
        ... })
        >>> type(result["delta"])
        <class 'float'>
        >>> type(result["count"])
        <class 'int'>
        >>> type(result["values"])
        <class 'list'>
    """
    # Handle NumPy scalar types
    if isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()

    # Handle collections recursively
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        converted = [convert_numpy_types(item) for item in obj]
        return converted if isinstance(obj, list) else tuple(converted)

    # Pass through other types unchanged
    else:
        return obj


# ============================================================================
# FEATURE SET DATACLASS
# ============================================================================


@dataclass
class FeatureSet:
    """
    Comprehensive feature set for a single ticker at a point in time.

    This dataclass aggregates all computed features from market data including
    price information, technical indicators, volatility metrics, options Greeks,
    IV analytics, liquidity metrics, and earnings calendar data.

    Attributes:
        identifier:
            ticker (str): Stock ticker symbol (e.g., "AAPL")
            timestamp (datetime): UTC timestamp when snapshot was captured

        price_data:
            price (float): Current stock price
            price_change_1d (Optional[float]): 1-day price change percentage
            price_change_5d (Optional[float]): 5-day price change percentage

        technicals (Dict[str, Any]):
            SMA indicators: sma_20, sma_50, sma_200 (simple moving averages)
            EMA indicators: ema_9, ema_21 (exponential moving averages)
            Oscillators: rsi (relative strength index), macd (moving avg convergence)
            Support/Resistance: fib_levels (Fibonacci retracement levels dict)
            Volume metrics: volume_sma_20, volume_trend, volume_ratio
            Breakout levels: resistance_20d, support_20d, breakout_level

        volatility (Dict[str, Any]):
            Historical: hv_10, hv_20, hv_60 (historical volatility)
            Alternative: parkinson, garman_klass (alternative vol estimators)
            Regime: vol_regime_ratio (current_vol / median_vol), vol_trend
            All as floating-point decimals (0.25 = 25%)

        options_front (Dict[str, Any]):
            For front-month (soonest) options expiration:
            dte (int): Days to expiration
            atm_iv (float): At-the-money implied volatility
            greeks (dict): delta, gamma, theta, vega, rho
            volume (int): Total ATM volume
            oi (int): Total ATM open interest
            spread_pct (float): ATM bid-ask spread percentage
            implied_move (float): Absolute $ implied move from options pricing

        options_back (Dict[str, Any]):
            Same structure as options_front for back-month expiration

        term_structure (Dict[str, Any]):
            iv_ratio (float): Front IV / Back IV ratio
            iv_diff (float): Front IV - Back IV (basis points or decimals)
            implied_move_front (float): Front month implied move
            implied_move_back (float): Back month implied move

        iv_metrics (Dict[str, Any]):
            iv_percentile (float): Percentile of current IV vs historical (0-100)
            iv_rank (float): Rank of current IV vs historical (0-1.0)
            iv_low (float): 52-week IV low
            iv_high (float): 52-week IV high

        liquidity (Dict[str, Any]):
            passes_filter (bool): Whether ticker passes liquidity requirements
            issues (List[str]): Reasons ticker failed filter if applicable
            adv_usd (float): Average daily volume in USD ($)
            atm_oi (int): ATM open interest
            atm_volume (int): ATM daily volume

        earnings (Dict[str, Any]):
            days_to_earnings (Optional[int]): Days until next earnings, or None
            earnings_date (Optional[date]): Next earnings date, or None

        config:
            config_hash (str): Hash/version of configuration used to compute features
    """

    # ========================================================================
    # IDENTIFIER
    # ========================================================================
    ticker: str  # Stock ticker symbol (e.g., "AAPL")
    timestamp: datetime  # UTC timestamp when snapshot was captured

    # ========================================================================
    # PRICE DATA
    # ========================================================================
    price: float  # Current stock price
    price_change_1d: Optional[float] = None  # 1-day price change percentage
    price_change_5d: Optional[float] = None  # 5-day price change percentage

    # ========================================================================
    # TECHNICAL INDICATORS
    # ========================================================================
    technicals: Dict[str, Any] = field(default_factory=dict)
    # Technical indicators: SMA, EMA, RSI, MACD, Fibonacci, volume, breakouts

    # ========================================================================
    # VOLATILITY METRICS
    # ========================================================================
    volatility: Dict[str, Any] = field(default_factory=dict)
    # Volatility: historical vol, Parkinson, Garman-Klass, regime, trend

    # ========================================================================
    # OPTIONS CHAIN - FRONT MONTH
    # ========================================================================
    options_front: Dict[str, Any] = field(default_factory=dict)
    # Front-month options metrics: IV, Greeks, volume, OI, spreads, implied move

    # ========================================================================
    # OPTIONS CHAIN - BACK MONTH
    # ========================================================================
    options_back: Dict[str, Any] = field(default_factory=dict)
    # Back-month options metrics: IV, Greeks, volume, OI, spreads, implied move

    # ========================================================================
    # TERM STRUCTURE
    # ========================================================================
    term_structure: Dict[str, Any] = field(default_factory=dict)
    # IV term structure and implied move ratios between front/back

    # ========================================================================
    # IV ANALYTICS
    # ========================================================================
    iv_metrics: Dict[str, Any] = field(default_factory=dict)
    # IV percentile, rank, historical low/high

    # ========================================================================
    # LIQUIDITY
    # ========================================================================
    liquidity: Dict[str, Any] = field(default_factory=dict)
    # Liquidity metrics: filter status, ADV, ATM OI/volume, issues

    # ========================================================================
    # EARNINGS
    # ========================================================================
    earnings: Dict[str, Any] = field(default_factory=dict)
    # Earnings information: days to next earnings, earnings date

    # ========================================================================
    # CONFIGURATION
    # ========================================================================
    config_hash: str = field(default="")  # Hash/version of configuration used to compute features

    def __post_init__(self) -> None:
        """
        Validate FeatureSet after initialization.

        Ensures:
        - Timestamp is in UTC
        - Ticker is uppercase
        - Price is positive
        - Dictionaries are not None
        - All NumPy types are converted to native Python types

        Raises:
            ValueError: If any validation fails
        """
        # Validate ticker
        if not self.ticker or not isinstance(self.ticker, str):
            raise ValueError(f"ticker must be non-empty string, got {self.ticker}")
        self.ticker = self.ticker.upper()

        # Validate timestamp is UTC
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must have UTC timezone")
        if self.timestamp.tzinfo != timezone.utc:
            raise ValueError("timestamp must be in UTC timezone")

        # Validate price is positive
        if not isinstance(self.price, (int, float)) or self.price <= 0:
            raise ValueError(f"price must be positive number, got {self.price}")

        # Validate dictionaries are initialized
        if self.technicals is None:
            self.technicals = {}
        if self.volatility is None:
            self.volatility = {}
        if self.options_front is None:
            self.options_front = {}
        if self.options_back is None:
            self.options_back = {}
        if self.term_structure is None:
            self.term_structure = {}
        if self.iv_metrics is None:
            self.iv_metrics = {}
        if self.liquidity is None:
            self.liquidity = {}
        if self.earnings is None:
            self.earnings = {}

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert FeatureSet to JSON-serializable dictionary.

        Recursively converts all nested dictionaries and lists, ensuring
        all NumPy types are converted to native Python types for clean
        JSON serialization.

        All datetime objects are converted to ISO format strings with 'Z' suffix.
        All date objects are converted to ISO format strings (YYYY-MM-DD).

        Returns:
            Dictionary representation of FeatureSet with all values JSON-serializable

        Example:
            >>> features = FeatureSet(...)
            >>> features_dict = features.to_dict()
            >>> import json
            >>> json_str = json.dumps(features_dict)  # No errors
        """
        # Convert to dict using dataclass asdict
        result = asdict(self)

        # Convert datetime objects to ISO format strings
        if isinstance(result["timestamp"], datetime):
            result["timestamp"] = result["timestamp"].isoformat() + "Z"

        # Convert date objects to ISO format strings
        earnings = result.get("earnings", {})
        if isinstance(earnings, dict) and "earnings_date" in earnings:
            if isinstance(earnings["earnings_date"], date):
                earnings["earnings_date"] = earnings["earnings_date"].isoformat()

        # Recursively convert all NumPy types
        result = convert_numpy_types(result)

        return result


# ============================================================================
# MAIN FEATURE COMPUTATION
# ============================================================================


def compute_features(snapshot: MarketSnapshot, config_hash: str) -> FeatureSet:
    """
    Compute comprehensive feature set from a market data snapshot.

    This orchestrator function takes raw market data and computes all technical,
    volatility, and options-based features needed for downstream analysis.

    High-level workflow:
    1. Extract basic price and identifier information
    2. Compute technical indicators (SMA, EMA, RSI, MACD, Fibonacci, volume)
    3. Compute volatility metrics (historical, Parkinson, Garman-Klass, regime)
    4. Extract options Greeks from front and back month chains
    5. Compute IV percentile and rank
    6. Liquidity filter assessment
    7. Estimate earnings dates (stub for now)
    8. Package into FeatureSet

    Args:
        snapshot (MarketSnapshot): Complete market data snapshot containing:
            - ticker: Stock symbol
            - timestamp: Current time (UTC)
            - price: Current stock price
            - price_history: List of historical PriceBar objects
            - options_chains: Dict mapping expiration dates to OptionsChain objects

        config_hash (str): Hash or version string of configuration used.
            Allows tracking which configuration was used for features.
            Example: "v1_baseline", "prod_20260115", or actual hash

    Returns:
        FeatureSet: Complete feature set with all computed metrics

    Raises:
        ValueError: If snapshot is invalid or missing required data
        KeyError: If expected fields are missing from snapshot or chains
        TypeError: If data types are incompatible

    Example:
        >>> from functions.market.models import MarketSnapshot
        >>> from datetime import datetime, timezone
        >>>
        >>> snapshot = MarketSnapshot(
        ...     ticker="AAPL",
        ...     timestamp=datetime.now(timezone.utc),
        ...     price=150.0,
        ...     price_history=[...],  # List of PriceBar objects
        ...     options_chains={...}   # Dict of OptionsChain objects
        ... )
        >>>
        >>> features = compute_features(snapshot, config_hash="v1_baseline")
        >>> print(f"Computed features for {features.ticker}")
        >>> print(f"Price: ${features.price}")
        >>> print(f"RSI: {features.technicals.get('rsi')}")

    Note:
        - All prices are in the asset's native currency
        - All volatilities are decimals (0.25 = 25%)
        - All IV metrics use decimal format
        - Timestamps are always UTC
        - Missing optional data returns None or empty dicts gracefully
    """
    logger.info(f"Computing features for {snapshot.ticker} at {snapshot.timestamp}")

    settings = get_settings()

    try:
        # ====================================================================
        # EXTRACT BASIC INFORMATION
        # ====================================================================
        ticker = snapshot.ticker
        timestamp = snapshot.timestamp
        current_price = snapshot.price

        logger.debug(f"Processing {ticker} at price ${current_price}")

        # ====================================================================
        # COMPUTE PRICE CHANGES
        # ====================================================================
        price_change_1d = None
        price_change_5d = None

        if snapshot.price_history:
            # 1-day price change
            if len(snapshot.price_history) >= 2:
                latest_bar = snapshot.price_history[-1]
                prev_bar = snapshot.price_history[-2] if len(snapshot.price_history) >= 2 else None
                if prev_bar:
                    price_change_1d = ((latest_bar.close - prev_bar.close) / prev_bar.close) * 100

            # 5-day price change
            if len(snapshot.price_history) >= 5:
                bar_5d_ago = snapshot.price_history[-5]
                latest_bar = snapshot.price_history[-1]
                price_change_5d = ((latest_bar.close - bar_5d_ago.close) / bar_5d_ago.close) * 100

        # ====================================================================
        # COMPUTE TECHNICAL INDICATORS
        # ====================================================================
        technicals = _compute_technicals(snapshot.price_history, current_price)
        logger.debug(f"Computed technicals: {list(technicals.keys())}")

        # ====================================================================
        # COMPUTE VOLATILITY METRICS
        # ====================================================================
        volatility = _compute_volatility(snapshot.price_history, current_price)
        logger.debug(f"Computed volatility: {list(volatility.keys())}")

        # ====================================================================
        # EXTRACT OPTIONS CHAINS - FRONT AND BACK MONTH
        # ====================================================================
        options_front = {}
        options_back = {}
        term_structure = {}

        if snapshot.options_chains:
            sorted_expirations = sorted(snapshot.options_chains.keys())
            logger.debug(f"Found {len(sorted_expirations)} options expirations")

            if len(sorted_expirations) >= 1:
                front_chain = snapshot.options_chains[sorted_expirations[0]]
                options_front = _extract_options_metrics(
                    front_chain, current_price, "front"
                )

            if len(sorted_expirations) >= 2:
                back_chain = snapshot.options_chains[sorted_expirations[1]]
                options_back = _extract_options_metrics(back_chain, current_price, "back")

                # Compute term structure only if both chains exist
                if options_front and options_back:
                    term_structure = _compute_term_structure(
                        options_front, options_back
                    )

        # ====================================================================
        # COMPUTE IV METRICS
        # ====================================================================
        iv_metrics = _compute_iv_metrics(snapshot.options_chains, options_front)
        logger.debug(f"Computed IV metrics: {list(iv_metrics.keys())}")

        # ====================================================================
        # LIQUIDITY ASSESSMENT
        # ====================================================================
        liquidity = _assess_liquidity(snapshot, options_front)
        logger.debug(f"Liquidity assessment: passes_filter={liquidity.get('passes_filter')}")

        # ====================================================================
        # EARNINGS INFORMATION
        # ====================================================================
        earnings = _extract_earnings_info(snapshot)
        logger.debug(f"Earnings info: {earnings}")

        # ====================================================================
        # CREATE FEATURE SET
        # ====================================================================
        feature_set = FeatureSet(
            ticker=ticker,
            timestamp=timestamp,
            price=current_price,
            price_change_1d=price_change_1d,
            price_change_5d=price_change_5d,
            technicals=technicals,
            volatility=volatility,
            options_front=options_front,
            options_back=options_back,
            term_structure=term_structure,
            iv_metrics=iv_metrics,
            liquidity=liquidity,
            earnings=earnings,
            config_hash=config_hash,
        )

        logger.info(f"Successfully computed features for {ticker}")
        return feature_set

    except Exception as e:
        logger.error(f"Failed to compute features for {snapshot.ticker}: {e}", exc_info=True)
        raise


# ============================================================================
# HELPER FUNCTIONS - TECHNICAL INDICATORS
# ============================================================================


def _compute_technicals(
    price_history: List, current_price: float
) -> Dict[str, Any]:
    """
    Compute technical indicators from price history.

    Args:
        price_history: List of PriceBar objects (ordered chronologically)
        current_price: Current stock price

    Returns:
        Dictionary containing: sma_20, sma_50, sma_200, ema_9, ema_21,
        rsi, macd, fib_levels, volume metrics, and breakout levels
    """
    technicals = {}

    if not price_history:
        logger.debug("No price history available for technicals")
        return technicals

    try:
        # Convert to DataFrame for easier calculation
        closes = [bar.close for bar in price_history]
        volumes = [bar.volume for bar in price_history]

        # Simple Moving Averages
        if len(closes) >= 20:
            technicals["sma_20"] = float(np.mean(closes[-20:]))
        if len(closes) >= 50:
            technicals["sma_50"] = float(np.mean(closes[-50:]))
        if len(closes) >= 200:
            technicals["sma_200"] = float(np.mean(closes[-200:]))

        # Exponential Moving Averages (simplified: not true EMA for now)
        if len(closes) >= 9:
            technicals["ema_9"] = float(np.mean(closes[-9:]))
        if len(closes) >= 21:
            technicals["ema_21"] = float(np.mean(closes[-21:]))

        # RSI (Relative Strength Index) - simplified calculation
        if len(closes) >= 14:
            deltas = np.diff(closes[-14:])
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains) if np.mean(gains) > 0 else 0.0001
            avg_loss = np.mean(losses) if np.mean(losses) > 0 else 0.0001
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            technicals["rsi"] = float(rsi)

        # MACD (simplified)
        if len(closes) >= 26:
            ema_12 = np.mean(closes[-12:])
            ema_26 = np.mean(closes[-26:])
            macd = float(ema_12 - ema_26)
            technicals["macd"] = macd

        # Fibonacci Levels (based on 20-day high/low)
        if len(price_history) >= 20:
            bars_20d = price_history[-20:]
            high_20d = max(bar.high for bar in bars_20d)
            low_20d = min(bar.low for bar in bars_20d)
            diff = high_20d - low_20d
            technicals["fib_levels"] = {
                "level_0": float(low_20d),
                "level_0.236": float(low_20d + diff * 0.236),
                "level_0.382": float(low_20d + diff * 0.382),
                "level_0.5": float(low_20d + diff * 0.5),
                "level_0.618": float(low_20d + diff * 0.618),
                "level_1.0": float(high_20d),
            }

        # Volume metrics
        if volumes:
            avg_volume = np.mean(volumes)
            current_volume = volumes[-1] if volumes else 0
            technicals["volume_sma_20"] = float(np.mean(volumes[-20:]) if len(volumes) >= 20 else avg_volume)
            if avg_volume > 0:
                technicals["volume_ratio"] = float(current_volume / avg_volume)
            technicals["volume_trend"] = "increasing" if current_volume > avg_volume else "decreasing"

        # Support and Resistance (20-day high/low)
        if len(price_history) >= 20:
            bars_20d = price_history[-20:]
            technicals["resistance_20d"] = float(max(bar.high for bar in bars_20d))
            technicals["support_20d"] = float(min(bar.low for bar in bars_20d))

            # Simple breakout level check
            if current_price > technicals["resistance_20d"]:
                technicals["breakout_level"] = "above_resistance"
            elif current_price < technicals["support_20d"]:
                technicals["breakout_level"] = "below_support"
            else:
                technicals["breakout_level"] = "inside_range"

        logger.debug(f"Computed {len(technicals)} technical indicators")

    except Exception as e:
        logger.warning(f"Error computing technicals: {e}")

    return technicals


# ============================================================================
# HELPER FUNCTIONS - VOLATILITY METRICS
# ============================================================================


def _compute_volatility(price_history: List, current_price: float) -> Dict[str, Any]:
    """
    Compute volatility metrics from price history.

    Args:
        price_history: List of PriceBar objects
        current_price: Current stock price

    Returns:
        Dictionary containing: hv_10, hv_20, hv_60, parkinson,
        garman_klass, vol_regime_ratio, vol_trend
    """
    volatility = {}

    if not price_history:
        logger.debug("No price history available for volatility")
        return volatility

    try:
        closes = np.array([bar.close for bar in price_history])

        # Historical Volatility (standard deviation of returns)
        if len(closes) >= 10:
            returns_10 = np.diff(np.log(closes[-10:])) * 100
            hv_10 = float(np.std(returns_10) / 100)  # Normalize to decimal
            volatility["hv_10"] = hv_10

        if len(closes) >= 20:
            returns_20 = np.diff(np.log(closes[-20:])) * 100
            hv_20 = float(np.std(returns_20) / 100)
            volatility["hv_20"] = hv_20

        if len(closes) >= 60:
            returns_60 = np.diff(np.log(closes[-60:])) * 100
            hv_60 = float(np.std(returns_60) / 100)
            volatility["hv_60"] = hv_60

        # Parkinson Volatility (uses high/low)
        if len(price_history) >= 20:
            bars = price_history[-20:]
            hl_ratio = np.array([np.log(bar.high / bar.low) for bar in bars])
            parkinson = float(np.sqrt(np.mean(hl_ratio ** 2) / (4 * np.log(2))) / 100)
            volatility["parkinson"] = parkinson

        # Garman-Klass Volatility (uses OHLC)
        if len(price_history) >= 20:
            bars = price_history[-20:]
            gk_values = []
            for bar in bars:
                if bar.close > 0 and bar.open > 0:
                    hl = np.log(bar.high / bar.low) ** 2
                    co = np.log(bar.close / bar.open) ** 2
                    gk_values.append(0.5 * hl - (2 * np.log(2) - 1) * co)
            if gk_values:
                garman_klass = float(np.sqrt(np.mean(gk_values)) / 100)
                volatility["garman_klass"] = garman_klass

        # Volatility Regime (current vs median)
        if "hv_20" in volatility:
            if len(closes) >= 60:
                returns_60 = np.diff(np.log(closes[-60:])) * 100
                median_vol_60 = float(np.median(np.abs(returns_60)) / 100)
                if median_vol_60 > 0:
                    volatility["vol_regime_ratio"] = volatility["hv_20"] / median_vol_60
                    # Trend: compare hv_20 with hv_10
                    if "hv_10" in volatility:
                        if volatility["hv_20"] > volatility["hv_10"]:
                            volatility["vol_trend"] = "increasing"
                        else:
                            volatility["vol_trend"] = "decreasing"

        logger.debug(f"Computed {len(volatility)} volatility metrics")

    except Exception as e:
        logger.warning(f"Error computing volatility: {e}")

    return volatility


# ============================================================================
# HELPER FUNCTIONS - OPTIONS METRICS
# ============================================================================


def _extract_options_metrics(
    chain: OptionsChain, current_price: float, position: str = "front"
) -> Dict[str, Any]:
    """
    Extract options metrics from an options chain.

    Args:
        chain: OptionsChain object for a single expiration
        current_price: Current underlying price
        position: "front" or "back" for logging

    Returns:
        Dictionary with: dte, atm_iv, greeks, volume, oi, spread_pct, implied_move
    """
    metrics = {}

    try:
        from datetime import datetime, timezone

        # Days to expiration
        today = datetime.now(timezone.utc).date()
        dte = (chain.expiration - today).days
        metrics["dte"] = int(dte) if dte >= 0 else 0

        # Find ATM option (closest to strike)
        atm_strike = chain.atm_strike
        atm_call = chain.get_call_by_strike(atm_strike)
        atm_put = chain.get_put_by_strike(atm_strike)

        # Use call for IV and Greeks metrics (or put if call not available)
        atm_option = atm_call if atm_call else atm_put

        if atm_option:
            # IV
            if atm_option.implied_volatility is not None:
                metrics["atm_iv"] = float(atm_option.implied_volatility)

            # Greeks
            greeks = {}
            if atm_option.delta is not None:
                greeks["delta"] = float(atm_option.delta)
            if atm_option.gamma is not None:
                greeks["gamma"] = float(atm_option.gamma)
            if atm_option.theta is not None:
                greeks["theta"] = float(atm_option.theta)
            if atm_option.vega is not None:
                greeks["vega"] = float(atm_option.vega)
            if atm_option.rho is not None:
                greeks["rho"] = float(atm_option.rho)
            if greeks:
                metrics["greeks"] = greeks

            # Volume and OI
            metrics["volume"] = int(atm_option.volume)
            metrics["oi"] = int(atm_option.open_interest)

            # Spread
            metrics["spread_pct"] = float(atm_option.spread_pct)

            # Implied move (simple estimate: ATM IV * current price)
            if atm_option.implied_volatility and metrics.get("dte", 0) > 0:
                days_in_year = 365.0
                time_to_exp = metrics["dte"] / days_in_year
                implied_move = current_price * atm_option.implied_volatility * np.sqrt(time_to_exp)
                metrics["implied_move"] = float(implied_move)

        logger.debug(
            f"Extracted {position} month options: {len(metrics)} metrics"
        )

    except Exception as e:
        logger.warning(f"Error extracting {position} options metrics: {e}")

    return metrics


def _compute_term_structure(
    options_front: Dict[str, Any], options_back: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compute term structure metrics comparing front and back month.

    Args:
        options_front: Front month options metrics
        options_back: Back month options metrics

    Returns:
        Dictionary with: iv_ratio, iv_diff, implied_move_front, implied_move_back
    """
    term_structure = {}

    try:
        # IV Ratio (front IV / back IV)
        front_iv = options_front.get("atm_iv")
        back_iv = options_back.get("atm_iv")
        if front_iv and back_iv and back_iv > 0:
            term_structure["iv_ratio"] = float(front_iv / back_iv)
            term_structure["iv_diff"] = float(front_iv - back_iv)

        # Implied moves
        if "implied_move" in options_front:
            term_structure["implied_move_front"] = options_front["implied_move"]
        if "implied_move" in options_back:
            term_structure["implied_move_back"] = options_back["implied_move"]

        logger.debug(f"Computed term structure: {list(term_structure.keys())}")

    except Exception as e:
        logger.warning(f"Error computing term structure: {e}")

    return term_structure


# ============================================================================
# HELPER FUNCTIONS - IV ANALYTICS
# ============================================================================


def _compute_iv_metrics(
    options_chains: Dict, options_front: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compute IV percentile and rank metrics.

    Args:
        options_chains: Dictionary of all OptionsChain objects
        options_front: Front month metrics dict

    Returns:
        Dictionary with: iv_percentile, iv_rank, iv_low, iv_high
    """
    iv_metrics = {}

    try:
        if not options_chains or not options_front:
            return iv_metrics

        current_iv = options_front.get("atm_iv")
        if not current_iv:
            return iv_metrics

        # Collect all IVs from all chains
        all_ivs = []
        for chain in options_chains.values():
            for call in chain.calls:
                if call.implied_volatility is not None:
                    all_ivs.append(call.implied_volatility)
            for put in chain.puts:
                if put.implied_volatility is not None:
                    all_ivs.append(put.implied_volatility)

        if all_ivs:
            all_ivs_array = np.array(all_ivs)
            iv_metrics["iv_low"] = float(np.percentile(all_ivs_array, 5))
            iv_metrics["iv_high"] = float(np.percentile(all_ivs_array, 95))

            # IV Percentile (what percentile is current IV)
            if current_iv and len(all_ivs) > 0:
                percentile = (all_ivs_array <= current_iv).sum() / len(all_ivs) * 100
                iv_metrics["iv_percentile"] = float(percentile)

                # IV Rank (0-1 scale between low and high)
                iv_range = iv_metrics["iv_high"] - iv_metrics["iv_low"]
                if iv_range > 0:
                    iv_rank = (current_iv - iv_metrics["iv_low"]) / iv_range
                    iv_metrics["iv_rank"] = float(np.clip(iv_rank, 0, 1))

        logger.debug(f"Computed IV metrics: {list(iv_metrics.keys())}")

    except Exception as e:
        logger.warning(f"Error computing IV metrics: {e}")

    return iv_metrics


# ============================================================================
# HELPER FUNCTIONS - LIQUIDITY ASSESSMENT
# ============================================================================


def _assess_liquidity(
    snapshot: MarketSnapshot, options_front: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Assess liquidity filters for the ticker.

    Args:
        snapshot: MarketSnapshot with price history
        options_front: Front month options metrics

    Returns:
        Dictionary with: passes_filter (bool), issues (list), adv_usd,
        atm_oi, atm_volume
    """
    liquidity = {"passes_filter": False, "issues": []}

    try:
        # Calculate Average Daily Volume in USD
        if snapshot.price_history:
            recent_bars = snapshot.price_history[-20:] if len(snapshot.price_history) >= 20 else snapshot.price_history
            volumes = [bar.volume for bar in recent_bars]
            prices = [bar.close for bar in recent_bars]
            avg_volume = np.mean(volumes) if volumes else 0
            avg_price = np.mean(prices) if prices else snapshot.price
            adv_usd = float(avg_volume * avg_price)
            liquidity["adv_usd"] = adv_usd
        else:
            liquidity["adv_usd"] = 0.0
            liquidity["issues"].append("No price history available")

        # Options liquidity
        atm_oi = options_front.get("oi", 0)
        atm_volume = options_front.get("volume", 0)
        liquidity["atm_oi"] = atm_oi
        liquidity["atm_volume"] = atm_volume

        # Check filters
        min_adv_usd = 1_000_000  # $1M minimum ADV
        min_atm_oi = 100  # Minimum open interest

        if liquidity["adv_usd"] < min_adv_usd:
            liquidity["issues"].append(f"ADV ${liquidity['adv_usd']:,.0f} below minimum ${min_adv_usd:,.0f}")
        if atm_oi < min_atm_oi:
            liquidity["issues"].append(f"ATM OI {atm_oi} below minimum {min_atm_oi}")

        # Pass filter if no issues
        liquidity["passes_filter"] = len(liquidity["issues"]) == 0

        logger.debug(f"Liquidity assessment: passes={liquidity['passes_filter']}")

    except Exception as e:
        logger.warning(f"Error assessing liquidity: {e}")
        liquidity["issues"].append(f"Assessment error: {str(e)}")

    return liquidity


# ============================================================================
# HELPER FUNCTIONS - EARNINGS
# ============================================================================


def _extract_earnings_info(snapshot: MarketSnapshot) -> Dict[str, Any]:
    """
    Extract earnings information.

    Stub function - actual implementation would query earnings calendar.
    Returns None for now, ready for integration with earnings data provider.

    Args:
        snapshot: MarketSnapshot (not used currently)

    Returns:
        Dictionary with: days_to_earnings (None), earnings_date (None)
    """
    earnings = {
        "days_to_earnings": None,
        "earnings_date": None,
    }

    logger.debug("Earnings info: stub (no data source)")

    return earnings
