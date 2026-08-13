"""Regime-aware candidate selection with industry diversification.

Deterministic given the same input tuple + regime + configuration.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from stock_agent.domain.features import _clamp, _round
from stock_agent.domain.risk import evaluate_risk
from stock_agent.domain.types import (
    Candidate,
    MarketInput,
    MarketRegime,
    RiskDecision,
    SecurityFeatures,
    SecuritySeries,
)

REGIME_THRESHOLDS: dict[MarketRegime, float] = {
    "TREND_UP": 52.0,
    "RANGE": 56.0,
    "RISK_OFF": 64.0,
}


@dataclass(frozen=True, slots=True)
class SelectionConfig:
    max_focus: int = 5
    max_total: int = 10
    max_per_industry: int = 2


@dataclass(frozen=True, slots=True)
class SelectionResult:
    candidates: tuple[Candidate, ...]
    rejected_count: int


def _confidence(raw_score: float, threshold: float) -> float:
    return _round(_clamp(0.55 + (raw_score - threshold) / 100, 0.5, 0.88), digits=2)


def select_candidates(
    input_data: MarketInput,
    features: tuple[SecurityFeatures, ...],
    regime: MarketRegime,
    config: SelectionConfig | None = None,
) -> SelectionResult:
    cfg = config or SelectionConfig()
    threshold = REGIME_THRESHOLDS[regime]

    by_id: dict[str, SecuritySeries] = {security.security_id: security for security in input_data.securities}
    ranked = sorted(
        (
            (feature, by_id[feature.security_id], evaluate_risk(by_id[feature.security_id], feature))
            for feature in features
        ),
        key=lambda item: item[0].raw_score,
        reverse=True,
    )

    eligible: list[tuple[SecurityFeatures, SecuritySeries, tuple[RiskDecision, ...]]] = [
        (feature, security, decisions)
        for feature, security, decisions in ranked
        if feature.raw_score >= threshold
        and not any(d.severity == "HARD_VETO" and not d.passed for d in decisions)
    ]

    industry_count: dict[str, int] = defaultdict(int)
    candidates: list[Candidate] = []
    for feature, security, decisions in eligible:
        if industry_count[security.industry] >= cfg.max_per_industry:
            continue
        industry_count[security.industry] += 1

        warning = next((d for d in decisions if d.severity == "WARNING" and not d.passed), None)
        tier = "FOCUS" if len(candidates) < cfg.max_focus and warning is None else "WATCH"

        candidates.append(
            Candidate(
                id=f"candidate-{security.security_id.replace('.', '-')}",
                security_id=security.security_id,
                name=security.name,
                industry=security.industry,
                close=feature.close,
                score=feature.raw_score,
                confidence=_confidence(feature.raw_score, threshold),
                tier=tier,
                reasons=(
                    f"趋势得分 {feature.trend_score}，近 20 日涨跌幅 {feature.return_20d}%",
                    f"基本面质量得分 {feature.fundamental_score}",
                    f"量能比 {feature.volume_ratio_5d}，流动性得分 {feature.liquidity_score}",
                ),
                risks=(
                    warning.message if warning else f"近 20 日最大回撤 {feature.max_drawdown_20d}%",
                    "市场风格变化可能使当前因子失效",
                ),
                observation=f"关注收盘价 {feature.close} 附近的量价确认，不追逐异常高开。",
                features=feature,
                risk_decisions=tuple(decisions),
            )
        )
        if len(candidates) >= cfg.max_total:
            break

    return SelectionResult(candidates=tuple(candidates), rejected_count=len(ranked) - len(candidates))
