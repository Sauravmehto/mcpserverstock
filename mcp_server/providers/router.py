"""Provider routing and fallback orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TypeVar

from mcp_server.providers.base import BaseDataProvider
from mcp_server.schemas.models import FundamentalsData, NewsSentimentData, OHLCVBar, PriceData, TickerType

LOGGER = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass
class ProviderRouter:
    """Route requests to providers and apply fallback strategy."""

    primary: BaseDataProvider
    secondary: BaseDataProvider

    def detect_ticker_type(self, ticker: str) -> TickerType:
        """Rough ticker classification for stock/ETF/crypto."""

        normalized = ticker.upper().strip()
        if normalized.endswith("USD") and "-" in normalized:
            return "crypto"
        if normalized in {"SPY", "QQQ", "DIA", "VTI", "IWM", "GLD", "TLT"}:
            return "etf"
        return "stock"

    async def _with_fallback(self, method_name: str, *args: object) -> T | None:
        """Try primary provider first, then secondary on failure or empty result."""

        primary_method = getattr(self.primary, method_name)
        secondary_method = getattr(self.secondary, method_name)
        try:
            primary_result = await primary_method(*args)
            if primary_result:
                return primary_result
        except Exception as error:  # noqa: BLE001
            LOGGER.warning("Primary provider failure", extra={"provider": self.primary.name, "error": str(error)})

        try:
            return await secondary_method(*args)
        except Exception as error:  # noqa: BLE001
            LOGGER.error("Secondary provider failure", extra={"provider": self.secondary.name, "error": str(error)})
            return None

    async def get_price(self, ticker: str) -> PriceData | None:
        """Get latest price with fallback."""

        return await self._with_fallback("get_price", ticker)

    async def get_ohlcv(self, ticker: str, timeframe: str) -> list[OHLCVBar]:
        """Get OHLCV bars with fallback."""

        result = await self._with_fallback("get_ohlcv", ticker, timeframe)
        return result if isinstance(result, list) else []

    async def get_technicals(self, ticker: str, timeframe: str) -> dict[str, float | None]:
        """Get technicals with fallback."""

        result = await self._with_fallback("get_technicals", ticker, timeframe)
        return result if isinstance(result, dict) else {}

    async def get_fundamentals(self, ticker: str) -> FundamentalsData | None:
        """Get fundamentals with fallback."""

        return await self._with_fallback("get_fundamentals", ticker)

    async def get_news_sentiment(self, ticker: str) -> NewsSentimentData | None:
        """Get news sentiment with fallback."""

        return await self._with_fallback("get_news_sentiment", ticker)


