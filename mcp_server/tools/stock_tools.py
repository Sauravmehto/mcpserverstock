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
from mcp_server.providers.router import ProviderRouter
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


