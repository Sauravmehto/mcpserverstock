"""Tests for scoring engine."""

from __future__ import annotations

from mcp_server.config.settings import ScoringWeights
from mcp_server.scoring.engine import composite_score, score_growth, score_quality, score_risk, score_value
from mcp_server.schemas.models import MetricsTable


def _metrics() -> MetricsTable:
    return MetricsTable(
        revenue_yoy=0.2,
        revenue_cagr_3y=0.15,
        eps_yoy=0.18,
        forward_eps_growth=0.12,
        gross_margin=0.5,
        operating_margin=0.3,
        net_margin=0.25,
        roe=0.28,
        debt_equity=0.7,
        pe=20.0,
        forward_pe=18.0,
        ps=5.0,
        ev_ebitda=14.0,
        beta=1.0,
        volatility_proxy=2.2,
        drawdown_risk=22.0,
    )


def test_individual_scores_in_range() -> None:
    metrics = _metrics()
    for value in [
        score_value(metrics),
        score_growth(metrics),
        score_quality(metrics),
        score_risk(metrics),
    ]:
        assert 0 <= value <= 100


def test_composite_score() -> None:
    metrics = _metrics()
    weights = ScoringWeights()
    scorecard = composite_score(metrics, weights)
    assert 0 <= scorecard.composite <= 100


