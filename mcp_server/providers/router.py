"""Provider routing and fallback orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Generic, TypeVar

from mcp_server.providers.base import BaseDataProvider
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
    TickerType,
)

LOGGER = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass
class RoutedData(Generic[T]):
    """Provider-routed payload with optional fallback notice."""

    data: T | None
    fallback_warning: str | None = None
    source: str | None = None


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

        routed = await self._with_fallback_routed(method_name, *args)
        return routed.data

    async def _with_fallback_routed(self, method_name: str, *args: object) -> RoutedData[T]:
        """Try providers with deterministic fallback notices for tools."""

        primary_method = getattr(self.primary, method_name)
        secondary_method = getattr(self.secondary, method_name)
        primary_reason = "no data returned"
        try:
            primary_result = await primary_method(*args)
            if primary_result:
                return RoutedData(data=primary_result, source=self.primary.name)
        except Exception as error:  # noqa: BLE001
            LOGGER.warning("Primary provider failure", extra={"provider": self.primary.name, "error": str(error)})
            primary_reason = f"request failed ({error})"

        try:
            secondary_result = await secondary_method(*args)
            if secondary_result:
                return RoutedData(
                    data=secondary_result,
                    source=self.secondary.name,
                    fallback_warning=(
                        f"Primary provider ({self.primary.name}) {primary_reason}; using "
                        f"fallback provider ({self.secondary.name})."
                    ),
                )
        except Exception as error:  # noqa: BLE001
            LOGGER.error("Secondary provider failure", extra={"provider": self.secondary.name, "error": str(error)})
            return RoutedData(
                data=None,
                fallback_warning=(
                    f"Both providers failed for {method_name}: "
                    f"{self.primary.name} ({primary_reason}); {self.secondary.name} (request failed: {error})."
                ),
            )
        return RoutedData(
            data=None,
            fallback_warning=(
                f"No provider returned data for {method_name} ({self.primary.name} then {self.secondary.name})."
            ),
        )

    async def get_price(self, ticker: str) -> PriceData | None:
        """Get latest price with fallback."""

        return await self._with_fallback("get_price", ticker)

    async def get_price_routed(self, ticker: str) -> RoutedData[PriceData]:
        """Get latest price with routed metadata."""

        return await self._with_fallback_routed("get_price", ticker)

    async def get_quote(self, ticker: str) -> QuoteData | None:
        """Get quote snapshot with fallback."""

        return await self._with_fallback("get_quote", ticker)

    async def get_quote_routed(self, ticker: str) -> RoutedData[QuoteData]:
        """Get quote snapshot with routed metadata."""

        return await self._with_fallback_routed("get_quote", ticker)

    async def get_company_profile(self, ticker: str) -> CompanyProfileData | None:
        """Get company profile with fallback."""

        return await self._with_fallback("get_company_profile", ticker)

    async def get_company_profile_routed(self, ticker: str) -> RoutedData[CompanyProfileData]:
        """Get company profile with routed metadata."""

        return await self._with_fallback_routed("get_company_profile", ticker)

    async def get_ohlcv(self, ticker: str, timeframe: str) -> list[OHLCVBar]:
        """Get OHLCV bars with fallback."""

        result = await self._with_fallback("get_ohlcv", ticker, timeframe)
        return result if isinstance(result, list) else []

    async def get_candles(self, ticker: str, timeframe: str, limit: int = 60) -> list[OHLCVBar]:
        """Get candles with fallback."""

        result = await self._with_fallback("get_candles", ticker, timeframe, limit)
        return result if isinstance(result, list) else []

    async def get_candles_routed(self, ticker: str, timeframe: str, limit: int = 60) -> RoutedData[list[OHLCVBar]]:
        """Get candles with routed metadata."""

        routed = await self._with_fallback_routed("get_candles", ticker, timeframe, limit)
        bars = routed.data if isinstance(routed.data, list) else []
        return RoutedData(data=bars, fallback_warning=routed.fallback_warning, source=routed.source)

    async def get_stock_news(self, ticker: str, limit: int = 10) -> StockNewsData | None:
        """Get stock news with fallback."""

        return await self._with_fallback("get_stock_news", ticker, limit)

    async def get_stock_news_routed(self, ticker: str, limit: int = 10) -> RoutedData[StockNewsData]:
        """Get stock news with routed metadata."""

        return await self._with_fallback_routed("get_stock_news", ticker, limit)

    async def get_rsi(self, ticker: str, timeframe: str = "swing") -> RSIData | None:
        """Get RSI with fallback."""

        return await self._with_fallback("get_rsi", ticker, timeframe)

    async def get_rsi_routed(self, ticker: str, timeframe: str = "swing") -> RoutedData[RSIData]:
        """Get RSI with routed metadata."""

        return await self._with_fallback_routed("get_rsi", ticker, timeframe)

    async def get_macd(self, ticker: str, timeframe: str = "swing") -> MACDData | None:
        """Get MACD with fallback."""

        return await self._with_fallback("get_macd", ticker, timeframe)

    async def get_macd_routed(self, ticker: str, timeframe: str = "swing") -> RoutedData[MACDData]:
        """Get MACD with routed metadata."""

        return await self._with_fallback_routed("get_macd", ticker, timeframe)

    async def get_key_financials(self, ticker: str) -> KeyFinancialsData | None:
        """Get key financials with fallback."""

        return await self._with_fallback("get_key_financials", ticker)

    async def get_key_financials_routed(self, ticker: str) -> RoutedData[KeyFinancialsData]:
        """Get key financials with routed metadata."""

        return await self._with_fallback_routed("get_key_financials", ticker)

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


