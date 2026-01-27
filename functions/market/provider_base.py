"""
Abstract base class for market data providers.

This module defines the MarketDataProvider abstract base class that all concrete
market data providers must implement. Providers are responsible for fetching
current prices, historical price data, options chains, and ticker information
from market data sources (e.g., Yahoo Finance, other APIs).

All error handling is done with logging and None returns (no exceptions raised to
the caller). This allows graceful degradation if some data is unavailable.

Abstract Methods (must be implemented by subclasses):
    - get_current_price(ticker: str) -> Optional[float]
    - get_price_history(ticker: str, lookback_days: int = 365) -> Optional[List[PriceBar]]
    - get_options_expirations(ticker: str) -> List[date]
    - get_options_chain(ticker: str, expiration: date) -> Optional[OptionsChain]
    - get_ticker_info(ticker: str) -> Optional[TickerInfo]

Default Implementations (can be overridden for efficiency):
    - get_batch_current_prices(tickers: List[str]) -> Dict[str, Optional[float]]
    - get_batch_price_history(tickers: List[str], lookback_days: int) -> Dict
    - get_full_snapshot(ticker: str) -> Optional[MarketSnapshot]

Usage:
    class YahooFinanceProvider(MarketDataProvider):
        def get_current_price(self, ticker: str) -> Optional[float]:
            # Implementation using yfinance
            pass

        # Implement other abstract methods...

    provider = YahooFinanceProvider()
    price = provider.get_current_price("AAPL")
    if price is not None:
        print(f"AAPL: ${price}")
"""

from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from typing import Optional, List, Dict
from functions.market.models import PriceBar, OptionsChain, TickerInfo, MarketSnapshot
from functions.util.logging_setup import get_logger

logger = get_logger(__name__)


