"""
Technical indicator calculations for options analysis.

This module provides functions for calculating technical indicators including moving averages,
momentum indicators (RSI, MACD), Fibonacci levels, and volume metrics. All calculations use
pandas and numpy for efficient vectorized operations.

Functions:
    Helper functions:
    - calculate_sma(prices, period): Simple Moving Average
    - calculate_ema(prices, period): Exponential Moving Average
    - calculate_rsi(prices, period): Relative Strength Index
    - calculate_macd(prices, fast, slow, signal): MACD and signal line
    - calculate_fib_levels(high, low, levels): Fibonacci retracement levels
    - calculate_volume_metrics(volume, ma_period): Volume analysis metrics
    - calculate_breakout_levels(high, low, lookback_days): Support/resistance levels

    Main class:
    - TechnicalAnalyzer: Comprehensive technical analysis for price data

Usage:
    from functions.compute.technicals import TechnicalAnalyzer
    import pandas as pd

    # Create DataFrame with OHLCV data
    df = pd.DataFrame({
        'close': [100, 101, 102, 101, 103, ...],
        'high': [101, 102, 103, 102, 104, ...],
        'low': [99, 100, 101, 100, 102, ...],
        'volume': [1000000, 1100000, 900000, ...]
    })

    # Initialize analyzer
    analyzer = TechnicalAnalyzer(df)

    # Compute all indicators
    indicators = analyzer.compute_all()

    # Access specific indicators
    print(indicators['sma_20'])
    print(indicators['rsi'])
    print(indicators['macd'])
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, Any
from functions.util.logging_setup import get_logger
from functions.config.settings import get_settings

logger = get_logger(__name__)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def calculate_sma(prices: pd.Series, period: int) -> pd.Series:
    """
    Calculate Simple Moving Average (SMA).

    The SMA is the unweighted mean of the previous n data points.
    Useful for identifying trend direction and support/resistance levels.

    Args:
        prices: Series of price values (typically closing prices)
        period: Number of periods for the moving average (e.g., 20, 50, 200)

    Returns:
        Series with SMA values (same length as input, NaN for initial periods)

    Raises:
        ValueError: If period is less than 1 or greater than series length
        TypeError: If prices is not a pandas Series

    Example:
        >>> prices = pd.Series([100, 101, 102, 101, 100])
        >>> sma_2 = calculate_sma(prices, period=2)
        >>> sma_2.iloc[-1]  # Most recent SMA value
    """
    if not isinstance(prices, pd.Series):
        raise TypeError(f"prices must be a pandas Series, got {type(prices)}")

    if period < 1:
        raise ValueError(f"period must be >= 1, got {period}")

    if period > len(prices):
        raise ValueError(
            f"period ({period}) cannot exceed series length ({len(prices)})"
        )

    return prices.rolling(window=period).mean()


def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    """
    Calculate Exponential Moving Average (EMA).

    The EMA gives more weight to recent prices compared to older prices.
    More responsive to price changes than SMA, useful for trend confirmation.

    Args:
        prices: Series of price values (typically closing prices)
        period: Number of periods for the moving average (e.g., 9, 21, 50)

    Returns:
        Series with EMA values (same length as input, NaN for initial periods)

    Raises:
        ValueError: If period is less than 1 or greater than series length
        TypeError: If prices is not a pandas Series

    Example:
        >>> prices = pd.Series([100, 101, 102, 101, 100])
        >>> ema_9 = calculate_ema(prices, period=9)
        >>> ema_9.iloc[-1]  # Most recent EMA value
    """
    if not isinstance(prices, pd.Series):
        raise TypeError(f"prices must be a pandas Series, got {type(prices)}")

    if period < 1:
        raise ValueError(f"period must be >= 1, got {period}")

    if period > len(prices):
        raise ValueError(
            f"period ({period}) cannot exceed series length ({len(prices)})"
        )

    return prices.ewm(span=period, adjust=False).mean()


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI).

    RSI oscillates between 0 and 100, measuring the magnitude of recent price changes
    to evaluate overbought/oversold conditions. Values above 70 suggest overbought,
    below 30 suggest oversold.

    Args:
        prices: Series of price values (typically closing prices)
        period: Number of periods for RSI calculation. Defaults to 14

    Returns:
        Series with RSI values between 0 and 100 (same length as input)

    Raises:
        ValueError: If period is less than 1 or greater than series length
        TypeError: If prices is not a pandas Series

    Example:
        >>> prices = pd.Series([100, 101, 102, 101, 100])
        >>> rsi = calculate_rsi(prices, period=14)
        >>> rsi.iloc[-1]  # Most recent RSI value (0-100)
    """
    if not isinstance(prices, pd.Series):
        raise TypeError(f"prices must be a pandas Series, got {type(prices)}")

    if period < 1:
        raise ValueError(f"period must be >= 1, got {period}")

    if period > len(prices):
        raise ValueError(
            f"period ({period}) cannot exceed series length ({len(prices)})"
        )

    # Calculate price changes
    delta = prices.diff()

    # Separate gains and losses
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    # Calculate average gain and loss using exponential smoothing
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()

    # Avoid division by zero
    rs = avg_gain / avg_loss.replace(0, 1e-10)

    # Calculate RSI
    rsi = 100 - (100 / (1 + rs))

    # Handle edge case where all losses are zero
    rsi = rsi.where(avg_loss != 0, 100)

    return rsi


