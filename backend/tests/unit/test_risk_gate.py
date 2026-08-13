"""Risk-gate sentinel behavior."""

from __future__ import annotations

from datetime import UTC, datetime

from stock_agent.agents.roles import RISK_GATE_PASS_SENTINEL, run_risk_agent


def test_risk_agent_pass_returns_gate_sentinel_first() -> None:
    result = run_risk_agent((), datetime.now(UTC))
    assert result.conclusions[0] == RISK_GATE_PASS_SENTINEL


def test_risk_agent_records_veto_count_when_present() -> None:
    from stock_agent.domain.types import Candidate, RiskDecision, SecurityFeatures

    veto = RiskDecision(
        rule_id="RISK-TRADE-001",
        severity="HARD_VETO",
        passed=False,
        message="ST",
    )
    feature = SecurityFeatures(
        security_id="XSHE.000001",
        name="平安银行",
        industry="银行",
        close=10.0,
        return_5d=0.0,
        return_20d=0.0,
        volume_ratio_5d=1.0,
        volatility_20d=0.0,
        max_drawdown_20d=0.0,
        liquidity_score=50.0,
        fundamental_score=50.0,
        trend_score=50.0,
        raw_score=50.0,
    )
    candidate = Candidate(
        id="c",
        security_id="XSHE.000001",
        name="平安银行",
        industry="银行",
        close=10.0,
        score=60.0,
        confidence=0.6,
        tier="WATCH",
        reasons=("r",),
        risks=("r",),
        observation="obs",
        features=feature,
        risk_decisions=(veto,),
    )
    result = run_risk_agent((candidate,), datetime.now(UTC))
    assert result.conclusions[0] != RISK_GATE_PASS_SENTINEL
    assert "硬否决" in result.conclusions[0]
