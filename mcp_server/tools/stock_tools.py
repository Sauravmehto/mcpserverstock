"""MCP tool registration and orchestration for stock analysis."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from mcp_server.analysis.claude_engine import ClaudeAnalysisEngine
from mcp_server.analysis.metrics import compute_metrics
from mcp_server.analysis.signal_engine import generate_signal
from mcp_server.config.settings import Settings
from mcp_server.indicators.technical import compute_technicals_from_bars
from mcp_server.providers.router import ProviderRouter, RoutedData
from mcp_server.schemas.models import ResearchRequest, StockResearchResult
from mcp_server.scoring.engine import composite_score


def register_stock_tools(
    mcp: FastMCP,
    router: ProviderRouter,
    claude_engine: ClaudeAnalysisEngine,
    settings: Settings,
) -> None:
    """Register all required stock tools."""

    @mcp.tool(name="get_price")
    async def get_price(ticker: str) -> str:
        data = await router.get_price(ticker.upper())
        return json.dumps((data.model_dump(mode="json") if data else {"ticker": ticker, "price": None}), default=str)

    @mcp.tool(name="get_ohlcv")
    async def get_ohlcv(ticker: str, timeframe: str = "swing") -> str:
        bars = await router.get_ohlcv(ticker.upper(), timeframe)
        return json.dumps([bar.model_dump(mode="json") for bar in bars], default=str)

    @mcp.tool(name="get_technicals")
    async def get_technicals(ticker: str, timeframe: str = "swing") -> str:
        bars = await router.get_ohlcv(ticker.upper(), timeframe)
        technicals = compute_technicals_from_bars(bars, source="computed")
        return json.dumps(technicals.model_dump(mode="json"), default=str)

    @mcp.tool(name="get_fundamentals")
    async def get_fundamentals(ticker: str) -> str:
        fundamentals = await router.get_fundamentals(ticker.upper())
        return json.dumps(
            fundamentals.model_dump(mode="json") if fundamentals else {"ticker": ticker, "error": "fundamentals_unavailable"},
            default=str,
        )

    @mcp.tool(name="get_news_sentiment")
    async def get_news_sentiment(ticker: str) -> str:
        sentiment = await router.get_news_sentiment(ticker.upper())
        return json.dumps(
            sentiment.model_dump(mode="json") if sentiment else {"ticker": ticker, "error": "sentiment_unavailable"},
            default=str,
        )

    @mcp.tool(name="get_stock_price")
    async def get_stock_price(ticker: str) -> str:
        routed = await router.get_price_routed(ticker.upper())
        if not routed.data:
            return _format_missing("get_stock_price", ticker, routed.fallback_warning)
        return _format_success(
            (
                f"{routed.data.ticker}: ${routed.data.price:.2f}"
                if routed.data.price is not None
                else f"{routed.data.ticker}: price unavailable"
            ),
            routed,
        )

    @mcp.tool(name="get_quote")
    async def get_quote(ticker: str) -> str:
        routed = await router.get_quote_routed(ticker.upper())
        if not routed.data:
            return _format_missing("get_quote", ticker, routed.fallback_warning)
        quote = routed.data
        change_text = "n/a"
        if quote.change is not None and quote.change_percent is not None:
            sign = "+" if quote.change >= 0 else ""
            change_text = f"{sign}{quote.change:.2f} ({sign}{quote.change_percent:.2f}%)"
        return _format_success(
            (
                f"{quote.ticker} quote: price=${quote.price:.2f} "
                f"change={change_text} high={_fmt_num(quote.high)} low={_fmt_num(quote.low)} "
                f"open={_fmt_num(quote.open)} prev_close={_fmt_num(quote.previous_close)}"
            ),
            routed,
        )

    @mcp.tool(name="get_company_profile")
    async def get_company_profile(ticker: str) -> str:
        routed = await router.get_company_profile_routed(ticker.upper())
        if not routed.data:
            return _format_missing("get_company_profile", ticker, routed.fallback_warning)
        profile = routed.data
        return _format_success(
            (
                f"{profile.ticker} profile: name={profile.name or 'n/a'} exchange={profile.exchange or 'n/a'} "
                f"industry={profile.industry or 'n/a'} sector={profile.sector or 'n/a'} "
                f"country={profile.country or 'n/a'} market_cap={_fmt_num(profile.market_cap)} "
                f"website={profile.website or 'n/a'}"
            ),
            routed,
        )

    @mcp.tool(name="get_candles")
    async def get_candles(ticker: str, timeframe: str = "swing", limit: int = 20) -> str:
        routed = await router.get_candles_routed(ticker.upper(), timeframe, limit)
        candles = routed.data or []
        if not candles:
            return _format_missing("get_candles", ticker, routed.fallback_warning)
        latest = candles[-1]
        return _format_success(
            (
                f"{ticker.upper()} candles ({timeframe}, count={len(candles)}): "
                f"latest={latest.date.isoformat()} O={latest.open:.2f} H={latest.high:.2f} "
                f"L={latest.low:.2f} C={latest.close:.2f} V={latest.volume:.0f}"
            ),
            routed,
        )

    @mcp.tool(name="get_stock_news")
    async def get_stock_news(ticker: str, limit: int = 5) -> str:
        routed = await router.get_stock_news_routed(ticker.upper(), limit)
        if not routed.data or not routed.data.items:
            return _format_missing("get_stock_news", ticker, routed.fallback_warning)
        headlines = "; ".join(item.headline for item in routed.data.items[:limit])
        return _format_success(
            f"{ticker.upper()} news ({len(routed.data.items)} items): {headlines}",
            routed,
        )

    @mcp.tool(name="get_rsi")
    async def get_rsi(ticker: str, timeframe: str = "swing") -> str:
        routed = await router.get_rsi_routed(ticker.upper(), timeframe)
        if not routed.data or routed.data.value is None:
            return _format_missing("get_rsi", ticker, routed.fallback_warning)
        state = "neutral"
        if routed.data.value >= 70:
            state = "overbought"
        elif routed.data.value <= 30:
            state = "oversold"
        return _format_success(
            f"{ticker.upper()} RSI ({timeframe}): {routed.data.value:.2f} ({state})",
            routed,
        )

    @mcp.tool(name="get_macd")
    async def get_macd(ticker: str, timeframe: str = "swing") -> str:
        routed = await router.get_macd_routed(ticker.upper(), timeframe)
        if not routed.data or routed.data.macd is None:
            return _format_missing("get_macd", ticker, routed.fallback_warning)
        macd = routed.data
        return _format_success(
            (
                f"{ticker.upper()} MACD ({timeframe}): macd={macd.macd:.4f} "
                f"signal={_fmt_num(macd.signal, digits=4)} hist={_fmt_num(macd.histogram, digits=4)}"
            ),
            routed,
        )

    @mcp.tool(name="get_key_financials")
    async def get_key_financials(ticker: str) -> str:
        routed = await router.get_key_financials_routed(ticker.upper())
        if not routed.data:
            return _format_missing("get_key_financials", ticker, routed.fallback_warning)
        fin = routed.data
        return _format_success(
            (
                f"{ticker.upper()} key financials: market_cap={_fmt_num(fin.market_cap)} "
                f"pe_ttm={_fmt_num(fin.pe_ttm)} forward_pe={_fmt_num(fin.forward_pe)} "
                f"ps_ttm={_fmt_num(fin.ps_ttm)} beta={_fmt_num(fin.beta)} "
                f"eps_ttm={_fmt_num(fin.eps_ttm)} dividend_yield={_fmt_num(fin.dividend_yield)} "
                f"profit_margin={_fmt_num(fin.profit_margin)}"
            ),
            routed,
        )

    @mcp.tool(name="analyze_stock")
    async def analyze_stock(
        ticker: str,
        timeframe: str = "swing",
        risk_profile: str = "moderate",
        output_format: str = "signal",
    ) -> str:
        request = ResearchRequest(
            ticker=ticker,
            timeframe=timeframe,  # type: ignore[arg-type]
            risk_profile=risk_profile,  # type: ignore[arg-type]
            output_format=output_format,  # type: ignore[arg-type]
        )
        result = await _run_full_analysis(request, router, claude_engine, settings)
        if request.output_format == "signal":
            payload = {
                "ticker": request.ticker,
                "signal": result.signal_if_requested,
                "confidence": result.confidence,
                "disclaimer": result.disclaimer,
            }
            return json.dumps(payload, default=str)
        return result.model_dump_json()

    @mcp.tool(name="stock_research_report")
    async def stock_research_report(
        ticker: str,
        comparison_ticker: str | None = None,
        timeframe: str = "swing",
        risk_profile: str = "moderate",
        output_format: str = "report",
    ) -> str:
        try:
            request = ResearchRequest(
                ticker=ticker,
                comparison_ticker=comparison_ticker,
                timeframe=timeframe,  # type: ignore[arg-type]
                risk_profile=risk_profile,  # type: ignore[arg-type]
                output_format=output_format,  # type: ignore[arg-type]
            )
        except ValidationError as error:
            return json.dumps(
                {
                    "error": {
                        "code": "validation_error",
                        "message": "Invalid request payload",
                        "details": error.errors(),
                    },
                },
            )
        result = await _run_full_analysis(request, router, claude_engine, settings)
        return result.model_dump_json()


async def _run_full_analysis(
    request: ResearchRequest,
    router: ProviderRouter,
    claude_engine: ClaudeAnalysisEngine,
    settings: Settings,
) -> StockResearchResult:
    bars = await router.get_ohlcv(request.ticker, request.timeframe)
    fundamentals = await router.get_fundamentals(request.ticker)
    metrics = compute_metrics(fundamentals, bars)
    scorecard = composite_score(metrics, settings.scoring_weights)
    signal, confidence = generate_signal(scorecard, request.risk_profile)

    peer_comparison_text = "No comparison ticker provided."
    if request.comparison_ticker:
        peer_fundamentals = await router.get_fundamentals(request.comparison_ticker)
        if peer_fundamentals and peer_fundamentals.pe and fundamentals and fundamentals.pe:
            peer_comparison_text = (
                f"{request.ticker} PE={fundamentals.pe} vs {request.comparison_ticker} PE={peer_fundamentals.pe}."
            )
        else:
            peer_comparison_text = "Comparison requested but not enough normalized peer data."

    sections = await claude_engine.build_sections(
        ticker=request.ticker,
        comparison_ticker=request.comparison_ticker,
        metrics=metrics,
        scorecard=scorecard,
    )

    signal_if_requested = signal if request.output_format == "signal" else None
    final_confidence = confidence if request.output_format == "signal" else sections.confidence

    return StockResearchResult(
        executive_summary=sections.executive_summary,
        metrics_table=metrics,
        scorecard=scorecard,
        growth_analysis=sections.growth_analysis,
        valuation_analysis=sections.valuation_analysis,
        risk_assessment=sections.risk_assessment,
        peer_comparison=peer_comparison_text,
        final_investment_view=sections.final_investment_view,
        confidence=final_confidence,
        assumptions=sections.assumptions,
        signal_if_requested=signal_if_requested,
    )


def _format_success(text: str, routed: RoutedData[Any]) -> str:
    warning = f"\nwarning: {routed.fallback_warning}" if routed.fallback_warning else ""
    source = f"\nsource: {routed.source}" if routed.source else ""
    return f"{text}{source}{warning}"


def _format_missing(tool_name: str, ticker: str, warning: str | None) -> str:
    details = warning or "No provider returned data."
    return f"{tool_name} unavailable for {ticker.upper()}. {details}"


def _fmt_num(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


