"""Provider abstraction for market data integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from mcp_server.schemas.models import (
    CompanyProfileData,
    FundamentalsData,
    KeyFinancialsData,
    MACDData,
    NewsSentimentData,
    OHLCVBar,
    PriceData,
    QuoteData,
    RSIData,
    StockNewsData,
)


class BaseDataProvider(ABC):
    """Abstract provider interface."""

    name: str

    @abstractmethod
    async def get_price(self, ticker: str) -> PriceData | None:
        """Fetch latest price."""

    @abstractmethod
    async def get_quote(self, ticker: str) -> QuoteData | None:
        """Fetch quote snapshot."""

    @abstractmethod
    async def get_company_profile(self, ticker: str) -> CompanyProfileData | None:
        """Fetch company profile."""

    @abstractmethod
    async def get_ohlcv(self, ticker: str, timeframe: str) -> list[OHLCVBar]:
        """Fetch historical OHLCV bars."""

    @abstractmethod
    async def get_candles(self, ticker: str, timeframe: str, limit: int = 60) -> list[OHLCVBar]:
        """Fetch historical candles for trading tools."""

    @abstractmethod
    async def get_stock_news(self, ticker: str, limit: int = 10) -> StockNewsData | None:
        """Fetch recent stock news."""

    @abstractmethod
    async def get_rsi(self, ticker: str, timeframe: str = "swing") -> RSIData | None:
        """Fetch RSI indicator."""

    @abstractmethod
    async def get_macd(self, ticker: str, timeframe: str = "swing") -> MACDData | None:
        """Fetch MACD indicator."""

    @abstractmethod
    async def get_key_financials(self, ticker: str) -> KeyFinancialsData | None:
        """Fetch key financials."""

    @abstractmethod
    async def get_technicals(self, ticker: str, timeframe: str) -> dict[str, float | None]:
        """Fetch provider-native technicals where available."""

    @abstractmethod
    async def get_fundamentals(self, ticker: str) -> FundamentalsData | None:
        """Fetch fundamentals snapshot."""

    @abstractmethod
    async def get_news_sentiment(self, ticker: str) -> NewsSentimentData | None:
        """Fetch sentiment data."""


