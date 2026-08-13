"""Markdown report renderer.

Never recomputes numbers — only formats already-validated structured data.
The disclaimer '不构成投资建议' and snapshot ID are asserted by the test
suite; do not drop them without updating tests.
"""

from __future__ import annotations

from datetime import date, datetime

from stock_agent.domain.types import AgentResult, Candidate, MarketReview


def _money(value: float) -> str:
    if value >= 100_000_000:
        return f"{value / 100_000_000:.1f} 亿元"
    return f"{value / 10_000:.0f} 万元"


def render_report(
    *,
    trade_date: date,
    as_of_time: datetime,
    snapshot_id: str,
    review: MarketReview,
    candidates: tuple[Candidate, ...],
    agents: tuple[AgentResult, ...],
    coverage: float,
    strategy_version: str,
) -> str:
    regime = {"TREND_UP": "趋势上行", "RISK_OFF": "风险收缩", "RANGE": "区间震荡"}[review.regime]

    if candidates:
        candidate_blocks = []
        for index, candidate in enumerate(candidates, start=1):
            candidate_blocks.append(
                "\n".join(
                    [
                        f"### {index}. {candidate.name}（{candidate.security_id}）",
                        (
                            f"- 行业：{candidate.industry}；收盘价：{candidate.close}；"
                            f"评分：{candidate.score}；置信度：{round(candidate.confidence * 100)}%"
                        ),
                        f"- 入选依据：{'；'.join(candidate.reasons)}",
                        f"- 风险：{'；'.join(candidate.risks)}",
                        f"- 观察条件：{candidate.observation}",
                    ]
                )
            )
        candidate_section = "\n\n".join(candidate_blocks)
    else:
        candidate_section = "当前没有标的同时满足评分和风控标准。"

    leading = "、".join(f"{item.name}（{item.change}%）" for item in review.leading_industries)
    agents_section = "\n".join(
        f"- {agent.role_label}：{agent.summary}（置信度 {round(agent.confidence * 100)}%）"
        for agent in agents
    )

    return f"""# {trade_date.isoformat()} A 股收盘复盘与次日观察池

> 仅供研究参考，不构成投资建议。数据截止时间：{as_of_time.isoformat()}

## 执行摘要

{review.summary} 本次输出 {len(candidates)} 只候选。

## 市场概览

- 市场状态：{regime}
- 样本近 5 日平均涨跌幅：{review.index_change}%
- 上涨占比：{review.advance_ratio}%
- 样本成交额：{_money(review.total_amount)}，较前一日 {review.volume_change}%
- 领先行业：{leading}

## 次日观察池

{candidate_section}

## 多角色复核

{agents_section}

## 数据与版本

- 数据快照：{snapshot_id}
- 核心行情覆盖率：{coverage}%
- 策略版本：{strategy_version}
- 角色版本：1.0.0

> 风险提示：股票市场存在价格波动和本金损失风险。候选是次日观察池，不是买入指令；当市场状态或量价条件变化时，原有逻辑可能失效。
"""
