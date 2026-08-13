"""Deterministic market-regime classification and industry ranking."""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from stock_agent.domain.features import _round
from stock_agent.domain.types import (
    IndustryChange,
    MarketInput,
    MarketRegime,
    MarketReview,
    SecurityFeatures,
)


def _classify_regime(index_change: float, advance_ratio: float) -> MarketRegime:
    if index_change > 1.2 and advance_ratio >= 0.58:
        return "TREND_UP"
    if index_change < -1.0 or advance_ratio < 0.35:
        return "RISK_OFF"
    return "RANGE"


def build_market_review(
    input_data: MarketInput,
    features: tuple[SecurityFeatures, ...],
) -> MarketReview:
    if not features:
        raise ValueError("cannot build market review without any features")

    positive = sum(1 for feature in features if feature.return_5d > 0)
    advance_ratio = positive / len(features)
    index_change = float(np.mean([feature.return_5d for feature in features]))

    current_amount = float(sum(security.bars[-1].amount for security in input_data.securities))
    previous_amount = float(sum(security.bars[-2].amount for security in input_data.securities))
    if previous_amount == 0:
        raise ValueError("previous-day amount is zero; cannot compute volume change")
    volume_change = current_amount / previous_amount - 1

    regime = _classify_regime(index_change, advance_ratio)

    industry_returns: dict[str, list[float]] = defaultdict(list)
    for feature in features:
        industry_returns[feature.industry].append(feature.return_5d)

    leading = sorted(
        (IndustryChange(name=name, change=_round(float(np.mean(values)))) for name, values in industry_returns.items()),
        key=lambda item: item.change,
        reverse=True,
    )[:3]

    regime_label = {"TREND_UP": "趋势上行", "RISK_OFF": "风险收缩", "RANGE": "区间震荡"}[regime]
    summary = (
        f"市场处于{regime_label}状态，近 5 日样本平均涨跌幅 {_round(index_change)}%，"
        f"上涨占比 {_round(advance_ratio * 100)}%。"
    )
    return MarketReview(
        regime=regime,
        index_change=_round(index_change),
        advance_ratio=_round(advance_ratio * 100),
        total_amount=round(current_amount),
        volume_change=_round(volume_change * 100),
        leading_industries=tuple(leading),
        summary=summary,
    )
