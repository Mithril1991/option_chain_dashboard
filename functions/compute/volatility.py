"""
Volatility calculation functions for the Option Chain Dashboard.

Provides comprehensive volatility metrics including:
- Historical volatility (HV) with customizable windows
- Parkinson volatility (range-based)
- Garman-Klass volatility (OHLCV-based)
- IV metrics and term structure analysis
- Volatility regime classification

All calculations use industry-standard formulas and are annualized by default.

Usage:
    from functions.compute.volatility import VolatilityAnalyzer, compute_iv_metrics
    import pandas as pd

    # Create analyzer with OHLCV data
    df = pd.DataFrame(...)  # Must have columns: open, high, low, close, volume
    analyzer = VolatilityAnalyzer(df)

    # Compute all volatility metrics
    metrics = analyzer.compute_all()
    print(f"HV 20: {metrics['hv_20']:.4f}")
    print(f"IV vs HV 20: {metrics['iv_vs_hv20']:.2%}")

    # Compute IV metrics
    iv_metrics = compute_iv_metrics(
        iv_front=0.35,
        iv_back=0.32,
        hv_20=0.28,
        iv_percentile=0.65
    )
    print(f"Term structure ratio: {iv_metrics['term_structure_ratio']:.4f}")
"""

import numpy as np
import pandas as pd
from scipy.stats import norm
import math
from typing import Dict, Optional, Tuple
from functions.util.logging_setup import get_logger

logger = get_logger(__name__)


# ============================================================================
# Helper Functions - Log Returns
# ============================================================================


def calculate_log_returns(prices: pd.Series) -> pd.Series:
    """
    Calculate log returns from a price series.

    Uses the natural logarithm of price ratios for volatility calculations.
    Log returns are preferred for statistical properties (additivity over time).

    Args:
        prices: Series of prices (typically close prices)

    Returns:
        Series of log returns matching the input index (NaN for first row)

    Raises:
        ValueError: If prices is empty or contains non-positive values

    Example:
        >>> prices = pd.Series([100, 102, 101, 103])
        >>> returns = calculate_log_returns(prices)
        >>> returns.round(4)
        0         NaN
        1    0.0198
        2   -0.0099
        3    0.0198
        dtype: float64

        >>> # For volatility calculation
        >>> vol = returns.std() * math.sqrt(252)  # Annualized
        >>> print(f"Annualized volatility: {vol:.2%}")
    """
    if prices.empty:
        raise ValueError("Prices series is empty")
    if (prices <= 0).any():
        raise ValueError("All prices must be positive")

    return np.log(prices / prices.shift(1))


# ============================================================================
# Helper Functions - Historical Volatility
# ============================================================================


def calculate_realized_volatility(
    returns: pd.Series, window: int, annualization_factor: float = 252
) -> pd.Series:
    """
    Calculate realized volatility from returns using rolling window.

    Uses the standard deviation of returns over a specified window period.
    Commonly called "Historical Volatility" (HV) in options trading.

    Args:
        returns: Series of returns (e.g., log returns)
        window: Rolling window size in periods (typically 10, 20, 60 for daily data)
        annualization_factor: Factor to annualize volatility (default 252 for daily data)

    Returns:
        Series of annualized volatility values (NaN for first window-1 rows)

    Raises:
        ValueError: If window <= 0, returns is empty, or annualization_factor <= 0

    Example:
        >>> prices = pd.Series([100, 102, 101, 103, 105, 104])
        >>> returns = calculate_log_returns(prices)
        >>> hv = calculate_realized_volatility(returns, window=3)
        >>> hv.round(4)
        0         NaN
        1         NaN
        2    0.0192
        3    0.0157
        4    0.0192
        5    0.0154
        dtype: float64

        >>> # Check 20-day historical volatility
        >>> prices = pd.Series(...)  # 252+ daily prices
        >>> returns = calculate_log_returns(prices)
        >>> hv_20 = calculate_realized_volatility(returns, window=20)
        >>> print(f"HV 20: {hv_20.iloc[-1]:.2%}")
        HV 20: 18.45%
    """
    if window <= 0:
        raise ValueError(f"Window must be positive, got {window}")
    if returns.empty:
        raise ValueError("Returns series is empty")
    if annualization_factor <= 0:
        raise ValueError(f"Annualization factor must be positive, got {annualization_factor}")

    rolling_std = returns.rolling(window=window).std()
    return rolling_std * math.sqrt(annualization_factor)


