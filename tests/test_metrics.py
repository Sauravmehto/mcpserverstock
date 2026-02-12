"""Tests for metrics engine."""

from __future__ import annotations

from datetime import date, timedelta

from mcp_server.analysis.metrics import compute_metrics, drawdown_risk, safe_cagr, volatility_proxy
from mcp_server.schemas.models import FundamentalsData, OHLCVBar


def _bars() -> list[OHLCVBar]:
    start = date(2024, 1, 1)
    prices = [100, 102, 99, 105, 103, 108, 107]
    data: list[OHLCVBar] = []
    for idx, price in enumerate(prices):
        data.append(
            OHLCVBar(
                date=start + timedelta(days=idx),
                open=price - 1,
                high=price + 1,
                low=price - 2,
                close=price,
                volume=1000 + idx,
            ),
        )
    return data


def test_safe_cagr() -> None:
    cagr = safe_cagr([100, 120, 140, 170], 3)
    assert cagr is not None
    assert cagr > 0


def test_risk_proxies() -> None:
    bars = _bars()
    assert volatility_proxy(bars) is not None
    dd = drawdown_risk(bars)
    assert dd is not None
    assert dd >= 0


def test_compute_metrics_populates_fields() -> None:
    bars = _bars()
    fundamentals = FundamentalsData(
        ticker="AAPL",
        pe=28.0,
        forward_pe=25.0,
        ps=7.0,
        ev_ebitda=18.0,
        beta=1.1,
        roe=0.3,
        debt_to_equity=1.2,
        gross_margin=0.45,
        operating_margin=0.28,
        net_margin=0.23,
        revenue_yoy=0.12,
        eps_yoy=0.15,
        forward_eps_growth=0.11,
        revenue_history=[200.0, 215.0, 235.0, 260.0, 280.0, 300.0],
        source="test",
    )
    metrics = compute_metrics(fundamentals, bars)
    assert metrics.pe == 28.0
    assert metrics.revenue_cagr_3y is not None


