"""Signal generation based on score and risk profile."""

from __future__ import annotations

from mcp_server.schemas.models import RiskProfile, Scorecard, SignalType


def generate_signal(scorecard: Scorecard, risk_profile: RiskProfile) -> tuple[SignalType, float]:
    """Map composite score to Buy/Hold/Sell according to risk profile."""

    threshold_buy = 70.0
    threshold_sell = 45.0
    if risk_profile == "aggressive":
        threshold_buy = 65.0
        threshold_sell = 40.0
    elif risk_profile == "conservative":
        threshold_buy = 75.0
        threshold_sell = 50.0

    score = scorecard.composite
    if score >= threshold_buy:
        return "Buy", min(100.0, round((score / 100) * 100, 2))
    if score <= threshold_sell:
        return "Sell", min(100.0, round(((100 - score) / 100) * 100, 2))
    return "Hold", round(60.0 + abs(score - ((threshold_buy + threshold_sell) / 2)) / 2, 2)


