"""Deterministic risk rules.

Rules mirror the design doc's `RISK-*` codes. Each rule returns a decision
that either passes or emits `HARD_VETO` / `WARNING` — no side effects, no
mutation of inputs.
"""

from __future__ import annotations

import numpy as np

from stock_agent.domain.types import RiskDecision, SecurityFeatures, SecuritySeries

MIN_AVG_AMOUNT_20D = 20_000_000.0
MAX_ANNUAL_VOLATILITY_PCT = 55.0


def evaluate_risk(security: SecuritySeries, feature: SecurityFeatures) -> tuple[RiskDecision, ...]:
    tail = np.array([bar.amount for bar in security.bars[-20:]], dtype=np.float64)
    average_amount = float(tail.mean()) if tail.size else 0.0

    return (
        RiskDecision(
            rule_id="RISK-TRADE-001",
            severity="HARD_VETO",
            passed=not security.is_st,
            message="ST/退市风险证券不进入候选池" if security.is_st else "非 ST 证券",
        ),
        RiskDecision(
            rule_id="RISK-TRADE-002",
            severity="HARD_VETO",
            passed=not security.is_suspended,
            message="当前停牌" if security.is_suspended else "正常交易",
        ),
        RiskDecision(
            rule_id="RISK-LIQ-001",
            severity="HARD_VETO",
            passed=average_amount >= MIN_AVG_AMOUNT_20D,
            message="20 日平均成交额满足阈值" if average_amount >= MIN_AVG_AMOUNT_20D else "流动性不足",
        ),
        RiskDecision(
            rule_id="RISK-VOL-001",
            severity="WARNING",
            passed=feature.volatility_20d <= MAX_ANNUAL_VOLATILITY_PCT,
            message=(
                "波动率处于允许范围"
                if feature.volatility_20d <= MAX_ANNUAL_VOLATILITY_PCT
                else "年化波动率偏高"
            ),
        ),
    )