def calculate_macd(
    prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    MACD is a trend-following momentum indicator that shows the relationship
    between two moving averages. Includes MACD line, signal line, and histogram.

    Args:
        prices: Series of price values (typically closing prices)
        fast: Period for fast EMA. Defaults to 12
        slow: Period for slow EMA. Defaults to 26
        signal: Period for signal line EMA. Defaults to 9

    Returns:
        Tuple of three Series: (macd_line, signal_line, macd_histogram)
        All have same length as input with NaN for initial periods

    Raises:
        ValueError: If periods are invalid (fast >= slow or signal <= 0)
        TypeError: If prices is not a pandas Series

    Example:
        >>> prices = pd.Series([100, 101, 102, 101, 100, 99, 100])
        >>> macd, signal, hist = calculate_macd(prices)
        >>> macd.iloc[-1]  # MACD value
        >>> signal.iloc[-1]  # Signal line
        >>> hist.iloc[-1]  # Histogram (MACD - Signal)
    """
    if not isinstance(prices, pd.Series):
        raise TypeError(f"prices must be a pandas Series, got {type(prices)}")

    if fast >= slow:
        raise ValueError(f"fast ({fast}) must be less than slow ({slow})")

    if signal <= 0:
        raise ValueError(f"signal ({signal}) must be positive")

    # Calculate EMAs
    ema_fast = calculate_ema(prices, period=fast)
    ema_slow = calculate_ema(prices, period=slow)

    # Calculate MACD line
    macd_line = ema_fast - ema_slow

    # Calculate signal line
    signal_line = calculate_ema(macd_line, period=signal)

    # Calculate histogram
    macd_histogram = macd_line - signal_line

    return macd_line, signal_line, macd_histogram


def calculate_fib_levels(
    high: float, low: float, levels: Optional[list] = None
) -> Dict[str, float]:
    """
    Calculate Fibonacci retracement levels.

    Fibonacci levels are used to identify potential support and resistance levels
    based on the theory that markets will retrace predictable percentages of
    a move before continuing in the original direction.

    Args:
        high: Highest price in the move (float)
        low: Lowest price in the move (float)
        levels: List of Fibonacci ratios to calculate. Defaults to standard levels

    Returns:
        Dictionary with level names as keys and price levels as values.
        Standard levels: 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%

    Raises:
        ValueError: If high <= low or negative prices
        TypeError: If inputs are not numeric

    Example:
        >>> fib_levels = calculate_fib_levels(high=110, low=100)
        >>> fib_levels['61.8%']  # Golden ratio level
    """
    try:
        high = float(high)
        low = float(low)
    except (ValueError, TypeError) as e:
        raise TypeError(f"high and low must be numeric, got {e}")

    if high <= low:
        raise ValueError(f"high ({high}) must be greater than low ({low})")

    if high < 0 or low < 0:
        raise ValueError("prices must be non-negative")

    # Default Fibonacci levels
    if levels is None:
        levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]

    # Calculate retracement levels
    diff = high - low
    fib_dict = {}

    for level in levels:
        price = high - (diff * level)
        percentage = f"{level * 100:.1f}%"
        fib_dict[percentage] = round(price, 2)

    return fib_dict


def calculate_volume_metrics(volume: pd.Series, ma_period: int = 20) -> Dict[str, Any]:
    """
    Calculate volume analysis metrics.

    Provides volume statistics including average volume, current vs average,
    and volume moving average for trend analysis.

    Args:
        volume: Series of trading volume values
        ma_period: Period for volume moving average. Defaults to 20

    Returns:
        Dictionary with volume metrics:
        - 'current': Most recent volume value
        - 'average': Average volume over entire series
        - 'ma': Volume moving average
        - 'current_vs_average_ratio': Current volume / average (>1 = above average)
        - 'volume_trend': 'increasing', 'decreasing', or 'stable'

    Raises:
        ValueError: If ma_period is invalid or volume is empty
        TypeError: If volume is not a pandas Series

    Example:
        >>> volume = pd.Series([1000000, 1100000, 900000, 1050000])
        >>> metrics = calculate_volume_metrics(volume, ma_period=2)
        >>> metrics['current_vs_average_ratio']  # Compare current to average
    """
    if not isinstance(volume, pd.Series):
        raise TypeError(f"volume must be a pandas Series, got {type(volume)}")

    if volume.empty:
        raise ValueError("volume Series cannot be empty")

    if ma_period < 1 or ma_period > len(volume):
        raise ValueError(
            f"ma_period must be between 1 and {len(volume)}, got {ma_period}"
        )

    current_volume = volume.iloc[-1]
    average_volume = volume.mean()
    volume_ma = volume.rolling(window=ma_period).mean()

    # Calculate trend: compare current MA to previous MA
    if len(volume_ma) >= 2 and not pd.isna(volume_ma.iloc[-1]):
        current_ma = volume_ma.iloc[-1]
        prev_ma = volume_ma.iloc[-2]
        if current_ma > prev_ma:
            trend = "increasing"
        elif current_ma < prev_ma:
            trend = "decreasing"
        else:
            trend = "stable"
    else:
        trend = "insufficient_data"

    ratio = current_volume / average_volume if average_volume > 0 else 0

    return {
        "current": current_volume,
        "average": round(average_volume, 0),
        "ma": volume_ma.iloc[-1] if not pd.isna(volume_ma.iloc[-1]) else None,
        "current_vs_average_ratio": round(ratio, 2),
        "volume_trend": trend,
    }


def calculate_breakout_levels(
    high: pd.Series, low: pd.Series, lookback_days: int = 20
) -> Dict[str, float]:
    """
    Calculate breakout levels based on recent support and resistance.

    Identifies potential breakout levels by finding the highest high and
    lowest low over a lookback period.

    Args:
        high: Series of high prices
        low: Series of low prices
        lookback_days: Number of periods to look back for levels. Defaults to 20

    Returns:
        Dictionary with breakout levels:
        - 'resistance': Highest high over lookback period
        - 'support': Lowest low over lookback period
        - 'midpoint': Average of resistance and support

    Raises:
        ValueError: If lookback_days is invalid or series are mismatched
        TypeError: If inputs are not pandas Series

    Example:
        >>> high = pd.Series([101, 102, 103, 102, 104, ...])
        >>> low = pd.Series([99, 100, 101, 100, 102, ...])
        >>> levels = calculate_breakout_levels(high, low, lookback_days=20)
        >>> levels['resistance']  # Recent high
    """
    if not isinstance(high, pd.Series) or not isinstance(low, pd.Series):
        raise TypeError("high and low must be pandas Series")

    if len(high) != len(low):
        raise ValueError("high and low Series must have same length")

    if lookback_days < 1:
        raise ValueError(f"lookback_days must be >= 1, got {lookback_days}")

    if lookback_days > len(high):
        lookback_days = len(high)
        logger.warning(
            f"lookback_days adjusted to series length ({len(high)}) as it was larger"
        )

    # Get recent data
    recent_high = high.tail(lookback_days)
    recent_low = low.tail(lookback_days)

    # Find levels
    resistance = recent_high.max()
    support = recent_low.min()
    midpoint = (resistance + support) / 2

    return {
        "resistance": round(resistance, 2),
        "support": round(support, 2),
        "midpoint": round(midpoint, 2),
    }


# ============================================================================
# TECHNICAL ANALYZER CLASS
# ============================================================================


class TechnicalAnalyzer:
    """
    Comprehensive technical analysis for price data.

    Computes multiple technical indicators on OHLCV (Open, High, Low, Close, Volume)
    data and provides a unified interface for accessing all indicators.

    Attributes:
        df: DataFrame containing OHLCV data
        required_columns: Set of required column names

    Example:
        >>> df = pd.DataFrame({
        ...     'open': [100, 101, 102],
        ...     'high': [101, 102, 103],
        ...     'low': [99, 100, 101],
        ...     'close': [100.5, 101.5, 102.5],
        ...     'volume': [1000000, 1100000, 900000]
        ... })
        >>> analyzer = TechnicalAnalyzer(df)
        >>> indicators = analyzer.compute_all()
        >>> print(indicators['rsi'])
    """

    # Required columns in the DataFrame
    REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume"}

    def __init__(self, df: pd.DataFrame) -> None:
        """
        Initialize TechnicalAnalyzer with OHLCV data.

        Args:
            df: DataFrame with columns 'open', 'high', 'low', 'close', 'volume'

        Raises:
            ValueError: If required columns are missing
            TypeError: If df is not a pandas DataFrame
            ValueError: If DataFrame is empty

        Example:
            >>> df = pd.read_csv('prices.csv')
            >>> analyzer = TechnicalAnalyzer(df)
        """
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"df must be a pandas DataFrame, got {type(df)}")

        if df.empty:
            raise ValueError("DataFrame cannot be empty")

        # Check for required columns
        missing_columns = self.REQUIRED_COLUMNS - set(df.columns)
        if missing_columns:
            raise ValueError(
                f"Missing required columns: {missing_columns}. "
                f"Required: {self.REQUIRED_COLUMNS}"
            )

        self.df = df.copy()
        logger.debug(f"TechnicalAnalyzer initialized with {len(df)} rows")

    def compute_all(self) -> Dict[str, Any]:
        """
        Compute all technical indicators.

        Calculates a comprehensive set of indicators including moving averages,
        momentum indicators, Fibonacci levels, volume metrics, and breakout levels.

        Returns:
            Dictionary containing all computed indicators:
            - 'price': Current price
            - 'price_change_1d': 1-day price change
            - 'price_change_5d': 5-day price change
            - 'sma_20', 'sma_50', 'sma_200': Simple moving averages
            - 'ema_9', 'ema_21': Exponential moving averages
            - 'rsi': Relative Strength Index (0-100)
            - 'macd': MACD line value
            - 'macd_signal': MACD signal line value
            - 'macd_hist': MACD histogram value
            - 'fib_levels': Dictionary of Fibonacci retracement levels
            - 'volume_metrics': Dictionary of volume statistics
            - 'breakout_levels': Dictionary of support/resistance levels
            - 'price_position': Position relative to key levels

        Raises:
            Exception: If computation fails (logged but not re-raised)

        Example:
            >>> indicators = analyzer.compute_all()
            >>> print(indicators['rsi'])
            >>> print(indicators['fib_levels']['61.8%'])
        """
        try:
            logger.debug("Computing all technical indicators")

            indicators = {}

            # Price data
            current_price = self.df["close"].iloc[-1]
            indicators["price"] = round(current_price, 2)

            # Price changes
            price_change_1d = (
                (self.df["close"].iloc[-1] - self.df["close"].iloc[-2])
                / self.df["close"].iloc[-2]
                * 100
                if len(self.df) >= 2
                else 0
            )
            indicators["price_change_1d"] = round(price_change_1d, 2)

            price_change_5d = (
                (self.df["close"].iloc[-1] - self.df["close"].iloc[-5])
                / self.df["close"].iloc[-5]
                * 100
                if len(self.df) >= 5
                else 0
            )
            indicators["price_change_5d"] = round(price_change_5d, 2)

            # Simple Moving Averages
            sma_20 = calculate_sma(self.df["close"], period=20)
            indicators["sma_20"] = (
                round(sma_20.iloc[-1], 2) if not pd.isna(sma_20.iloc[-1]) else None
            )

            sma_50 = calculate_sma(self.df["close"], period=50)
            indicators["sma_50"] = (
                round(sma_50.iloc[-1], 2) if not pd.isna(sma_50.iloc[-1]) else None
            )

            sma_200 = calculate_sma(self.df["close"], period=200)
            indicators["sma_200"] = (
                round(sma_200.iloc[-1], 2) if not pd.isna(sma_200.iloc[-1]) else None
            )

            # Exponential Moving Averages
            ema_9 = calculate_ema(self.df["close"], period=9)
            indicators["ema_9"] = (
                round(ema_9.iloc[-1], 2) if not pd.isna(ema_9.iloc[-1]) else None
            )

            ema_21 = calculate_ema(self.df["close"], period=21)
            indicators["ema_21"] = (
                round(ema_21.iloc[-1], 2) if not pd.isna(ema_21.iloc[-1]) else None
            )

            # RSI
            rsi = calculate_rsi(self.df["close"], period=14)
            indicators["rsi"] = (
                round(rsi.iloc[-1], 2) if not pd.isna(rsi.iloc[-1]) else None
            )

            # MACD
            macd, signal, hist = calculate_macd(self.df["close"])
            indicators["macd"] = (
                round(macd.iloc[-1], 4) if not pd.isna(macd.iloc[-1]) else None
            )
            indicators["macd_signal"] = (
                round(signal.iloc[-1], 4) if not pd.isna(signal.iloc[-1]) else None
            )
            indicators["macd_hist"] = (
                round(hist.iloc[-1], 4) if not pd.isna(hist.iloc[-1]) else None
            )

            # Fibonacci levels
            high = self.df["high"].max()
            low = self.df["low"].min()
            indicators["fib_levels"] = calculate_fib_levels(high, low)

            # Volume metrics
            indicators["volume_metrics"] = calculate_volume_metrics(
                self.df["volume"], ma_period=20
            )

            # Breakout levels
            indicators["breakout_levels"] = calculate_breakout_levels(
                self.df["high"], self.df["low"], lookback_days=20
            )

            # Price position relative to key levels
            if indicators["sma_20"] is not None:
                sma_20_val = indicators["sma_20"]
                if current_price > sma_20_val:
                    price_position = "above_sma_20"
                elif current_price < sma_20_val:
                    price_position = "below_sma_20"
                else:
                    price_position = "at_sma_20"
            else:
                price_position = "insufficient_data"

            indicators["price_position"] = price_position

            logger.debug("Technical indicators computed successfully")
            return indicators

        except Exception as e:
            logger.error(f"Error computing technical indicators: {e}", exc_info=True)
            raise
