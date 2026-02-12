"""Claude-driven analysis engine with strict JSON output requirements."""

from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import AsyncAnthropic
from pydantic import ValidationError

from mcp_server.schemas.models import AnalysisSections, MetricsTable, Scorecard

LOGGER = logging.getLogger(__name__)


class ClaudeAnalysisEngine:
    """Generate structured narrative sections from deterministic metrics."""

    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def build_sections(
        self,
        ticker: str,
        comparison_ticker: str | None,
        metrics: MetricsTable,
        scorecard: Scorecard,
    ) -> AnalysisSections:
        """Generate and validate analysis sections."""

        prompt = self._build_prompt(ticker, comparison_ticker, metrics, scorecard)
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=1800,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        text_parts = [block.text for block in response.content if getattr(block, "text", None)]
        joined = "\n".join(text_parts).strip()
        try:
            data = json.loads(joined)
            return AnalysisSections.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as error:
            LOGGER.warning("Claude JSON parse failed", extra={"error": str(error)})
            return AnalysisSections(
                executive_summary=f"Deterministic analysis for {ticker} generated without LLM narrative due to response format issue.",
                growth_analysis="Growth trends inferred from computed metrics only.",
                valuation_analysis="Valuation view inferred from scorecard and available multiples.",
                risk_assessment="Risk view inferred from beta, volatility proxy, and drawdown.",
                competitive_positioning=f"Peer comparison against {comparison_ticker or 'market baseline'} is limited by available normalized data.",
                final_investment_view="Use scorecard and signal output for decision support.",
                confidence=max(35.0, min(85.0, scorecard.composite)),
                key_drivers=["Composite score", "Growth metrics", "Risk profile alignment"],
                bear_case="Macro slowdown and earnings compression may weaken thesis.",
                bull_case="Execution upside and favorable valuation rerating may improve returns.",
                assumptions=["LLM output fallback path was used due to invalid JSON response."],
            )

    def _build_prompt(
        self,
        ticker: str,
        comparison_ticker: str | None,
        metrics: MetricsTable,
        scorecard: Scorecard,
    ) -> str:
        """Create strict JSON-only prompt."""

        return (
            "You are an institutional equity research analyst.\n"
            "Rules:\n"
            "1) Use ONLY the provided metrics and scorecard.\n"
            "2) Do not invent numbers or facts.\n"
            "3) If metric missing, explicitly mention data limitation.\n"
            "4) Return STRICT JSON only with keys:\n"
            "executive_summary,growth_analysis,valuation_analysis,risk_assessment,"
            "competitive_positioning,final_investment_view,confidence,key_drivers,bear_case,bull_case,assumptions\n\n"
            f"ticker={ticker}\n"
            f"comparison_ticker={comparison_ticker}\n"
            f"metrics={metrics.model_dump()}\n"
            f"scorecard={scorecard.model_dump()}\n"
        )


