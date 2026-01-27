"""
Pydantic models for market data and options chains.

This module defines the data structures for representing market data, option contracts,
options chains, and ticker information. These models provide validation and serialization
for all market data used throughout the application.

Models:
    - PriceBar: OHLCV (Open, High, Low, Close, Volume) price data
    - OptionContract: Single option contract with Greeks and pricing
    - OptionsChain: Complete options chain for an expiration date
    - MarketSnapshot: Full market data snapshot with history and chains
    - TickerInfo: Company information and fundamentals

Usage:
    from functions.market.models import MarketSnapshot, OptionsChain, PriceBar
    from datetime import datetime, date, timezone

    # Create a price bar
    price_bar = PriceBar(
        timestamp=datetime.now(timezone.utc),
        open=150.0,
        high=152.5,
        low=149.5,
        close=151.0,
        volume=1000000
    )

    # Create an option contract
    from functions.market.models import OptionContract
    call = OptionContract(
        strike=150.0,
        option_type="call",
        bid=2.50,
        ask=2.60,
        volume=500,
        open_interest=1000,
        implied_volatility=0.25
    )

    # Create a full market snapshot
    snapshot = MarketSnapshot(
        ticker="AAPL",
        timestamp=datetime.now(timezone.utc),
        price=151.0,
        price_history=[price_bar],
        options_chains={}
    )
"""

from datetime import datetime, date, timezone
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# PRICE DATA MODELS
# ============================================================================


class PriceBar(BaseModel):
    """OHLCV (Open, High, Low, Close, Volume) price data for a time period.

    Attributes:
        timestamp: UTC datetime when the bar period ends
        open: Opening price for the period
        high: Highest price during the period
        low: Lowest price during the period
        close: Closing price for the period
        volume: Trading volume during the period (number of shares)

    Note:
        All prices are in the asset's native currency. Timestamps are always
        in UTC for consistency across timezones.
    """

    timestamp: datetime = Field(
        ..., description="UTC datetime when the bar period ends"
    )
    open: float = Field(..., gt=0, description="Opening price")
    high: float = Field(..., gt=0, description="Highest price in period")
    low: float = Field(..., gt=0, description="Lowest price in period")
    close: float = Field(..., gt=0, description="Closing price")
    volume: int = Field(..., ge=0, description="Trading volume in shares")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp_is_utc(cls, v: datetime) -> datetime:
        """Ensure timestamp has UTC timezone information.

        Args:
            v: The datetime to validate

        Returns:
            The datetime with UTC timezone if not present

        Raises:
            ValueError: If timezone cannot be determined (ambiguous)
        """
        if v.tzinfo is None:
            # Assume UTC if no timezone specified
            return v.replace(tzinfo=timezone.utc)
        elif v.tzinfo != timezone.utc:
            # Convert to UTC if different timezone
            return v.astimezone(timezone.utc)
        return v

    @field_validator("high")
    @classmethod
    def validate_high_greater_than_low(cls, v: float, info) -> float:
        """Ensure high price is greater than or equal to low price."""
        if "low" in info.data and v < info.data["low"]:
            raise ValueError("High price must be >= low price")
        return v

    @field_validator("close")
    @classmethod
    def validate_close_within_range(cls, v: float, info) -> float:
        """Ensure close price is within high/low range."""
        data = info.data
        if "high" in data and "low" in data:
            if v > data["high"] or v < data["low"]:
                raise ValueError("Close price must be between low and high")
        return v

    class Config:
        """Pydantic configuration."""
        extra = "forbid"


# ============================================================================
# OPTION CONTRACT MODELS
# ============================================================================