# ============================================================================
# Helper Functions - Parkinson Volatility
# ============================================================================


def calculate_parkinson_volatility(
    high: pd.Series, low: pd.Series, window: int, annualization_factor: float = 252
) -> pd.Series:
    """
    Calculate Parkinson volatility from high-low range data.

    Parkinson volatility uses intraday high-low range, which contains more
    information about volatility than close prices alone. Particularly useful
    when intraday data is available.

    Formula:
        Parkinson = sqrt( (1 / (4 * ln(2) * N)) * sum(ln(H/L)^2) )
        Annualized = Parkinson * sqrt(annualization_factor)

    Args:
        high: Series of intraday high prices
        low: Series of intraday low prices
        window: Rolling window size in periods
        annualization_factor: Factor to annualize volatility (default 252 for daily data)

    Returns:
        Series of annualized Parkinson volatility (NaN for first window-1 rows)

    Raises:
        ValueError: If inputs invalid, window <= 0, or high < low anywhere

    Example:
        >>> high = pd.Series([101, 103, 102, 104])
        >>> low = pd.Series([99, 101, 100, 102])
        >>> pv = calculate_parkinson_volatility(high, low, window=2)
        >>> pv.round(4)
        0         NaN
        1    0.1571
        2    0.1286
        3    0.1286
        dtype: float64

        >>> # Compare Parkinson vs Historical Volatility
        >>> hv_20 = calculate_realized_volatility(returns, window=20)
        >>> pv_20 = calculate_parkinson_volatility(high, low, window=20)
        >>> print(f"HV 20: {hv_20.iloc[-1]:.2%}, PV 20: {pv_20.iloc[-1]:.2%}")
    """
    if window <= 0:
        raise ValueError(f"Window must be positive, got {window}")
    if high.empty or low.empty:
        raise ValueError("High/low series are empty")
    if annualization_factor <= 0:
        raise ValueError(f"Annualization factor must be positive, got {annualization_factor}")

    if (high < low).any():
        raise ValueError("High prices must be >= low prices at all points")

    # Calculate HL ratio and log
    hl_ratio = high / low
    log_hl = np.log(hl_ratio)

    # Parkinson formula: sqrt((1 / (4*ln(2)*N)) * sum(ln(H/L)^2))
    ln2 = np.log(2)
    rolling_sum_sq = (log_hl ** 2).rolling(window=window).sum()
    denominator = 4 * ln2 * window

    parkinson = np.sqrt(rolling_sum_sq / denominator)
    return parkinson * math.sqrt(annualization_factor)


# ============================================================================
# Helper Functions - Garman-Klass Volatility
# ============================================================================


