"""Offline demo connector.

Byte-for-byte parity with the TypeScript reference `demo-data.ts` so replay
tests can compare with the legacy implementation. The date base is fixed at
2026-07-14 (matches `Date.UTC(2026, 6, 13 + offset)` from the TS source,
which is 0-indexed month) — do not change without updating replay fixtures.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta

from stock_agent.domain.types import DailyBar, MarketInput, SecuritySeries
from stock_agent.infrastructure.data_connectors.base import DataConnector, FetchRequest

_ROSTER: tuple[tuple[str, str, str, float, float, float, float, float, float], ...] = (
    ("XSHE.000001", "平安银行", "银行", 10.4, 0.0022, 0.18, 0.115, 0.04, 0.63),
    ("XSHG.600519", "贵州茅台", "食品饮料", 1398.0, 0.0017, 0.12, 0.31, 0.09, 0.18),
    ("XSHE.300750", "宁德时代", "电力设备", 268.0, 0.0045, 0.28, 0.24, 0.18, 0.55),
    ("XSHG.601012", "隆基绿能", "电力设备", 19.8, -0.001, 0.31, 0.05, -0.08, 0.58),
    ("XSHG.600036", "招商银行", "银行", 43.2, 0.0031, 0.16, 0.146, 0.055, 0.61),
    ("XSHE.002594", "比亚迪", "汽车", 324.0, 0.004, 0.26, 0.215, 0.14, 0.72),
    ("XSHG.688981", "中芯国际", "电子", 91.0, 0.0054, 0.34, 0.09, 0.16, 0.42),
    ("XSHE.000333", "美的集团", "家用电器", 76.0, 0.0028, 0.14, 0.235, 0.095, 0.49),
    ("XSHG.601318", "中国平安", "非银金融", 58.0, 0.0019, 0.15, 0.132, 0.062, 0.64),
    ("XSHE.300059", "东方财富", "非银金融", 27.0, 0.005, 0.37, 0.105, 0.19, 0.38),
    ("XSHG.603000", "风险样本", "传媒", 12.2, 0.008, 0.65, -0.02, -0.2, 0.83),
    ("XSHE.002001", "流动性样本", "基础化工", 8.6, -0.002, 0.08, 0.08, 0.03, 0.45),
)

_BASE_DATE = date(2026, 7, 14)  # Mirrors TS `Date.UTC(2026, 6, 13 + offset)` at offset=1
_TRADE_DATE = date(2026, 8, 11)
_AS_OF_TIME = datetime(2026, 8, 11, 8, 30, tzinfo=UTC)
_BARS = 22


def _round2(value: float) -> float:
    return math.floor(value * 100 + 0.5) / 100 if value >= 0 else -math.floor(-value * 100 + 0.5) / 100


def _build_bars(base: float, drift: float, volatility: float, index: int) -> tuple[DailyBar, ...]:
    previous = base
    bars: list[DailyBar] = []
    for day in range(_BARS):
        wave = math.sin((day + index) * 1.31) * volatility * 0.016
        shock = (((day * 7 + index * 11) % 9) - 4) * volatility * 0.0025
        close = max(1.0, previous * (1 + drift + wave + shock))
        open_ = previous * (1 + math.sin(day + index) * 0.002)
        high = max(open_, close) * (1 + 0.006 + volatility * 0.01)
        low = min(open_, close) * (1 - 0.006 - volatility * 0.008)
        volume_base = 90_000 if index == 11 else 6_000_000 + index * 700_000
        volume = round(volume_base * (0.82 + day * 0.012 + abs(wave) * 8))
        previous = close
        bars.append(
            DailyBar(
                date=_BASE_DATE + timedelta(days=day),
                open=_round2(open_),
                high=_round2(high),
                low=_round2(low),
                close=_round2(close),
                volume=volume,
                amount=round(volume * close),
            )
        )
    return tuple(bars)


class DemoConnector:
    """Deterministic in-memory connector for tests and offline demos."""

    source_id = "demo"

    def fetch(self, request: FetchRequest) -> MarketInput:
        del request  # request ignored; demo is fixed
        securities = tuple(
            SecuritySeries(
                security_id=row[0],
                name=row[1],
                industry=row[2],
                listed_days=420 if index == 10 else 1500 + index * 50,
                is_st=index == 10,
                is_suspended=False,
                bars=_build_bars(row[3], row[4], row[5], index),
                roe=row[6],
                revenue_growth=row[7],
                debt_ratio=row[8],
                event_risk="退市风险警示" if index == 10 else None,
            )
            for index, row in enumerate(_ROSTER)
        )
        return MarketInput(market="CN_A", trade_date=_TRADE_DATE, as_of_time=_AS_OF_TIME, securities=securities)


def _ensure_protocol_conformance() -> None:  # pragma: no cover — type-guard only
    _: DataConnector = DemoConnector()
    del _
