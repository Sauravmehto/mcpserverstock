"""Tests for technical indicator calculations."""

from __future__ import annotations

from datetime import date, timedelta

from mcp_server.indicators.technical import calculate_ema, calculate_macd, calculate_rsi, compute_technicals_from_bars
from mcp_server.schemas.models import OHLCVBar


def _sample_bars(count: int = 260) -> list[OHLCVBar]:
    start = date(2024, 1, 1)
    bars: list[OHLCVBar] = []
    for index in range(count):
        close = 100 + index * 0.4
        bars.append(
            OHLCVBar(
                date=start + timedelta(days=index),
                open=close - 1,
                high=close + 1,
                low=close - 2,
                close=close,
                volume=1000 + (index * 10),
            ),
        )
    return bars


def test_ema_returns_value_when_enough_points() -> None:
    values = [float(i) for i in range(1, 30)]
    ema = calculate_ema(values, 20)
    assert ema is not None


def test_rsi_in_uptrend_is_high() -> None:
    values = [float(i) for i in range(1, 40)]
    rsi = calculate_rsi(values, 14)
    assert rsi is not None
    assert rsi > 60


def test_macd_returns_tuple() -> None:
    values = [100 + (i * 0.2) for i in range(60)]
    macd, signal = calculate_macd(values)
    assert macd is not None
    assert signal is not None


def test_compute_technicals_from_bars() -> None:
    bars = _sample_bars()
    result = compute_technicals_from_bars(bars, source="computed")
    assert result.ema_20 is not None
    assert result.ema_50 is not None
    assert result.ema_200 is not None


