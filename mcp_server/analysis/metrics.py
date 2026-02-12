"""Financial metrics computations used by reports and scoring."""

from __future__ import annotations

from math import pow

from mcp_server.schemas.models import FundamentalsData, MetricsTable, OHLCVBar


def safe_cagr(values: list[float], years: int) -> float | None:
    """Calculate CAGR based on historical values."""

    if len(values) < years + 1:
        return None
    start = values[-(years + 1)]
    end = values[-1]
    if start <= 0:
        return None
    return (pow(end / start, 1 / years) - 1) * 100


def margin_trend(gross_margin: float | None, operating_margin: float | None, net_margin: float | None) -> float | None:
    """Simple trend proxy from profitability stack."""

    margins = [value for value in [gross_margin, operating_margin, net_margin] if value is not None]
    if not margins:
        return None
    return sum(margins) / len(margins)


def volatility_proxy(bars: list[OHLCVBar]) -> float | None:
    """Compute average absolute daily return percentage."""

    if len(bars) < 2:
        return None
    closes = [bar.close for bar in sorted(bars, key=lambda item: item.date)]
    returns: list[float] = []
    for idx in range(1, len(closes)):
        previous = closes[idx - 1]
        if previous == 0:
            continue
        returns.append(abs((closes[idx] - previous) / previous) * 100)
    if not returns:
        return None
    return sum(returns) / len(returns)


def drawdown_risk(bars: list[OHLCVBar]) -> float | None:
    """Compute max drawdown percentage over the provided bar set."""

    if not bars:
        return None
    closes = [bar.close for bar in sorted(bars, key=lambda item: item.date)]
    peak = closes[0]
    max_drawdown = 0.0
    for close in closes:
        if close > peak:
            peak = close
        if peak > 0:
            drawdown = ((peak - close) / peak) * 100
            max_drawdown = max(max_drawdown, drawdown)
    return max_drawdown


def compute_metrics(fundamentals: FundamentalsData | None, bars: list[OHLCVBar]) -> MetricsTable:
    """Build normalized metric table from available data."""

    if fundamentals is None:
        return MetricsTable(
            volatility_proxy=volatility_proxy(bars),
            drawdown_risk=drawdown_risk(bars),
        )

    return MetricsTable(
        revenue_yoy=fundamentals.revenue_yoy,
        revenue_cagr_3y=safe_cagr(fundamentals.revenue_history, 3),
        revenue_cagr_5y=safe_cagr(fundamentals.revenue_history, 5),
        eps_yoy=fundamentals.eps_yoy,
        forward_eps_growth=fundamentals.forward_eps_growth,
        margin_trend=margin_trend(
            fundamentals.gross_margin,
            fundamentals.operating_margin,
            fundamentals.net_margin,
        ),
        gross_margin=fundamentals.gross_margin,
        operating_margin=fundamentals.operating_margin,
        net_margin=fundamentals.net_margin,
        roe=fundamentals.roe,
        roic=fundamentals.roe,
        debt_equity=fundamentals.debt_to_equity,
        pe=fundamentals.pe,
        forward_pe=fundamentals.forward_pe,
        ps=fundamentals.ps,
        ev_ebitda=fundamentals.ev_ebitda,
        beta=fundamentals.beta,
        volatility_proxy=volatility_proxy(bars),
        drawdown_risk=drawdown_risk(bars),
    )


