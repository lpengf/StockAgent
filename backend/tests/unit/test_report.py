"""Report renderer contract tests."""

from __future__ import annotations

from stock_agent.application.orchestrator import run_stock_agent


def test_report_contains_disclaimer_snapshot_and_regime(demo_input) -> None:  # type: ignore[no-untyped-def]
    run = run_stock_agent(demo_input, id_suffix="report")
    text = run.report_markdown
    assert "不构成投资建议" in text
    assert run.snapshot_id in text
    assert run.market_review.regime in {"TREND_UP", "RANGE", "RISK_OFF"}
    assert "策略版本" in text
