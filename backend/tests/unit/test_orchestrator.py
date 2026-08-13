"""End-to-end orchestrator tests. Mirror the TS reference suite."""

from __future__ import annotations

import re

import pytest

from stock_agent.application.orchestrator import run_stock_agent
from stock_agent.domain.features import compute_features
from stock_agent.domain.quality import validate_input
from stock_agent.domain.risk import evaluate_risk
from stock_agent.domain.types import MarketInput
from stock_agent.errors import DataQualityError


def test_full_run_produces_snapshot_five_agents_and_report(demo_input: MarketInput) -> None:
    run = run_stock_agent(demo_input, id_suffix="test-1")

    assert run.status == "SUCCEEDED"
    assert len(run.agents) == 5
    assert run.data_quality.coverage == 100.0
    assert len(run.candidates) > 0
    assert re.search(re.escape(run.snapshot_id), run.report_markdown)
    assert "不构成投资建议" in run.report_markdown


def test_st_sample_triggers_unblockable_hard_veto(demo_input: MarketInput) -> None:
    st_security = next(security for security in demo_input.securities if security.is_st)
    decisions = evaluate_risk(st_security, compute_features(st_security))
    assert any(decision.severity == "HARD_VETO" and not decision.passed for decision in decisions)

    run = run_stock_agent(demo_input, id_suffix="test-2")
    assert all(candidate.security_id != st_security.security_id for candidate in run.candidates)


def test_low_coverage_stops_the_run(demo_input: MarketInput) -> None:
    stripped = demo_input.model_copy(
        update={
            "securities": (
                demo_input.securities[0].model_copy(update={"bars": ()}),
                *demo_input.securities[1:],
            )
        }
    )
    with pytest.raises(DataQualityError, match="覆盖率"):
        validate_input(stripped)


def test_same_input_produces_deterministic_output(demo_input: MarketInput) -> None:
    first = run_stock_agent(demo_input, id_suffix="det")
    second = run_stock_agent(demo_input, id_suffix="det")

    first_sig = [(candidate.security_id, candidate.score, candidate.tier) for candidate in first.candidates]
    second_sig = [(candidate.security_id, candidate.score, candidate.tier) for candidate in second.candidates]
    assert first_sig == second_sig
