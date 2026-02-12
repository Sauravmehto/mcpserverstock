"""Tests for trading tool registration and text formatting behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
import asyncio

from mcp_server.providers.router import RoutedData
from mcp_server.schemas.models import PriceData
from mcp_server.tools.stock_tools import register_stock_tools


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, name: str):
        def _decorator(func):
            self.tools[name] = func
            return func

        return _decorator


class _FakeRouter:
    async def get_price(self, ticker: str):  # pragma: no cover
        _ = ticker
        return None

    async def get_ohlcv(self, ticker: str, timeframe: str):  # pragma: no cover
        _ = ticker, timeframe
        return []

    async def get_fundamentals(self, ticker: str):  # pragma: no cover
        _ = ticker
        return None

    async def get_news_sentiment(self, ticker: str):  # pragma: no cover
        _ = ticker
        return None

    async def get_price_routed(self, ticker: str) -> RoutedData[PriceData]:
        _ = ticker
        return RoutedData(
            data=PriceData(
                ticker="AAPL",
                price=196.12,
                currency="USD",
                timestamp=datetime.now(UTC),
                source="finnhub",
            ),
            source="finnhub",
            fallback_warning="Primary provider (alpha_vantage) no data returned; using fallback provider (finnhub).",
        )

    async def get_quote_routed(self, ticker: str):  # pragma: no cover
        _ = ticker
        return RoutedData(data=None)

    async def get_company_profile_routed(self, ticker: str):  # pragma: no cover
        _ = ticker
        return RoutedData(data=None)

    async def get_candles_routed(self, ticker: str, timeframe: str, limit: int = 60):  # pragma: no cover
        _ = ticker, timeframe, limit
        return RoutedData(data=[])

    async def get_stock_news_routed(self, ticker: str, limit: int = 10):  # pragma: no cover
        _ = ticker, limit
        return RoutedData(data=None)

    async def get_rsi_routed(self, ticker: str, timeframe: str = "swing"):  # pragma: no cover
        _ = ticker, timeframe
        return RoutedData(data=None)

    async def get_macd_routed(self, ticker: str, timeframe: str = "swing"):  # pragma: no cover
        _ = ticker, timeframe
        return RoutedData(data=None)

    async def get_key_financials_routed(self, ticker: str):  # pragma: no cover
        _ = ticker
        return RoutedData(data=None)


class _FakeClaudeEngine:
    async def build_sections(self, **_: object):  # pragma: no cover
        raise RuntimeError("not used in this test")


def test_get_stock_price_includes_source_and_fallback_warning() -> None:
    mcp = _FakeMCP()
    router = _FakeRouter()
    register_stock_tools(
        mcp=mcp,  # type: ignore[arg-type]
        router=router,  # type: ignore[arg-type]
        claude_engine=_FakeClaudeEngine(),  # type: ignore[arg-type]
        settings=SimpleNamespace(scoring_weights=None),  # type: ignore[arg-type]
    )

    get_stock_price = mcp.tools["get_stock_price"]
    result = asyncio.run(get_stock_price("aapl"))  # type: ignore[operator]
    assert "AAPL: $196.12" in result
    assert "source: finnhub" in result
    assert "warning:" in result

