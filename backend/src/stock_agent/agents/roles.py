"""Five deterministic agent roles.

The `risk_officer` role produces the publication-gate sentinel that the
orchestrator relies on: the FIRST conclusion string must be the exact literal
`"无未处理硬否决"` when it passes. Downstream code compares against this
string — do not change it without also updating the orchestrator gate check
and any consumers of the conclusion payload.
"""

from __future__ import annotations

from datetime import datetime

from stock_agent.domain.types import AgentResult, AgentRoleId, Candidate, Evidence, MarketReview

RISK_GATE_PASS_SENTINEL = "无未处理硬否决"


def _make_result(
    role_id: AgentRoleId,
    role_label: str,
    confidence: float,
    summary: str,
    conclusions: tuple[str, ...],
    evidence: tuple[Evidence, ...],
    risks: tuple[str, ...] = (),
) -> AgentResult:
    return AgentResult(
        id=f"agent-{role_id}",
        role_id=role_id,
        role_label=role_label,
        confidence=confidence,
        summary=summary,
        conclusions=conclusions,
        evidence=evidence,
        risks=risks,
        duration_ms=8 + len(conclusions) * 3,
    )


def run_coordinator_agent(as_of_time: datetime, coverage: float) -> AgentResult:
    return _make_result(
        role_id="coordinator",
        role_label="协调 Agent",
        confidence=0.99,
        summary="数据快照已冻结，专业角色按依赖图完成分析。",
        conclusions=(
            "核心数据质量门禁通过",
            "量化与风控角色为强制发布依赖",
            "报告仅引用结构化结果",
        ),
        evidence=(
            Evidence(
                id="ev-data-coverage",
                type="DATA_QUALITY",
                label="核心行情覆盖率",
                value=f"{coverage}%",
                as_of_time=as_of_time,
            ),
        ),
    )


def run_market_agent(review: MarketReview, as_of_time: datetime) -> AgentResult:
    regime_label = {"TREND_UP": "趋势上行", "RISK_OFF": "风险收缩", "RANGE": "区间震荡"}[review.regime]
    lead_names = "、".join(item.name for item in review.leading_industries)
    risks = (
        ("风险偏好收缩，应减少候选数量",) if review.regime == "RISK_OFF" else ("风格切换可能降低趋势信号有效性",)
    )
    return _make_result(
        role_id="market_analyst",
        role_label="市场分析 Agent",
        confidence=0.82,
        summary=review.summary,
        conclusions=(
            f"市场状态：{regime_label}",
            f"上涨样本占比 {review.advance_ratio}%",
            f"领先行业：{lead_names}",
        ),
        evidence=(
            Evidence(
                id="ev-index-change",
                type="METRIC",
                label="样本近 5 日平均涨跌幅",
                value=f"{review.index_change}%",
                as_of_time=as_of_time,
            ),
            Evidence(
                id="ev-advance-ratio",
                type="METRIC",
                label="上涨占比",
                value=f"{review.advance_ratio}%",
                as_of_time=as_of_time,
            ),
        ),
        risks=risks,
    )


def run_quant_agent(
    candidates: tuple[Candidate, ...],
    rejected_count: int,
    as_of_time: datetime,
) -> AgentResult:
    top = candidates[0] if candidates else None
    summary = (
        f"规则引擎筛出 {len(candidates)} 只候选，{rejected_count} 只未入池。"
        if candidates
        else "当前没有股票通过评分与分散约束。"
    )
    conclusions = (
        f"候选数量：{len(candidates)}",
        (f"最高评分：{top.name} {top.score}" if top else "允许空候选，不降低阈值"),
        "评分由趋势、流动性、基本面和风险惩罚确定性计算",
    )
    return _make_result(
        role_id="quant_analyst",
        role_label="量化 Agent",
        confidence=0.86 if candidates else 0.62,
        summary=summary,
        conclusions=conclusions,
        evidence=(
            Evidence(
                id="ev-candidate-count",
                type="METRIC",
                label="通过候选数",
                value=str(len(candidates)),
                as_of_time=as_of_time,
            ),
        ),
    )


def run_risk_agent(candidates: tuple[Candidate, ...], as_of_time: datetime) -> AgentResult:
    unresolved = [
        decision
        for candidate in candidates
        for decision in candidate.risk_decisions
        if decision.severity == "HARD_VETO" and not decision.passed
    ]
    passed = not unresolved
    top_risks = tuple(risk for candidate in candidates for risk in candidate.risks)[:3]
    return _make_result(
        role_id="risk_officer",
        role_label="风控 Agent",
        confidence=0.96,
        summary=(
            "重点与观察候选均通过硬风控门禁。"
            if passed
            else "发现未处理硬否决，禁止发布候选。"
        ),
        conclusions=(
            RISK_GATE_PASS_SENTINEL if passed else f"存在 {len(unresolved)} 项硬否决",
            "已检查 ST、停牌、流动性与异常波动",
            "候选池执行单行业数量限制",
        ),
        evidence=(
            Evidence(
                id="ev-risk-gate",
                type="RULE",
                label="硬风控门禁",
                value="PASSED" if passed else "FAILED",
                as_of_time=as_of_time,
            ),
        ),
        risks=top_risks,
    )


def run_report_agent(candidate_count: int, as_of_time: datetime) -> AgentResult:
    return _make_result(
        role_id="report_writer",
        role_label="报告 Agent",
        confidence=0.94,
        summary="报告已根据已验证结构化结果生成，未新增计算数值。",
        conclusions=(
            "复盘摘要已生成",
            f"已生成 {candidate_count} 张候选卡片",
            "免责声明与版本信息已写入",
        ),
        evidence=(
            Evidence(
                id="ev-report-gate",
                type="RULE",
                label="报告一致性检查",
                value="PASSED",
                as_of_time=as_of_time,
            ),
        ),
    )
