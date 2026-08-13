"""Orchestrates one screening run end-to-end.

Stage ordering is FIXED because the risk gate depends on the risk agent
having executed before the report agent. Any change to `agents` ordering or
the risk-gate sentinel string must be reflected in
`stock_agent.agents.roles.RISK_GATE_PASS_SENTINEL` and in the test suite.
"""

from __future__ import annotations

from stock_agent.agents.roles import (
    RISK_GATE_PASS_SENTINEL,
    run_coordinator_agent,
    run_market_agent,
    run_quant_agent,
    run_report_agent,
    run_risk_agent,
)
from stock_agent.application.report import render_report
from stock_agent.config import get_settings
from stock_agent.domain.features import compute_features
from stock_agent.domain.market_review import build_market_review
from stock_agent.domain.quality import validate_input
from stock_agent.domain.selection import SelectionConfig, select_candidates
from stock_agent.domain.types import MarketInput, StockAgentRun
from stock_agent.errors import RiskGateError
from stock_agent.logging import get_logger

_log = get_logger(__name__)


def run_stock_agent(input_data: MarketInput, id_suffix: str = "demo") -> StockAgentRun:
    settings = get_settings()
    trade_key = input_data.trade_date.isoformat().replace("-", "")
    run_id = f"run-{trade_key}-{id_suffix}"
    snapshot_id = f"snapshot-{trade_key}-{id_suffix}"
    report_id = f"report-{trade_key}-{id_suffix}"

    _log.info("orchestrator.start", run_id=run_id, snapshot_id=snapshot_id, securities=len(input_data.securities))

    data_quality = validate_input(input_data)
    features = tuple(compute_features(security) for security in input_data.securities)
    market_review = build_market_review(input_data, features)

    selection = select_candidates(
        input_data,
        features,
        market_review.regime,
        SelectionConfig(
            max_focus=settings.max_focus_candidates,
            max_total=settings.max_total_candidates,
            max_per_industry=settings.max_per_industry,
        ),
    )

    agents = [
        run_coordinator_agent(input_data.as_of_time, data_quality.coverage),
        run_market_agent(market_review, input_data.as_of_time),
        run_quant_agent(selection.candidates, selection.rejected_count, input_data.as_of_time),
        run_risk_agent(selection.candidates, input_data.as_of_time),
    ]

    risk_result = next(agent for agent in agents if agent.role_id == "risk_officer")
    if not risk_result.conclusions or risk_result.conclusions[0] != RISK_GATE_PASS_SENTINEL:
        _log.warning(
            "orchestrator.risk_gate_failed",
            run_id=run_id,
            risk_summary=risk_result.summary,
            risk_conclusions=risk_result.conclusions,
        )
        raise RiskGateError(
            "风控发布门禁失败",
            details={"run_id": run_id, "conclusions": list(risk_result.conclusions)},
        )

    agents.append(run_report_agent(len(selection.candidates), input_data.as_of_time))
    report_markdown = render_report(
        trade_date=input_data.trade_date,
        as_of_time=input_data.as_of_time,
        snapshot_id=snapshot_id,
        review=market_review,
        candidates=selection.candidates,
        agents=tuple(agents),
        coverage=data_quality.coverage,
        strategy_version=settings.strategy_version,
    )

    _log.info(
        "orchestrator.done",
        run_id=run_id,
        candidates=len(selection.candidates),
        rejected=selection.rejected_count,
        status=data_quality.status,
    )

    return StockAgentRun(
        run_id=run_id,
        snapshot_id=snapshot_id,
        report_id=report_id,
        trade_date=input_data.trade_date,
        as_of_time=input_data.as_of_time,
        strategy_version=settings.strategy_version,
        status="SUCCEEDED" if data_quality.status == "PASSED" else "DEGRADED_SUCCEEDED",
        data_quality=data_quality,
        market_review=market_review,
        candidates=selection.candidates,
        rejected_count=selection.rejected_count,
        agents=tuple(agents),
        report_markdown=report_markdown,
    )
