"""Finnhub provider implementation."""

from __future__ import annotations

from datetime import UTC, date, datetime
from statistics import mean
from typing import Any

from mcp_server.providers.base import BaseDataProvider
from mcp_server.schemas.models import FundamentalsData, NewsSentimentData, OHLCVBar, PriceData
from mcp_server.utils.http import HttpClient


class FinnhubProvider(BaseDataProvider):
    """Fetch market and sentiment data from Finnhub."""

    name = "finnhub"
    _base_url = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str, http_client: HttpClient) -> None:
        self._api_key = api_key
        self._http_client = http_client

    async def get_price(self, ticker: str) -> PriceData | None:
        payload = await self._http_client.get_json(
            f"{self._base_url}/quote?symbol={ticker}&token={self._api_key}",
        )
        if not isinstance(payload, dict) or not payload.get("c"):
            return None
        return PriceData(
            ticker=ticker,
            price=float(payload["c"]),
            currency="USD",
            timestamp=datetime.now(UTC),
            source=self.name,
        )

    async def get_ohlcv(self, ticker: str, timeframe: str) -> list[OHLCVBar]:
        resolution = "D"
        if timeframe == "intraday":
            resolution = "60"
        now = int(datetime.now(UTC).timestamp())
        from_ts = now - (60 * 60 * 24 * 365)
        payload = await self._http_client.get_json(
            f"{self._base_url}/stock/candle?symbol={ticker}&resolution={resolution}&from={from_ts}&to={now}&token={self._api_key}",
        )
        if not isinstance(payload, dict) or payload.get("s") != "ok":
            return []
        timestamps = payload.get("t", [])
        opens = payload.get("o", [])
        highs = payload.get("h", [])
        lows = payload.get("l", [])
        closes = payload.get("c", [])
        volumes = payload.get("v", [])
        bars: list[OHLCVBar] = []
        for idx, ts in enumerate(timestamps):
            try:
                bars.append(
                    OHLCVBar(
                        date=datetime.fromtimestamp(int(ts), tz=UTC).date(),
                        open=float(opens[idx]),
                        high=float(highs[idx]),
                        low=float(lows[idx]),
                        close=float(closes[idx]),
                        volume=float(volumes[idx]),
                    ),
                )
            except (IndexError, ValueError, TypeError):
                continue
        return bars

    async def get_technicals(self, ticker: str, timeframe: str) -> dict[str, float | None]:
        _ = ticker, timeframe
        return {"rsi": None, "macd": None, "ema_20": None, "ema_50": None, "ema_200": None}

    async def get_fundamentals(self, ticker: str) -> FundamentalsData | None:
        profile = await self._http_client.get_json(
            f"{self._base_url}/stock/profile2?symbol={ticker}&token={self._api_key}",
        )
        metric_payload = await self._http_client.get_json(
            f"{self._base_url}/stock/metric?symbol={ticker}&metric=all&token={self._api_key}",
        )
        if not isinstance(profile, dict) or not isinstance(metric_payload, dict):
            return None
        metrics = metric_payload.get("metric", {})
        if not isinstance(metrics, dict):
            metrics = {}
        return FundamentalsData(
            ticker=ticker,
            pe=_as_float(metrics.get("peTTM")),
            forward_pe=_as_float(metrics.get("forwardPE")),
            ps=_as_float(metrics.get("psTTM")),
            ev_ebitda=_as_float(metrics.get("evToEbitdaTTM")),
            beta=_as_float(metrics.get("beta")),
            roe=_as_float(metrics.get("roeTTM")),
            debt_to_equity=_as_float(metrics.get("totalDebt/totalEquityQuarterly")),
            gross_margin=_as_float(metrics.get("grossMarginTTM")),
            operating_margin=_as_float(metrics.get("operatingMarginTTM")),
            net_margin=_as_float(metrics.get("netMarginTTM")),
            revenue_yoy=_as_float(metrics.get("revenueGrowthTTMYoy")),
            eps_yoy=_as_float(metrics.get("epsGrowthTTMYoy")),
            forward_eps_growth=_as_float(metrics.get("epsGrowth5Y")),
            revenue_history=[],
            source=self.name,
        )

    async def get_news_sentiment(self, ticker: str) -> NewsSentimentData | None:
        to_date = date.today().isoformat()
        from_date = date.fromordinal(date.today().toordinal() - 30).isoformat()
        payload = await self._http_client.get_json(
            f"{self._base_url}/company-news?symbol={ticker}&from={from_date}&to={to_date}&token={self._api_key}",
        )
        if not isinstance(payload, list):
            return None
        sentiments: list[float] = []
        for item in payload[:30]:
            if isinstance(item, dict):
                sentiment = _as_float(item.get("sentiment"))
                if sentiment is not None:
                    sentiments.append(sentiment)
        return NewsSentimentData(
            ticker=ticker,
            average_sentiment=mean(sentiments) if sentiments else None,
            articles=[],
            source=self.name,
        )


def _as_float(value: Any) -> float | None:
    """Convert value to float safely."""

    if value in (None, "", "None", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


