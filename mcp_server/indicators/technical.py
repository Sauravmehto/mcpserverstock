"""Technical indicator calculations."""

from __future__ import annotations

from mcp_server.schemas.models import OHLCVBar, TechnicalsData


def calculate_ema(values: list[float], period: int) -> float | None:
    """Calculate exponential moving average for the given period."""

    if len(values) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for value in values[period:]:
        ema = (value - ema) * multiplier + ema
    return ema


def calculate_rsi(values: list[float], period: int = 14) -> float | None:
    """Calculate RSI using the smoothed average gains/losses method."""

    if len(values) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for idx in range(1, len(values)):
        delta = values[idx] - values[idx - 1]
        gains.append(max(delta, 0.0))
        losses.append(abs(min(delta, 0.0)))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for idx in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + gains[idx]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[idx]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_macd(values: list[float]) -> tuple[float | None, float | None]:
    """Calculate MACD and MACD signal."""

    if len(values) < 35:
        return None, None
    macd_series: list[float] = []
    for idx in range(len(values)):
        prefix = values[: idx + 1]
        ema12 = calculate_ema(prefix, 12)
        ema26 = calculate_ema(prefix, 26)
        if ema12 is None or ema26 is None:
            continue
        macd_series.append(ema12 - ema26)
    if not macd_series:
        return None, None
    macd_value = macd_series[-1]
    signal = calculate_ema(macd_series, 9)
    return macd_value, signal


def compute_technicals_from_bars(bars: list[OHLCVBar], source: str) -> TechnicalsData:
    """Build technical indicator snapshot from OHLCV bars."""

    closes = [bar.close for bar in sorted(bars, key=lambda item: item.date)]
    ema20 = calculate_ema(closes, 20)
    ema50 = calculate_ema(closes, 50)
    ema200 = calculate_ema(closes, 200)
    rsi = calculate_rsi(closes, 14)
    macd, macd_signal = calculate_macd(closes)
    return TechnicalsData(
        rsi=rsi,
        macd=macd,
        macd_signal=macd_signal,
        ema_20=ema20,
        ema_50=ema50,
        ema_200=ema200,
        source=source,
    )