def calculate_garman_klass_volatility(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int,
    annualization_factor: float = 252,
) -> pd.Series:
    """
    Calculate Garman-Klass volatility from OHLC data.

    Garman-Klass combines open-close and high-low information for efficient
    volatility estimation. More efficient than close-to-close (HV) while
    less sensitive to overnight gaps than just high-low (Parkinson).

    Formula:
        GK = sqrt( (1/N) * sum(
            0.5 * ln(H/L)^2 - (2*ln(2) - 1) * ln(C/O)^2
        ))
        Annualized = GK * sqrt(annualization_factor)

    Args:
        open_: Series of open prices
        high: Series of high prices
        low: Series of low prices
        close: Series of close prices
        window: Rolling window size in periods
        annualization_factor: Factor to annualize volatility (default 252)

    Returns:
        Series of annualized Garman-Klass volatility (NaN for first window-1 rows)

    Raises:
        ValueError: If inputs invalid or window <= 0

    Example:
        >>> open_ = pd.Series([100, 101, 102])
        >>> high = pd.Series([102, 103, 104])
        >>> low = pd.Series([99, 100, 101])
        >>> close = pd.Series([101, 102, 103])
        >>> gk = calculate_garman_klass_volatility(open_, high, low, close, window=2)
        >>> gk.round(4)
        0         NaN
        1    0.0892
        2    0.0882
        dtype: float64

        >>> # Typically GK < Parkinson < HV (less noise, more efficient)
        >>> hv = calculate_realized_volatility(returns, window=20)
        >>> pv = calculate_parkinson_volatility(high, low, window=20)
        >>> gk = calculate_garman_klass_volatility(open_, high, low, close, window=20)
        >>> print(f"HV: {hv.iloc[-1]:.2%}, PV: {pv.iloc[-1]:.2%}, GK: {gk.iloc[-1]:.2%}")
    """
    if window <= 0:
        raise ValueError(f"Window must be positive, got {window}")
    if any(s.empty for s in [open_, high, low, close]):
        raise ValueError("OHLC series cannot be empty")
    if annualization_factor <= 0:
        raise ValueError(f"Annualization factor must be positive, got {annualization_factor}")

    # Garman-Klass formula components
    hl_ratio = high / low
    co_ratio = close / open_

    ln2 = np.log(2)
    term1 = 0.5 * (np.log(hl_ratio) ** 2)
    term2 = (2 * ln2 - 1) * (np.log(co_ratio) ** 2)

    gk_daily = np.sqrt(term1 - term2)
    rolling_sum = gk_daily.rolling(window=window).sum()

    garman_klass = np.sqrt(rolling_sum / window)
    return garman_klass * math.sqrt(annualization_factor)


# ============================================================================
# IV Metrics Computation
# ============================================================================


def compute_iv_metrics(
    iv_front: float,
    iv_back: float,
    hv_20: float,
    iv_percentile: float,
    iv_low: Optional[float] = None,
    iv_high: Optional[float] = None,
) -> Dict[str, float]:
    """
    Compute implied volatility (IV) metrics and term structure analysis.

    Analyzes the relationship between front/back IV levels, historical volatility,
    and percentile positioning for options strategy evaluation.

    Args:
        iv_front: Front-month (near-term) implied volatility (e.g., 0.35 for 35%)
        iv_back: Back-month (longer-term) implied volatility
        hv_20: 20-day historical volatility
        iv_percentile: IV percentile (0-1, where 1.0 = 100th percentile)
        iv_low: Optional 52-week IV low for reference
        iv_high: Optional 52-week IV high for reference

    Returns:
        Dictionary with following keys:
        - iv_front: Front month IV (input)
        - iv_back: Back month IV (input)
        - term_structure_diff: iv_back - iv_front (positive = contango)
        - term_structure_ratio: iv_back / iv_front (>1.0 = contango)
        - contango: Boolean, True if iv_back > iv_front
        - backwardation: Boolean, True if iv_back < iv_front
        - iv_vs_hv20: IV front month vs HV 20 ratio
        - iv_premium: (iv_front - hv_20) / hv_20, premium above historical vol
        - iv_percentile: IV percentile rank (input)
        - iv_low: 52-week low if provided, else None
        - iv_high: 52-week high if provided, else None

    Raises:
        ValueError: If iv values negative, iv_percentile not in [0,1], or hv_20 <= 0

    Example:
        >>> metrics = compute_iv_metrics(
        ...     iv_front=0.35,
        ...     iv_back=0.32,
        ...     hv_20=0.28,
        ...     iv_percentile=0.65,
        ...     iv_low=0.25,
        ...     iv_high=0.45
        ... )
        >>> print(f"Term structure: {metrics['term_structure_diff']:.4f}")
        >>> print(f"Backwardation: {metrics['backwardation']}")
        >>> print(f"IV Premium: {metrics['iv_premium']:.2%}")
        Term structure: -0.0300
        Backwardation: True
        IV Premium: 25.00%

        >>> # In contango environment
        >>> metrics = compute_iv_metrics(
        ...     iv_front=0.30, iv_back=0.35, hv_20=0.28, iv_percentile=0.50
        ... )
        >>> print(f"Contango: {metrics['contango']}")
        >>> print(f"IV vs HV Ratio: {metrics['iv_vs_hv20']:.4f}")
        Contango: True
        IV vs HV Ratio: 1.0714
    """
    if iv_front < 0 or iv_back < 0 or hv_20 <= 0:
        raise ValueError(
            f"IV values must be >= 0, HV must be > 0. "
            f"Got iv_front={iv_front}, iv_back={iv_back}, hv_20={hv_20}"
        )
    if not (0 <= iv_percentile <= 1):
        raise ValueError(f"IV percentile must be in [0, 1], got {iv_percentile}")

    term_structure_diff = iv_back - iv_front
    term_structure_ratio = iv_back / iv_front if iv_front > 0 else 0.0
    is_contango = iv_back > iv_front
    is_backwardation = iv_back < iv_front

    iv_vs_hv20 = iv_front / hv_20
    iv_premium = (iv_front - hv_20) / hv_20

    return {
        "iv_front": iv_front,
        "iv_back": iv_back,
        "term_structure_diff": term_structure_diff,
        "term_structure_ratio": term_structure_ratio,
        "contango": is_contango,
        "backwardation": is_backwardation,
        "iv_vs_hv20": iv_vs_hv20,
        "iv_premium": iv_premium,
        "iv_percentile": iv_percentile,
        "iv_low": iv_low,
        "iv_high": iv_high,
    }