class OptionContract(BaseModel):
    """Single option contract with pricing and Greeks.

    Attributes:
        strike: Strike price of the option
        option_type: "call" or "put"
        bid: Best bid price (what buyers will pay)
        ask: Best ask price (what sellers want)
        mid: Midpoint between bid and ask (calculated from bid/ask)
        volume: Daily trading volume
        open_interest: Total open interest contracts
        implied_volatility: Implied volatility as decimal (0.25 = 25%)
        delta: Rate of price change relative to underlying (-1 to 1)
        gamma: Rate of change of delta (how delta changes)
        theta: Time decay value per day (typically negative for longs)
        vega: Sensitivity to 1% change in volatility
        rho: Sensitivity to interest rate changes
        spread_pct: Bid-ask spread as percentage of midpoint

    Note:
        Greeks are optional because they may not be available for all
        options (especially illiquid or recently listed). Bid-ask spread
        is calculated automatically from bid and ask prices.
    """

    strike: float = Field(..., gt=0, description="Strike price")
    option_type: str = Field(
        ...,
        description="Type of option: 'call' or 'put'",
    )
    bid: float = Field(..., ge=0, description="Best bid price")
    ask: float = Field(..., ge=0, description="Best ask price")
    volume: int = Field(default=0, ge=0, description="Daily trading volume")
    open_interest: int = Field(default=0, ge=0, description="Total open interest")
    implied_volatility: Optional[float] = Field(
        default=None, ge=0, description="Implied volatility (0.25 = 25%)"
    )
    delta: Optional[float] = Field(
        default=None, description="Delta value (-1 to 1)"
    )
    gamma: Optional[float] = Field(default=None, ge=0, description="Gamma value")
    theta: Optional[float] = Field(
        default=None, description="Theta/time decay per day"
    )
    vega: Optional[float] = Field(default=None, ge=0, description="Vega value")
    rho: Optional[float] = Field(default=None, description="Rho value")

    @field_validator("option_type")
    @classmethod
    def validate_option_type(cls, v: str) -> str:
        """Ensure option_type is either 'call' or 'put'.

        Args:
            v: The option type string

        Returns:
            The lowercase option type

        Raises:
            ValueError: If option_type is not 'call' or 'put'
        """
        v_lower = v.lower()
        if v_lower not in ("call", "put"):
            raise ValueError("option_type must be 'call' or 'put'")
        return v_lower

    @field_validator("ask")
    @classmethod
    def validate_ask_greater_than_bid(cls, v: float, info) -> float:
        """Ensure ask price is >= bid price.

        Args:
            v: The ask price
            info: Validation context with other field values

        Returns:
            The ask price if valid

        Raises:
            ValueError: If ask < bid
        """
        if "bid" in info.data and v < info.data["bid"]:
            raise ValueError("Ask price must be >= bid price")
        return v

    @field_validator("delta")
    @classmethod
    def validate_delta_range(cls, v: Optional[float]) -> Optional[float]:
        """Ensure delta is within valid range [-1, 1].

        Args:
            v: The delta value

        Returns:
            The delta if valid, or None if not provided

        Raises:
            ValueError: If delta is outside [-1, 1]
        """
        if v is not None and not (-1 <= v <= 1):
            raise ValueError("Delta must be between -1 and 1")
        return v

    @property
    def mid(self) -> float:
        """Calculate midpoint between bid and ask prices.

        Returns:
            The midpoint price (average of bid and ask)

        Note:
            If both bid and ask are 0, returns 0.
        """
        if self.bid == 0 and self.ask == 0:
            return 0.0
        # If only one side has a price, use that; otherwise average
        if self.bid == 0:
            return self.ask
        if self.ask == 0:
            return self.bid
        return (self.bid + self.ask) / 2.0

    @property
    def spread_pct(self) -> float:
        """Calculate bid-ask spread as percentage of midpoint.

        Returns:
            Spread percentage (e.g., 1.5 for 1.5% spread)

        Note:
            Returns 0.0 if spread cannot be calculated (e.g., zero mid price).
        """
        mid = self.mid
        if mid == 0:
            return 0.0
        spread = self.ask - self.bid
        return (spread / mid) * 100.0

    class Config:
        """Pydantic configuration."""
        extra = "forbid"


# ============================================================================
# OPTIONS CHAIN MODELS
# ============================================================================


class OptionsChain(BaseModel):
    """Complete options chain for a single expiration date.

    Attributes:
        underlying_price: Current price of the underlying asset
        expiration: Expiration date of all options in this chain
        calls: List of call option contracts
        puts: List of put option contracts
        atm_strike: At-the-money strike price (closest to underlying_price)

    Note:
        The at-the-money (ATM) strike is determined as the strike closest
        to the underlying price. This is useful for finding near-ATM
        options for strategies like straddles and strangles.
    """

    underlying_price: float = Field(..., gt=0, description="Current underlying price")
    expiration: date = Field(..., description="Expiration date")
    calls: List[OptionContract] = Field(default_factory=list, description="Call options")
    puts: List[OptionContract] = Field(default_factory=list, description="Put options")
    atm_strike: float = Field(
        ..., gt=0, description="At-the-money strike (closest to spot)"
    )

    @field_validator("expiration")
    @classmethod
    def validate_expiration_is_future(cls, v: date) -> date:
        """Ensure expiration date is in the future (not in the past).

        Args:
            v: The expiration date

        Returns:
            The expiration date

        Raises:
            ValueError: If expiration is before today
        """
        today = date.today()
        if v < today:
            raise ValueError(f"Expiration date must be in the future, got {v}")
        return v

    @field_validator("atm_strike")
    @classmethod
    def validate_atm_strike_exists(cls, v: float, info) -> float:
        """Ensure ATM strike is reasonable given underlying price.

        Args:
            v: The ATM strike price
            info: Validation context with other field values

        Returns:
            The ATM strike if valid

        Note:
            ATM strike should be close to underlying_price. Allows some
            deviation to handle edge cases, but validates it's reasonable.
        """
        if "underlying_price" in info.data:
            underlying = info.data["underlying_price"]
            # Allow up to 50% deviation from underlying (handles extreme cases)
            ratio = v / underlying
            if ratio < 0.5 or ratio > 2.0:
                raise ValueError(
                    f"ATM strike {v} is too far from underlying price {underlying}"
                )
        return v

    def get_call_by_strike(self, strike: float) -> Optional[OptionContract]:
        """Get call option by strike price.

        Args:
            strike: The strike price to find

        Returns:
            The OptionContract if found, None otherwise
        """
        for call in self.calls:
            if call.strike == strike:
                return call
        return None

    def get_put_by_strike(self, strike: float) -> Optional[OptionContract]:
        """Get put option by strike price.

        Args:
            strike: The strike price to find

        Returns:
            The OptionContract if found, None otherwise
        """
        for put in self.puts:
            if put.strike == strike:
                return put
        return None

    class Config:
        """Pydantic configuration."""
        extra = "forbid"


