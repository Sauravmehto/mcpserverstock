"""Provider abstraction for market data integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from mcp_server.schemas.models import (
    FundamentalsData,
    NewsSentimentData,
    OHLCVBar,
    PriceData,
)


class BaseDataProvider(ABC):
    """Abstract provider interface."""

    name: str

    @abstractmethod
    async def get_price(self, ticker: str) -> PriceData | None:
        """Fetch latest price."""

    @abstractmethod
    async def get_ohlcv(self, ticker: str, timeframe: str) -> list[OHLCVBar]:
        """Fetch historical OHLCV bars."""

    @abstractmethod
    async def get_technicals(self, ticker: str, timeframe: str) -> dict[str, float | None]:
        """Fetch provider-native technicals where available."""

    @abstractmethod
    async def get_fundamentals(self, ticker: str) -> FundamentalsData | None:
        """Fetch fundamentals snapshot."""

    @abstractmethod
    async def get_news_sentiment(self, ticker: str) -> NewsSentimentData | None:
        """Fetch sentiment data."""