# ============================================================================
# Abstract Base Class
# ============================================================================
class MarketDataProvider(ABC):
    """Abstract base class for market data providers.

    All concrete implementations must provide:
    - get_current_price(): Fetch current price for a single ticker
    - get_price_history(): Fetch historical OHLCV data
    - get_options_expirations(): List available expiration dates
    - get_options_chain(): Fetch complete options chain for expiration
    - get_ticker_info(): Fetch company information

    Subclasses can optionally override batch and snapshot methods for efficiency.

    Error Handling:
        All methods return None on errors, never raise exceptions. This allows
        graceful degradation when partial data is unavailable. Warnings are
        logged for debugging.

    Example:
        >>> class DemoProvider(MarketDataProvider):
        ...     def get_current_price(self, ticker: str) -> Optional[float]:
        ...         return 150.50
        ...     def get_price_history(self, ticker: str, lookback_days: int = 365):
        ...         return None  # Not implemented
        ...     def get_options_expirations(self, ticker: str) -> list[date]:
        ...         return []
        ...     def get_options_chain(self, ticker: str, expiration: date):
        ...         return None
        ...     def get_ticker_info(self, ticker: str):
        ...         return None
        >>>
        >>> provider = DemoProvider()
        >>> price = provider.get_current_price("AAPL")
        >>> print(f"Current price: ${price}")
    """

    # ========================================================================
    # Abstract Methods (must be implemented by subclasses)
    # ========================================================================

    @abstractmethod
    def get_current_price(self, ticker: str) -> Optional[float]:
        """Fetch the current market price for a ticker.

        Retrieves the most recent bid/ask/last price for a security.

        Args:
            ticker: Ticker symbol (e.g., "AAPL", "SPY")

        Returns:
            Current price as float, or None if fetch failed.
            The returned value should be the last/mid price, typically the
            last traded price or mid-point of bid-ask spread.

        Example:
            >>> provider = YahooFinanceProvider()
            >>> price = provider.get_current_price("AAPL")
            >>> if price is not None:
            ...     print(f"AAPL current price: ${price}")
        """
        pass

    @abstractmethod
    def get_price_history(self, ticker: str, lookback_days: int = 365) -> Optional[List[PriceBar]]:
        """Fetch historical price data for a ticker.

        Retrieves daily OHLCV (open, high, low, close, volume) data for the
        specified lookback period. Bars should be ordered chronologically
        from oldest to newest.

        Args:
            ticker: Ticker symbol (e.g., "AAPL", "SPY")
            lookback_days: Number of days of history to fetch (default: 365)

        Returns:
            List of PriceBar objects ordered chronologically (oldest first),
            or None if fetch failed.

        Example:
            >>> provider = YahooFinanceProvider()
            >>> bars = provider.get_price_history("AAPL", lookback_days=252)
            >>> if bars:
            ...     latest = bars[-1]
            ...     print(f"Latest close: ${latest.close}")
        """
        pass

    @abstractmethod
    def get_options_expirations(self, ticker: str) -> List[date]:
        """Fetch available options expiration dates for a ticker.

        Returns the list of all expiration dates available for options on this
        underlying. If no options exist, returns empty list (not None).

        Args:
            ticker: Ticker symbol (e.g., "AAPL", "SPY")

        Returns:
            List of date objects for available expirations, ordered chronologically.
            Returns empty list [] if no expirations available or on error.
            Never returns None - worst case is empty list.

        Example:
            >>> provider = YahooFinanceProvider()
            >>> expirations = provider.get_options_expirations("AAPL")
            >>> if expirations:
            ...     next_exp = expirations[0]
            ...     print(f"Next expiration: {next_exp}")
        """
        pass

    @abstractmethod
    def get_options_chain(self, ticker: str, expiration: date) -> Optional[OptionsChain]:
        """Fetch the complete options chain for a given expiration.

        Retrieves all calls and puts for the specified underlying and expiration.
        Includes strike prices, bid/ask, volume, open interest, and Greeks if
        available.

        Args:
            ticker: Ticker symbol (e.g., "AAPL", "SPY")
            expiration: Expiration date to fetch

        Returns:
            OptionsChain object containing all calls and puts, or None if fetch failed.
            The returned OptionsChain may have empty calls/puts lists if no contracts
            exist.

        Example:
            >>> from datetime import date
            >>> provider = YahooFinanceProvider()
            >>> chain = provider.get_options_chain("AAPL", date(2026, 2, 20))
            >>> if chain:
            ...     atm_calls = [c for c in chain.calls if 440 <= c.strike <= 450]
            ...     print(f"ATM calls: {len(atm_calls)}")
        """
        pass

    @abstractmethod
    def get_ticker_info(self, ticker: str) -> Optional[TickerInfo]:
        """Fetch company and ticker information.

        Retrieves company name, sector, industry, market cap, P/E ratio, and
        other fundamental data for the ticker.

        Args:
            ticker: Ticker symbol (e.g., "AAPL", "SPY")

        Returns:
            TickerInfo object with company data, or None if fetch failed.
            Partial information is acceptable (e.g., some fields may be None
            if not available).

        Example:
            >>> provider = YahooFinanceProvider()
            >>> info = provider.get_ticker_info("AAPL")
            >>> if info:
            ...     print(f"{info.company_name} ({info.symbol})")
            ...     print(f"Sector: {info.sector}")
        """
        pass

    # ========================================================================
    # Default Implementations (can be overridden)
    # ========================================================================

    def get_batch_current_prices(self, tickers: List[str]) -> Dict[str, Optional[float]]:
        """Fetch current prices for multiple tickers.

        Default implementation calls get_current_price() for each ticker.
        Subclasses may override for efficiency (e.g., batch API calls).

        Args:
            tickers: List of ticker symbols to fetch

        Returns:
            Dictionary mapping ticker -> price (or None if fetch failed).
            All input tickers are included in result dict.

        Example:
            >>> provider = YahooFinanceProvider()
            >>> prices = provider.get_batch_current_prices(["AAPL", "MSFT", "GOOGL"])
            >>> for ticker, price in prices.items():
            ...     if price is not None:
            ...         print(f"{ticker}: ${price}")
        """
        result: Dict[str, Optional[float]] = {}
        for ticker in tickers:
            try:
                price = self.get_current_price(ticker)
                result[ticker] = price
            except Exception as e:
                logger.warning(f"Error fetching price for {ticker}: {e}")
                result[ticker] = None
        return result

    def get_batch_price_history(
        self, tickers: List[str], lookback_days: int = 365
    ) -> Dict[str, Optional[List[PriceBar]]]:
        """Fetch price history for multiple tickers.

        Default implementation calls get_price_history() for each ticker.
        Subclasses may override for efficiency (e.g., parallel fetching).

        Args:
            tickers: List of ticker symbols to fetch
            lookback_days: Days of history for each ticker (default: 365)

        Returns:
            Dictionary mapping ticker -> price history (or None if fetch failed).
            All input tickers are included in result dict.

        Example:
            >>> provider = YahooFinanceProvider()
            >>> histories = provider.get_batch_price_history(["AAPL", "MSFT"], lookback_days=252)
            >>> for ticker, bars in histories.items():
            ...     if bars:
            ...         latest = bars[-1]
            ...         print(f"{ticker} latest close: ${latest.close}")
        """
        result: Dict[str, Optional[List[PriceBar]]] = {}
        for ticker in tickers:
            try:
                history = self.get_price_history(ticker, lookback_days)
                result[ticker] = history
            except Exception as e:
                logger.warning(f"Error fetching history for {ticker}: {e}")
                result[ticker] = None
        return result

    def get_full_snapshot(self, ticker: str) -> Optional[MarketSnapshot]:
        """Fetch complete market data snapshot for a ticker.

        Combines current price, ticker info, and available options expirations
        into a single snapshot. Gracefully handles partial data (some fields
        may be None if fetch failed).

        Default implementation calls individual methods and combines results.
        Subclasses may override for efficiency.

        Args:
            ticker: Ticker symbol to fetch data for

        Returns:
            MarketSnapshot with available data, or None if all fetches failed.
            Partial snapshots are acceptable (e.g., missing ticker info is OK).

        Example:
            >>> provider = YahooFinanceProvider()
            >>> snapshot = provider.get_full_snapshot("AAPL")
            >>> if snapshot:
            ...     print(f"Price: ${snapshot.price}")
            ...     print(f"Options chains: {len(snapshot.options_chains)}")
        """
        try:
            # Fetch all components
            current_price = self.get_current_price(ticker)
            ticker_info = self.get_ticker_info(ticker)
            expirations = self.get_options_expirations(ticker)

            # If we got no price data, we can't create a valid snapshot
            if current_price is None:
                logger.warning(f"Cannot create snapshot without price data: {ticker}")
                return None

            # Build snapshot with whatever data we got
            # Note: options_chains will be empty initially, can be populated later
            snapshot = MarketSnapshot(
                ticker=ticker,
                price=current_price,
                timestamp=datetime.now(timezone.utc),
                price_history=[],
                options_chains={},
            )
            return snapshot

        except Exception as e:
            logger.warning(f"Error creating snapshot for {ticker}: {e}")
            return None