# ============================================================================
# TICKER INFO MODELS
# ============================================================================


class TickerInfo(BaseModel):
    """Company information and fundamental data.

    Attributes:
        symbol: Stock ticker symbol
        name: Company name
        sector: Business sector (e.g., "Technology")
        industry: Specific industry (e.g., "Software - Infrastructure")
        market_cap: Market capitalization in USD (optional)
        pe_ratio: Price-to-earnings ratio (optional)

    Note:
        Optional fields are often not available for all securities,
        particularly for thinly traded or recently listed stocks.
    """

    symbol: str = Field(
        ..., min_length=1, max_length=10, description="Stock ticker symbol"
    )
    name: str = Field(..., min_length=1, description="Company name")
    sector: str = Field(
        default="Unknown",
        description="Business sector",
    )
    industry: str = Field(
        default="Unknown",
        description="Specific industry",
    )
    market_cap: Optional[float] = Field(
        default=None, ge=0, description="Market capitalization in USD"
    )
    pe_ratio: Optional[float] = Field(
        default=None, gt=0, description="Price-to-earnings ratio"
    )

    @field_validator("symbol")
    @classmethod
    def validate_symbol_format(cls, v: str) -> str:
        """Ensure symbol is uppercase alphanumeric.

        Args:
            v: The symbol

        Returns:
            The uppercase symbol

        Raises:
            ValueError: If symbol contains invalid characters
        """
        v_upper = v.upper()
        if not all(c.isalnum() or c in ("-", ".") for c in v_upper):
            raise ValueError(f"Invalid symbol format: {v}")
        return v_upper

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        """Ensure company name is not empty after stripping.

        Args:
            v: The company name

        Returns:
            The stripped name

        Raises:
            ValueError: If name is empty after stripping
        """
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Company name cannot be empty")
        return v_stripped

    class Config:
        """Pydantic configuration."""
        extra = "forbid"


# ============================================================================
# MARKET SNAPSHOT MODELS
# ============================================================================


class MarketSnapshot(BaseModel):
    """Complete market data snapshot for a single ticker.

    Attributes:
        ticker: Stock ticker symbol (e.g., "AAPL")
        timestamp: UTC datetime when snapshot was created
        price: Current stock price
        price_history: List of historical price bars
        options_chains: Dictionary mapping expiration date -> OptionsChain

    Note:
        The price_history list should be ordered chronologically (oldest first).
        options_chains uses expiration dates as keys for easy lookup of specific
        expiration chains.
    """

    ticker: str = Field(
        ..., min_length=1, max_length=10, description="Stock ticker symbol"
    )
    timestamp: datetime = Field(
        ..., description="UTC datetime when snapshot was created"
    )
    price: float = Field(..., gt=0, description="Current stock price")
    price_history: List[PriceBar] = Field(
        default_factory=list, description="Historical OHLCV data"
    )
    options_chains: Dict[date, OptionsChain] = Field(
        default_factory=dict, description="Options chains by expiration date"
    )

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp_is_utc(cls, v: datetime) -> datetime:
        """Ensure timestamp has UTC timezone.

        Args:
            v: The datetime to validate

        Returns:
            The datetime with UTC timezone if not present
        """
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        elif v.tzinfo != timezone.utc:
            return v.astimezone(timezone.utc)
        return v

    @field_validator("ticker")
    @classmethod
    def validate_ticker_format(cls, v: str) -> str:
        """Ensure ticker is uppercase alphanumeric.

        Args:
            v: The ticker symbol

        Returns:
            The uppercase ticker

        Raises:
            ValueError: If ticker contains invalid characters
        """
        v_upper = v.upper()
        # Allow letters, numbers, and hyphens/periods (for special cases)
        if not all(c.isalnum() or c in ("-", ".") for c in v_upper):
            raise ValueError(f"Invalid ticker format: {v}")
        return v_upper

    def get_chain_by_expiration(self, expiration: date) -> Optional[OptionsChain]:
        """Get options chain for a specific expiration date.

        Args:
            expiration: The expiration date to look up

        Returns:
            The OptionsChain if found, None otherwise
        """
        return self.options_chains.get(expiration)

    def get_latest_price_bar(self) -> Optional[PriceBar]:
        """Get the most recent price bar from history.

        Returns:
            The most recent PriceBar, or None if history is empty
        """
        if not self.price_history:
            return None
        # Assume list is ordered chronologically (oldest first)
        return self.price_history[-1]

    class Config:
        """Pydantic configuration."""
        extra = "forbid"
