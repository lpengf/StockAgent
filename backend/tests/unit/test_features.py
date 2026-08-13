"""Unit tests for pure feature computation."""

from __future__ import annotations

from stock_agent.domain.features import compute_features
from stock_agent.domain.types import MarketInput


def test_features_are_bounded_and_finite(demo_input: MarketInput) -> None:
    for security in demo_input.securities:
        feature = compute_features(security)
        assert 0.0 <= feature.trend_score <= 100.0
        assert 0.0 <= feature.liquidity_score <= 100.0
        assert 0.0 <= feature.fundamental_score <= 100.0
        assert 0.0 <= feature.raw_score <= 100.0
        assert feature.close > 0
        assert feature.volatility_20d >= 0


def test_return_columns_agree_with_close_history(demo_input: MarketInput) -> None:
    security = demo_input.securities[0]
    feature = compute_features(security)
    closes = [bar.close for bar in security.bars]
    expected_5d = round((closes[-1] / closes[-6] - 1) * 100 * 100) / 100
    assert abs(feature.return_5d - expected_5d) < 0.05
