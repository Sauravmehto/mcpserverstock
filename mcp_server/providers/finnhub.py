"""Finnhub provider implementation."""

from __future__ import annotations

from datetime import UTC, date, datetime
from statistics import mean
from typing import Any

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
    StockNewsItem,
)
from mcp_server.utils.http import HttpClient


class FinnhubProvider(BaseDataProvider):
    """Fetch market and sentiment data from Finnhub."""

    name = "finnhub"
    _base_url = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str, http_client: HttpClient) -> None:
        self._api_key = api_key
        self._http_client = http_client

    async def get_price(self, ticker: str) -> PriceData | None:
        quote = await self.get_quote(ticker)
        if not quote or quote.price is None:
            return None
        return PriceData(
            ticker=ticker,
            price=quote.price,
            currency="USD",
            timestamp=quote.timestamp,
            source=self.name,
        )

    async def get_quote(self, ticker: str) -> QuoteData | None:
        payload = await self._http_client.get_json(
            f"{self._base_url}/quote?symbol={ticker}&token={self._api_key}",
        )
        if not isinstance(payload, dict) or not payload.get("c"):
            return None
        timestamp = datetime.now(UTC)
        raw_ts = payload.get("t")
        if raw_ts:
            try:
                timestamp = datetime.fromtimestamp(int(raw_ts), tz=UTC)
            except (TypeError, ValueError, OSError):
                pass
        return QuoteData(
            ticker=ticker,
            price=float(payload["c"]),
            change=_as_float(payload.get("d")),
            change_percent=_as_float(payload.get("dp")),
            high=_as_float(payload.get("h")),
            low=_as_float(payload.get("l")),
            open=_as_float(payload.get("o")),
            previous_close=_as_float(payload.get("pc")),
            timestamp=timestamp,
            source=self.name,
        )

    async def get_company_profile(self, ticker: str) -> CompanyProfileData | None:
        profile = await self._http_client.get_json(
            f"{self._base_url}/stock/profile2?symbol={ticker}&token={self._api_key}",
        )
        if not isinstance(profile, dict) or not profile:
            return None
        ipo = None
        raw_ipo = profile.get("ipo")
        if raw_ipo:
            try:
                ipo = date.fromisoformat(str(raw_ipo))
            except ValueError:
                ipo = None
        return CompanyProfileData(
            ticker=ticker,
            name=str(profile.get("name")) if profile.get("name") else None,
            exchange=str(profile.get("exchange")) if profile.get("exchange") else None,
            industry=str(profile.get("finnhubIndustry")) if profile.get("finnhubIndustry") else None,
            country=str(profile.get("country")) if profile.get("country") else None,
            market_cap=_as_float(profile.get("marketCapitalization")),
            website=str(profile.get("weburl")) if profile.get("weburl") else None,
            ipo=ipo,
            source=self.name,
        )

    async def get_ohlcv(self, ticker: str, timeframe: str) -> list[OHLCVBar]:
        resolution = _timeframe_to_resolution(timeframe)
        now, from_ts = _time_window(timeframe)
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

    async def get_candles(self, ticker: str, timeframe: str, limit: int = 60) -> list[OHLCVBar]:
        bars = await self.get_ohlcv(ticker, timeframe)
        return bars[-limit:] if limit > 0 else bars

    async def get_stock_news(self, ticker: str, limit: int = 10) -> StockNewsData | None:
        to_date = date.today().isoformat()
        from_date = date.fromordinal(date.today().toordinal() - 30).isoformat()
        payload = await self._http_client.get_json(
            f"{self._base_url}/company-news?symbol={ticker}&from={from_date}&to={to_date}&token={self._api_key}",
        )
        if not isinstance(payload, list):
            return None
        items: list[StockNewsItem] = []
        for entry in payload[: max(limit, 0)]:
            if not isinstance(entry, dict):
                continue
            published_at = None
            raw_datetime = entry.get("datetime")
            if raw_datetime:
                try:
                    published_at = datetime.fromtimestamp(int(raw_datetime), tz=UTC)
                except (TypeError, ValueError, OSError):
                    published_at = None
            items.append(
                StockNewsItem(
                    headline=str(entry.get("headline") or "Untitled"),
                    summary=str(entry.get("summary")) if entry.get("summary") else None,
                    source=str(entry.get("source")) if entry.get("source") else None,
                    url=str(entry.get("url")) if entry.get("url") else None,
                    published_at=published_at,
                ),
            )
        return StockNewsData(ticker=ticker, items=items, source=self.name)

    async def get_rsi(self, ticker: str, timeframe: str = "swing") -> RSIData | None:
        resolution = _timeframe_to_resolution(timeframe)
        now, from_ts = _time_window(timeframe)
        payload = await self._http_client.get_json(
            f"{self._base_url}/indicator?symbol={ticker}&resolution={resolution}&from={from_ts}&to={now}&indicator=rsi&timeperiod=14&token={self._api_key}",
        )
        if not isinstance(payload, dict) or payload.get("s") != "ok":
            return None
        values = payload.get("rsi", [])
        if not isinstance(values, list) or not values:
            return None
        return RSIData(ticker=ticker, value=_as_float(values[-1]), source=self.name)

    async def get_macd(self, ticker: str, timeframe: str = "swing") -> MACDData | None:
        resolution = _timeframe_to_resolution(timeframe)
        now, from_ts = _time_window(timeframe)
        payload = await self._http_client.get_json(
            f"{self._base_url}/indicator?symbol={ticker}&resolution={resolution}&from={from_ts}&to={now}&indicator=macd&token={self._api_key}",
        )
        if not isinstance(payload, dict) or payload.get("s") != "ok":
            return None
        macd_values = payload.get("macd", [])
        signal_values = payload.get("signal", [])
        histogram_values = payload.get("hist", [])
        if not isinstance(macd_values, list) or not macd_values:
            return None
        return MACDData(
            ticker=ticker,
            macd=_as_float(macd_values[-1]),
            signal=_as_float(signal_values[-1]) if isinstance(signal_values, list) and signal_values else None,
            histogram=_as_float(histogram_values[-1]) if isinstance(histogram_values, list) and histogram_values else None,
            source=self.name,
        )

    async def get_key_financials(self, ticker: str) -> KeyFinancialsData | None:
        profile = await self._http_client.get_json(
            f"{self._base_url}/stock/profile2?symbol={ticker}&token={self._api_key}",
        )
        metric_payload = await self._http_client.get_json(
            f"{self._base_url}/stock/metric?symbol={ticker}&metric=all&token={self._api_key}",
        )
        if not isinstance(metric_payload, dict):
            return None
        metrics = metric_payload.get("metric", {})
        if not isinstance(metrics, dict):
            metrics = {}
        market_cap = None
        if isinstance(profile, dict):
            market_cap = _as_float(profile.get("marketCapitalization"))
        return KeyFinancialsData(
            ticker=ticker,
            market_cap=market_cap,
            pe_ttm=_as_float(metrics.get("peTTM")),
            forward_pe=_as_float(metrics.get("forwardPE")),
            ps_ttm=_as_float(metrics.get("psTTM")),
            beta=_as_float(metrics.get("beta")),
            eps_ttm=_as_float(metrics.get("epsTTM")),
            dividend_yield=_as_float(metrics.get("dividendYieldIndicatedAnnual")),
            profit_margin=_as_float(metrics.get("netMarginTTM")),
            source=self.name,
        )

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


def _timeframe_to_resolution(timeframe: str) -> str:
    if timeframe == "intraday":
        return "60"
    return "D"


def _time_window(timeframe: str) -> tuple[int, int]:
    now = int(datetime.now(UTC).timestamp())
    if timeframe == "intraday":
        lookback_days = 30
    elif timeframe == "longterm":
        lookback_days = 365 * 3
    else:
        lookback_days = 365
    return now, now - (60 * 60 * 24 * lookback_days)


