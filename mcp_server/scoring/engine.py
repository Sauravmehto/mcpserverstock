"""Deterministic stock scoring engine."""

from __future__ import annotations

from mcp_server.config.settings import ScoringWeights
from mcp_server.schemas.models import MetricsTable, Scorecard


def _score_inverse(value: float | None, good_below: float, bad_above: float) -> float:
    if value is None:
        return 50.0
    if value <= good_below:
        return 100.0
    if value >= bad_above:
        return 0.0
    span = bad_above - good_below
    return max(0.0, 100.0 - ((value - good_below) / span) * 100)


def _score_direct(value: float | None, bad_below: float, good_above: float) -> float:
    if value is None:
        return 50.0
    if value <= bad_below:
        return 0.0
    if value >= good_above:
        return 100.0
    span = good_above - bad_below
    return min(100.0, ((value - bad_below) / span) * 100)


def score_value(metrics: MetricsTable) -> float:
    """Lower valuation multiples score higher."""

    pe_score = _score_inverse(metrics.pe, good_below=12, bad_above=45)
    ps_score = _score_inverse(metrics.ps, good_below=1.5, bad_above=15)
    ev_ebitda_score = _score_inverse(metrics.ev_ebitda, good_below=8, bad_above=40)
    return round((pe_score + ps_score + ev_ebitda_score) / 3, 2)


def score_growth(metrics: MetricsTable) -> float:
    """Higher growth metrics score higher."""

    revenue = _score_direct(metrics.revenue_yoy, bad_below=-5, good_above=30)
    eps = _score_direct(metrics.eps_yoy, bad_below=-10, good_above=35)
    forward = _score_direct(metrics.forward_eps_growth, bad_below=0, good_above=25)
    cagr = _score_direct(metrics.revenue_cagr_3y, bad_below=0, good_above=20)
    return round((revenue + eps + forward + cagr) / 4, 2)


def score_quality(metrics: MetricsTable) -> float:
    """Profitability and balance-sheet quality."""

    margin = _score_direct(metrics.net_margin, bad_below=0.05, good_above=0.25)
    roe = _score_direct(metrics.roe, bad_below=0.05, good_above=0.3)
    debt = _score_inverse(metrics.debt_equity, good_below=0.3, bad_above=2.0)
    return round((margin + roe + debt) / 3, 2)


def score_momentum(metrics: MetricsTable) -> float:
    """Momentum proxy from drawdown and volatility."""

    drawdown = _score_inverse(metrics.drawdown_risk, good_below=10, bad_above=60)
    vol = _score_inverse(metrics.volatility_proxy, good_below=1.5, bad_above=7.0)
    return round((drawdown + vol) / 2, 2)


def score_risk(metrics: MetricsTable) -> float:
    """Lower beta and drawdown score as lower risk."""

    beta = _score_inverse(metrics.beta, good_below=0.8, bad_above=2.0)
    drawdown = _score_inverse(metrics.drawdown_risk, good_below=10, bad_above=70)
    debt = _score_inverse(metrics.debt_equity, good_below=0.4, bad_above=2.5)
    return round((beta + drawdown + debt) / 3, 2)


def composite_score(
    metrics: MetricsTable,
    weights: ScoringWeights,
) -> Scorecard:
    """Build weighted composite scorecard."""

    value = score_value(metrics)
    growth = score_growth(metrics)
    quality = score_quality(metrics)
    momentum = score_momentum(metrics)
    risk = score_risk(metrics)
    weighted = (
        value * weights.value
        + growth * weights.growth
        + quality * weights.quality
        + momentum * weights.momentum
        + risk * weights.risk
    )
    return Scorecard(
        value=value,
        growth=growth,
        quality=quality,
        momentum=momentum,
        risk=risk,
        composite=round(weighted, 2),
    )


