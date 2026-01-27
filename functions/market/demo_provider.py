"""
Demo market data provider for offline/demo scans.

Provides deterministic but realistic-looking price, option chain, and ticker info
without calling external APIs. This lets the scheduler run even when no live
provider is configured.
"""

from __future__ import annotations

from datetime import datetime, timedelta, date, timezone
from typing import List, Optional

from functions.market.models import (
    MarketSnapshot,
    OptionContract,
    OptionsChain,
    PriceBar,
    TickerInfo,
)
from functions.market.provider_base import MarketDataProvider


class DemoMarketDataProvider(MarketDataProvider):
    """Simple provider that returns synthetic market data for any ticker."""

    def __init__(self, base_price: float = 150.0, iv: float = 0.25) -> None:
        self.base_price = base_price
        self.iv = iv

    def get_current_price(self, ticker: str) -> Optional[float]:
        return float(self.base_price)

    def get_price_history(
        self, ticker: str, lookback_days: int = 30
    ) -> Optional[List[PriceBar]]:
        now = datetime.now(timezone.utc)
        granularity = max(lookback_days, 1)
        history: List[PriceBar] = []

        for day in range(granularity):
            timestamp = now - timedelta(days=day)
            variation = (day % 5) * 0.1
            price = self.base_price + variation
            history.append(
                PriceBar(
                    timestamp=timestamp,
                    open=price - 0.5,
                    high=price + 0.7,
                    low=price - 0.7,
                    close=price,
                    volume=1000000,
                )
            )

        return list(reversed(history))

    def get_options_expirations(self, ticker: str) -> List[date]:
        today = date.today()
        return [today + timedelta(days=7), today + timedelta(days=14), today + timedelta(days=30)]

    def get_options_chain(self, ticker: str, expiration: date) -> Optional[OptionsChain]:
        calls: List[OptionContract] = []
        puts: List[OptionContract] = []
        strikes = [self.base_price - 5, self.base_price, self.base_price + 5]

        for strike in strikes:
            calls.append(
                OptionContract(
                    strike=strike,
                    option_type="call",
                    bid=max(0.01, self.base_price - strike + 1.0),
                    ask=max(0.01, self.base_price - strike + 1.3),
                    volume=500,
                    open_interest=1000,
                    implied_volatility=self.iv,
                )
            )
            puts.append(
                OptionContract(
                    strike=strike,
                    option_type="put",
                    bid=max(0.01, strike - self.base_price + 1.0),
                    ask=max(0.01, strike - self.base_price + 1.3),
                    volume=500,
                    open_interest=1000,
                    implied_volatility=self.iv,
                )
            )

        return OptionsChain(
            ticker=ticker,
            expiration=expiration,
            timestamp=datetime.now(timezone.utc),
            calls=calls,
            puts=puts,
        )

    def get_ticker_info(self, ticker: str) -> Optional[TickerInfo]:
        return TickerInfo(
            ticker=ticker,
            company_name=f"Demo {ticker}",
            sector="Technology",
            industry="Software",
            market_cap=1_000_000_000,
            dividend_yield=0.01,
            earnings_date=None,
        )

    def get_full_snapshot(self, ticker: str) -> Optional[MarketSnapshot]:
        snapshot = super().get_full_snapshot(ticker)
        if snapshot is None:
            return None

        history = self.get_price_history(ticker, lookback_days=30)
        if history:
            snapshot.price_history = history

        expirations = self.get_options_expirations(ticker)
        for exp in expirations:
            chain = self.get_options_chain(ticker, exp)
            if chain:
                snapshot.options_chains[exp.isoformat()] = chain

        return snapshot
