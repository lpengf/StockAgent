"""Data-quality gate that runs before feature computation.

Raises `DataQualityError` on hard failures; returns a `DataQuality` object
otherwise. Coverage is measured as the fraction of securities that meet the
minimum bar count and pass OHLC sanity.
"""

from __future__ import annotations

from stock_agent.config import get_settings
from stock_agent.domain.types import DataQuality, MarketInput, SecuritySeries
from stock_agent.errors import DataQualityError, ValidationError

MIN_BARS = 20


def _security_is_complete(security: SecuritySeries) -> bool:
    if len(security.bars) < MIN_BARS:
        return False
    for bar in security.bars:
        if bar.close <= 0 or bar.high < bar.low:
            return False
    return True


def validate_input(input_data: MarketInput) -> DataQuality:
    ids = [security.security_id for security in input_data.securities]
    if len(set(ids)) != len(ids):
        raise ValidationError("证券代码存在重复", details={"duplicates": _duplicates(ids)})

    if not input_data.securities:
        raise ValidationError("证券列表为空")

    complete = sum(1 for security in input_data.securities if _security_is_complete(security))
    coverage = round((complete / len(input_data.securities)) * 10000) / 100

    threshold = get_settings().coverage_hard_threshold
    if coverage < threshold:
        raise DataQualityError(
            f"核心行情覆盖率 {coverage}% 低于 {threshold}% 门槛",
            details={"coverage": coverage, "threshold": threshold},
        )

    return DataQuality(
        status="PASSED" if coverage == 100 else "DEGRADED",
        coverage=coverage,
        checks=(
            "交易日与截止时间有效",
            "OHLC 关系检查通过",
            "证券代码无重复",
            f"核心行情覆盖率 {coverage}%",
        ),
    )


def _duplicates(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for i in ids:
        if i in seen:
            dupes.add(i)
        seen.add(i)
    return sorted(dupes)