# ============================================================================
# Main Analyzer Class
# ============================================================================


class VolatilityAnalyzer:
    """
    Comprehensive volatility analysis from OHLCV data.

    Computes multiple volatility metrics and classifications suitable for
    options analysis, risk management, and opportunity identification.

    Attributes:
        df (pd.DataFrame): OHLCV DataFrame with columns: open, high, low, close, volume
        close_prices (pd.Series): Close price series
        returns (pd.Series): Log returns series
    """

    def __init__(self, df: pd.DataFrame):
        """
        Initialize VolatilityAnalyzer with OHLCV data.

        Args:
            df: DataFrame with required columns: open, high, low, close, volume
               Index should be datetime

        Raises:
            ValueError: If required columns missing or data is empty

        Example:
            >>> import pandas as pd
            >>> df = pd.DataFrame({
            ...     'open': [100, 101, 102],
            ...     'high': [102, 103, 104],
            ...     'low': [99, 100, 101],
            ...     'close': [101, 102, 103],
            ...     'volume': [1000000, 1100000, 900000]
            ... }, index=pd.date_range('2026-01-01', periods=3))
            >>> analyzer = VolatilityAnalyzer(df)
            >>> metrics = analyzer.compute_all()
        """
        required_cols = {"open", "high", "low", "close", "volume"}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            raise ValueError(f"Missing required columns: {missing}")

        if df.empty:
            raise ValueError("DataFrame is empty")

        self.df = df.copy()
        self.close_prices = df["close"]
        self.returns = calculate_log_returns(self.close_prices)

        logger.debug(f"VolatilityAnalyzer initialized with {len(df)} rows")

    def compute_all(self) -> Dict[str, pd.Series]:
        """
        Compute all volatility metrics at once.

        Computes multiple historical volatility windows, range-based volatility,
        and volatility regime classification. Returns the latest value for each metric.

        Returns:
            Dictionary with keys:
            - hv_10: 10-day historical volatility
            - hv_20: 20-day historical volatility
            - hv_60: 60-day historical volatility
            - parkinson_vol_20: 20-day Parkinson volatility
            - garman_klass_vol_20: 20-day Garman-Klass volatility
            - vol_regime_ratio: hv_20 / hv_60 (>1.0 = increasing vol)
            - vol_expanding: Boolean (hv_20 > hv_60)
            - vol_trend: String, one of "expanding", "compressing", "stable"

        Example:
            >>> import pandas as pd
            >>> prices = pd.Series([100 + i*0.5 for i in range(100)])
            >>> ohlc_data = {
            ...     'open': prices - 0.5,
            ...     'high': prices + 0.5,
            ...     'low': prices - 1.0,
            ...     'close': prices,
            ...     'volume': [1000000] * 100
            ... }
            >>> df = pd.DataFrame(ohlc_data)
            >>> analyzer = VolatilityAnalyzer(df)
            >>> metrics = analyzer.compute_all()
            >>> for key, val in metrics.items():
            ...     if isinstance(val, (int, float)):
            ...         print(f"{key}: {val:.4f}")
            ...     else:
            ...         print(f"{key}: {val}")
        """
        try:
            # Calculate historical volatility across windows
            hv_10 = calculate_realized_volatility(self.returns, window=10)
            hv_20 = calculate_realized_volatility(self.returns, window=20)
            hv_60 = calculate_realized_volatility(self.returns, window=60)

            # Calculate range-based volatility
            parkinson_vol_20 = calculate_parkinson_volatility(
                self.df["high"], self.df["low"], window=20
            )

            garman_klass_vol_20 = calculate_garman_klass_volatility(
                self.df["open"],
                self.df["high"],
                self.df["low"],
                self.df["close"],
                window=20,
            )

            # Calculate volatility regime metrics
            latest_hv_20 = hv_20.iloc[-1]
            latest_hv_60 = hv_60.iloc[-1]

            if latest_hv_60 > 0:
                vol_regime_ratio = latest_hv_20 / latest_hv_60
            else:
                vol_regime_ratio = 1.0

            vol_expanding = latest_hv_20 > latest_hv_60

            # Classify volatility trend
            if vol_regime_ratio > 1.1:
                vol_trend = "expanding"
            elif vol_regime_ratio < 0.9:
                vol_trend = "compressing"
            else:
                vol_trend = "stable"

            logger.debug(
                f"Volatility metrics computed: HV20={latest_hv_20:.4f}, "
                f"HV60={latest_hv_60:.4f}, trend={vol_trend}"
            )

            return {
                "hv_10": hv_10.iloc[-1],
                "hv_20": hv_20.iloc[-1],
                "hv_60": hv_60.iloc[-1],
                "parkinson_vol_20": parkinson_vol_20.iloc[-1],
                "garman_klass_vol_20": garman_klass_vol_20.iloc[-1],
                "vol_regime_ratio": vol_regime_ratio,
                "vol_expanding": vol_expanding,
                "vol_trend": vol_trend,
            }

        except Exception as e:
            logger.error(f"Error computing volatility metrics: {e}")
            raise

    def compute_all_series(self) -> Dict[str, pd.Series]:
        """
        Compute all volatility metrics as time series (not just latest values).

        Similar to compute_all() but returns full Series instead of latest values.
        Useful for charting, backtesting, or analyzing volatility evolution over time.

        Returns:
            Dictionary with keys matching compute_all() but values are Series

        Example:
            >>> analyzer = VolatilityAnalyzer(df)
            >>> series = analyzer.compute_all_series()
            >>> hv_20_series = series['hv_20']
            >>> # Plot volatility evolution
            >>> import matplotlib.pyplot as plt
            >>> hv_20_series.plot()
            >>> plt.title("20-Day Historical Volatility")
            >>> plt.show()
        """
        try:
            hv_10 = calculate_realized_volatility(self.returns, window=10)
            hv_20 = calculate_realized_volatility(self.returns, window=20)
            hv_60 = calculate_realized_volatility(self.returns, window=60)

            parkinson_vol_20 = calculate_parkinson_volatility(
                self.df["high"], self.df["low"], window=20
            )

            garman_klass_vol_20 = calculate_garman_klass_volatility(
                self.df["open"],
                self.df["high"],
                self.df["low"],
                self.df["close"],
                window=20,
            )

            # Vol regime as series
            vol_regime_ratio = hv_20 / hv_60.replace(0, np.nan)

            # Create boolean series for vol expanding
            vol_expanding = hv_20 > hv_60

            # Classify trend for each row
            def classify_trend(ratio):
                if pd.isna(ratio):
                    return None
                if ratio > 1.1:
                    return "expanding"
                elif ratio < 0.9:
                    return "compressing"
                else:
                    return "stable"

            vol_trend = vol_regime_ratio.apply(classify_trend)

            logger.debug("Volatility time series computed")

            return {
                "hv_10": hv_10,
                "hv_20": hv_20,
                "hv_60": hv_60,
                "parkinson_vol_20": parkinson_vol_20,
                "garman_klass_vol_20": garman_klass_vol_20,
                "vol_regime_ratio": vol_regime_ratio,
                "vol_expanding": vol_expanding,
                "vol_trend": vol_trend,
            }

        except Exception as e:
            logger.error(f"Error computing volatility time series: {e}")
            raise
