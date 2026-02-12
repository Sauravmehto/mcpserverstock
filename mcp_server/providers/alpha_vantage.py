"""Alpha Vantage provider implementation."""

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


class AlphaVantageProvider(BaseDataProvider):
    """Fetch market data from Alpha Vantage APIs."""

    name = "alpha_vantage"
    _base_url = "https://www.alphavantage.co/query"

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
        params = f"function=GLOBAL_QUOTE&symbol={ticker}&apikey={self._api_key}"
        payload = await self._http_client.get_json(f"{self._base_url}?{params}")
        quote = payload.get("Global Quote", {}) if isinstance(payload, dict) else {}
        raw_price = quote.get("05. price")
        if not raw_price:
            return None
        return QuoteData(
            ticker=ticker,
            price=float(raw_price),
            change=_as_float(quote.get("09. change")),
            change_percent=_as_float(str(quote.get("10. change percent", "")).replace("%", "")),
            high=_as_float(quote.get("03. high")),
            low=_as_float(quote.get("04. low")),
            open=_as_float(quote.get("02. open")),
            previous_close=_as_float(quote.get("08. previous close")),
            timestamp=datetime.now(UTC),
            source=self.name,
        )

    async def get_company_profile(self, ticker: str) -> CompanyProfileData | None:
        params = f"function=OVERVIEW&symbol={ticker}&apikey={self._api_key}"
        payload = await self._http_client.get_json(f"{self._base_url}?{params}")
        if not isinstance(payload, dict) or not payload:
            return None
        ipo = None
        raw_ipo = payload.get("IPODate")
        if raw_ipo:
            try:
                ipo = date.fromisoformat(str(raw_ipo))
            except ValueError:
                ipo = None
        return CompanyProfileData(
            ticker=ticker,
            name=str(payload.get("Name")) if payload.get("Name") else None,
            exchange=str(payload.get("Exchange")) if payload.get("Exchange") else None,
            industry=str(payload.get("Industry")) if payload.get("Industry") else None,
            sector=str(payload.get("Sector")) if payload.get("Sector") else None,
            country=str(payload.get("Country")) if payload.get("Country") else None,
            market_cap=_as_float(payload.get("MarketCapitalization")),
            website=str(payload.get("OfficialSite")) if payload.get("OfficialSite") else None,
            ipo=ipo,
            source=self.name,
        )

    async def get_ohlcv(self, ticker: str, timeframe: str) -> list[OHLCVBar]:
        function = "TIME_SERIES_DAILY"
        if timeframe == "intraday":
            function = "TIME_SERIES_INTRADAY"
        params = f"function={function}&symbol={ticker}&outputsize=compact&apikey={self._api_key}"
        if timeframe == "intraday":
            params += "&interval=60min"
        payload = await self._http_client.get_json(f"{self._base_url}?{params}")
        if not isinstance(payload, dict):
            return []
        series_key = next((key for key in payload.keys() if "Time Series" in key), None)
        if not series_key:
            return []
        points = payload.get(series_key, {})
        if not isinstance(points, dict):
            return []
        bars: list[OHLCVBar] = []
        for stamp, row in points.items():
            if not isinstance(row, dict):
                continue
            try:
                bars.append(
                    OHLCVBar(
                        date=date.fromisoformat(stamp[:10]),
                        open=float(row.get("1. open")),
                        high=float(row.get("2. high")),
                        low=float(row.get("3. low")),
                        close=float(row.get("4. close")),
                        volume=float(row.get("5. volume", 0)),
                    ),
                )
            except (TypeError, ValueError):
                continue
        bars.sort(key=lambda bar: bar.date)
        return bars

    async def get_candles(self, ticker: str, timeframe: str, limit: int = 60) -> list[OHLCVBar]:
        bars = await self.get_ohlcv(ticker, timeframe)
        return bars[-limit:] if limit > 0 else bars

    async def get_stock_news(self, ticker: str, limit: int = 10) -> StockNewsData | None:
        params = f"function=NEWS_SENTIMENT&tickers={ticker}&apikey={self._api_key}"
        payload = await self._http_client.get_json(f"{self._base_url}?{params}")
        if not isinstance(payload, dict):
            return None
        feed = payload.get("feed", [])
        if not isinstance(feed, list):
            return None
        items: list[StockNewsItem] = []
        for entry in feed[: max(limit, 0)]:
            if not isinstance(entry, dict):
                continue
            published_at = None
            raw_time = entry.get("time_published")
            if raw_time:
                try:
                    published_at = datetime.strptime(str(raw_time), "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
                except ValueError:
                    published_at = None
            items.append(
                StockNewsItem(
                    headline=str(entry.get("title") or "Untitled"),
                    summary=str(entry.get("summary")) if entry.get("summary") else None,
                    source=str(entry.get("source")) if entry.get("source") else None,
                    url=str(entry.get("url")) if entry.get("url") else None,
                    published_at=published_at,
                ),
            )
        return StockNewsData(ticker=ticker, items=items, source=self.name)

    async def get_rsi(self, ticker: str, timeframe: str = "swing") -> RSIData | None:
        interval = _timeframe_to_interval(timeframe)
        params = (
            f"function=RSI&symbol={ticker}&interval={interval}&time_period=14&series_type=close&apikey={self._api_key}"
        )
        payload = await self._http_client.get_json(f"{self._base_url}?{params}")
        if not isinstance(payload, dict):
            return None
        series_key = next((key for key in payload.keys() if "Technical Analysis: RSI" in key), None)
        if not series_key:
            return None
        points = payload.get(series_key, {})
        if not isinstance(points, dict) or not points:
            return None
        latest_key = sorted(points.keys())[-1]
        latest_row = points.get(latest_key, {})
        if not isinstance(latest_row, dict):
            return None
        return RSIData(ticker=ticker, value=_as_float(latest_row.get("RSI")), source=self.name)

    async def get_macd(self, ticker: str, timeframe: str = "swing") -> MACDData | None:
        interval = _timeframe_to_interval(timeframe)
        params = f"function=MACD&symbol={ticker}&interval={interval}&series_type=close&apikey={self._api_key}"
        payload = await self._http_client.get_json(f"{self._base_url}?{params}")
        if not isinstance(payload, dict):
            return None
        series_key = next((key for key in payload.keys() if "Technical Analysis: MACD" in key), None)
        if not series_key:
            return None
        points = payload.get(series_key, {})
        if not isinstance(points, dict) or not points:
            return None
        latest_key = sorted(points.keys())[-1]
        latest_row = points.get(latest_key, {})
        if not isinstance(latest_row, dict):
            return None
        return MACDData(
            ticker=ticker,
            macd=_as_float(latest_row.get("MACD")),
            signal=_as_float(latest_row.get("MACD_Signal")),
            histogram=_as_float(latest_row.get("MACD_Hist")),
            source=self.name,
        )

    async def get_key_financials(self, ticker: str) -> KeyFinancialsData | None:
        params = f"function=OVERVIEW&symbol={ticker}&apikey={self._api_key}"
        payload = await self._http_client.get_json(f"{self._base_url}?{params}")
        if not isinstance(payload, dict) or not payload:
            return None
        return KeyFinancialsData(
            ticker=ticker,
            market_cap=_as_float(payload.get("MarketCapitalization")),
            pe_ttm=_as_float(payload.get("PERatio")),
            forward_pe=_as_float(payload.get("ForwardPE")),
            ps_ttm=_as_float(payload.get("PriceToSalesRatioTTM")),
            beta=_as_float(payload.get("Beta")),
            eps_ttm=_as_float(payload.get("EPS")) or _as_float(payload.get("DilutedEPSTTM")),
            dividend_yield=_as_float(payload.get("DividendYield")),
            profit_margin=_as_float(payload.get("ProfitMargin")),
            source=self.name,
        )

    async def get_technicals(self, ticker: str, timeframe: str) -> dict[str, float | None]:
        # Indicator values are calculated internally from OHLCV.
        _ = timeframe
        return {"rsi": None, "macd": None, "ema_20": None, "ema_50": None, "ema_200": None}

    async def get_fundamentals(self, ticker: str) -> FundamentalsData | None:
        params = f"function=OVERVIEW&symbol={ticker}&apikey={self._api_key}"
        payload = await self._http_client.get_json(f"{self._base_url}?{params}")
        if not isinstance(payload, dict) or not payload:
            return None
        rev_hist = await self._extract_revenue_history(ticker)
        return FundamentalsData(
            ticker=ticker,
            pe=_as_float(payload.get("PERatio")),
            forward_pe=_as_float(payload.get("ForwardPE")),
            ps=_as_float(payload.get("PriceToSalesRatioTTM")),
            ev_ebitda=_as_float(payload.get("EVToEBITDA")),
            beta=_as_float(payload.get("Beta")),
            roe=_as_float(payload.get("ReturnOnEquityTTM")),
            debt_to_equity=_as_float(payload.get("DebtToEquity")),
            gross_margin=_as_float(payload.get("GrossProfitTTM")),
            operating_margin=_as_float(payload.get("OperatingMarginTTM")),
            net_margin=_as_float(payload.get("ProfitMargin")),
            revenue_yoy=_as_float(payload.get("QuarterlyRevenueGrowthYOY")),
            eps_yoy=_as_float(payload.get("QuarterlyEarningsGrowthYOY")),
            forward_eps_growth=_as_float(payload.get("EPS")) or _as_float(payload.get("DilutedEPSTTM")),
            revenue_history=rev_hist,
            source=self.name,
        )

    async def _extract_revenue_history(self, ticker: str) -> list[float]:
        params = f"function=INCOME_STATEMENT&symbol={ticker}&apikey={self._api_key}"
        payload = await self._http_client.get_json(f"{self._base_url}?{params}")
        if not isinstance(payload, dict):
            return []
        reports = payload.get("annualReports", [])
        if not isinstance(reports, list):
            return []
        revenues: list[float] = []
        for report in reports[:6]:
            if not isinstance(report, dict):
                continue
            value = _as_float(report.get("totalRevenue"))
            if value is not None:
                revenues.append(value)
        return list(reversed(revenues))

    async def get_news_sentiment(self, ticker: str) -> NewsSentimentData | None:
        params = f"function=NEWS_SENTIMENT&tickers={ticker}&apikey={self._api_key}"
        payload = await self._http_client.get_json(f"{self._base_url}?{params}")
        if not isinstance(payload, dict):
            return None
        feed = payload.get("feed", [])
        if not isinstance(feed, list):
            return None
        sentiments: list[float] = []
        for item in feed:
            if not isinstance(item, dict):
                continue
            score = _as_float(item.get("overall_sentiment_score"))
            if score is not None:
                sentiments.append(score)
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


def _timeframe_to_interval(timeframe: str) -> str:
    if timeframe == "intraday":
        return "60min"
    if timeframe == "longterm":
        return "weekly"
    return "daily"


