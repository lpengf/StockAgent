"""Deterministic feature computation.

Ported 1-to-1 from the reference TypeScript implementation so replay results
match across languages. Uses numpy only for vectorised math — no randomness,
no time-based branching, no floating-point tricks beyond IEEE-754 defaults.
"""

from __future__ import annotations

import math

import numpy as np

from stock_agent.domain.types import DailyBar, SecurityFeatures, SecuritySeries

TRADING_DAYS_PER_YEAR = 252


def _mean(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    return float(values.mean())


def _std(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    avg = values.mean()
    return float(math.sqrt(((values - avg) ** 2).mean()))


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _round(value: float, digits: int = 2) -> float:
    factor = 10**digits
    return math.floor(value * factor + 0.5) / factor if value >= 0 else -math.floor(-value * factor + 0.5) / factor


def _total_return(closes: np.ndarray, days: int) -> float:
    if closes.size == 0:
        return 0.0
    start_index = max(0, closes.size - 1 - days)
    start = closes[start_index]
    if start == 0:
        return 0.0
    return float(closes[-1] / start - 1)


def _max_drawdown(closes: np.ndarray) -> float:
    if closes.size == 0:
        return 0.0
    peak = closes[0]
    drawdown = 0.0
    for close in closes:
        peak = max(peak, close)
        drawdown = min(drawdown, close / peak - 1)
    return float(drawdown)


def compute_features(security: SecuritySeries) -> SecurityFeatures:
    bars: tuple[DailyBar, ...] = security.bars
    if not bars:
        raise ValueError(f"security {security.security_id} has no bars")

    closes = np.array([bar.close for bar in bars], dtype=np.float64)
    volumes = np.array([bar.volume for bar in bars], dtype=np.float64)
    amounts = np.array([bar.amount for bar in bars], dtype=np.float64)
    returns = closes[1:] / closes[:-1] - 1

    amount_20 = _mean(amounts[-20:])
    return_5d = _total_return(closes, 5)
    return_20d = _total_return(closes, 20)
    recent_volume = _mean(volumes[-5:])
    base_volume = max(_mean(volumes[-20:-5]), 1.0)
    volume_ratio_5d = recent_volume / base_volume
    volatility_20d = _std(returns[-20:]) * math.sqrt(TRADING_DAYS_PER_YEAR)
    max_drawdown_20d = _max_drawdown(closes[-20:])

    trend_score = _clamp(50 + return_5d * 500 + return_20d * 250 + (volume_ratio_5d - 1) * 12)
    liquidity_score = _clamp(20 + math.log10(max(amount_20, 1.0)) * 9)
    fundamental_score = _clamp(
        50
        + security.roe * 90
        + security.revenue_growth * 55
        - max(0.0, security.debt_ratio - 0.65) * 80
    )
    risk_penalty = volatility_20d * 30 + abs(min(0.0, max_drawdown_20d)) * 80
    raw_score = _clamp(trend_score * 0.48 + liquidity_score * 0.2 + fundamental_score * 0.32 - risk_penalty)

    return SecurityFeatures(
        security_id=security.security_id,
        name=security.name,
        industry=security.industry,
        close=float(closes[-1]),
        return_5d=_round(return_5d * 100),
        return_20d=_round(return_20d * 100),
        volume_ratio_5d=_round(volume_ratio_5d),
        volatility_20d=_round(volatility_20d * 100),
        max_drawdown_20d=_round(max_drawdown_20d * 100),
        liquidity_score=_round(liquidity_score),
        fundamental_score=_round(fundamental_score),
        trend_score=_round(trend_score),
        raw_score=_round(raw_score),
    )
