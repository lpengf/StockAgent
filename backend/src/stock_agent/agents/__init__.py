"""Deterministic agent roles.

Each function here corresponds to one row in the design doc's agent DAG.
Currently deterministic; the LLM gateway seam is `stock_agent.infrastructure.llm`
so future LLM-backed agents can slot in without touching orchestrator code.
"""

from stock_agent.agents.roles import (
    run_coordinator_agent,
    run_market_agent,
    run_quant_agent,
    run_report_agent,
    run_risk_agent,
)

__all__ = [
    "run_coordinator_agent",
    "run_market_agent",
    "run_quant_agent",
    "run_report_agent",
    "run_risk_agent",
]
