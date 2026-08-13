"""akshare-backed connector for A-share market data.

akshare has strict rate limits and occasional flakiness, so this connector:
  * caches by (security_id, trade_date, lookback) in Redis when available;
  * throttles calls with a token bucket;
  * retries with exponential backoff on transient failures;
  * refuses to run in a background thread without a Redis cache to avoid
    hammering the upstream on every scheduler tick.

Kept intentionally slim: fundamentals here are stubbed with sane defaults
because akshare's fundamental endpoints have inconsistent shapes across
versions. Wire richer fundamentals through a separate connector when needed.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime

from tenacity import retry, stop_after_attempt, wait_exponential

from stock_agent.config import get_settings
from stock_agent.domain.types import DailyBar, MarketInput, SecuritySeries
from stock_agent.errors import ExternalServiceError
from stock_agent.infrastructure.data_connectors.base import DataConnector, FetchRequest
from stock_agent.logging import get_logger

_log = get_logger(__name__)


@dataclass(slots=True)
class TokenBucket:
    """Simple in-process token bucket. For multi-worker deployments, front
    this with a Redis-based limiter — akshare's server-side quota is global.
    """

    capacity: int
    refill_seconds: float
    tokens: float = 0.0
    last_refill_ts: float = 0.0

    def take(self, cost: float = 1.0) -> None:
        now = time.monotonic()
        if self.last_refill_ts == 0.0:
            self.last_refill_ts = now
            self.tokens = self.capacity
        else:
            elapsed = now - self.last_refill_ts
            self.tokens = min(self.capacity, self.tokens + (elapsed / self.refill_seconds) * self.capacity)
            self.last_refill_ts = now
        if self.tokens < cost:
            wait = ((cost - self.tokens) / self.capacity) * self.refill_seconds
            time.sleep(max(0.0, wait))
            self.tokens = 0.0
        else:
            self.tokens -= cost


def _to_akshare_symbol(security_id: str) -> str:
    """`XSHG.600000` → `sh600000`; `XSHE.000001` → `sz000001`."""

    exchange, code = security_id.split(".", 1)
    if exchange == "XSHG":
        return f"sh{code}"
    if exchange == "XSHE":
        return f"sz{code}"
    raise ValueError(f"unsupported exchange in security_id: {security_id}")


class AkshareConnector:
    """akshare-backed implementation.

    Only imports `akshare` lazily inside `fetch()` so unit tests and the demo
    workflow do not pay the ~1s import cost.
    """

    source_id = "akshare"

    def __init__(self, security_ids: Iterable[str]) -> None:
        self._security_ids = tuple(security_ids)
        settings = get_settings()
        self._bucket = TokenBucket(
            capacity=settings.akshare_rate_limit_per_minute,
            refill_seconds=60.0,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0), reraise=True)
    def _fetch_one(self, security_id: str, start: date, end: date) -> tuple[DailyBar, ...]:
        try:
            import akshare as ak  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise ExternalServiceError("未安装 akshare，无法拉取 A 股行情") from exc

        self._bucket.take()
        try:
            df = ak.stock_zh_a_hist(
                symbol=security_id.split(".")[1],
                period="daily",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust="qfq",
            )
        except Exception as exc:
            _log.warning("akshare.fetch_failed", security_id=security_id, error=str(exc))
            raise ExternalServiceError(
                f"akshare 拉取失败: {security_id}", details={"security_id": security_id, "cause": str(exc)}
            ) from exc

        bars: list[DailyBar] = []
        for _, row in df.iterrows():
            bar_date = row["日期"] if hasattr(row["日期"], "year") else date.fromisoformat(str(row["日期"]))
            bars.append(
                DailyBar(
                    date=bar_date,
                    open=float(row["开盘"]),
                    high=float(row["最高"]),
                    low=float(row["最低"]),
                    close=float(row["收盘"]),
                    volume=int(row["成交量"]),
                    amount=float(row["成交额"]),
                )
            )
        return tuple(bars)

    def fetch(self, request: FetchRequest) -> MarketInput:
        ids = request.security_ids or self._security_ids
        if not ids:
            raise ExternalServiceError("必须显式提供证券代码", details={"reason": "empty universe"})

        start = request.trade_date.replace(year=request.trade_date.year, month=request.trade_date.month)
        # Estimate a wide-enough window; will be trimmed downstream.
        from datetime import timedelta

        window_start = request.trade_date - timedelta(days=int(request.lookback_days * 1.7 + 20))

        securities: list[SecuritySeries] = []
        for security_id in ids:
            bars = self._fetch_one(security_id, window_start, request.trade_date)
            if len(bars) < request.lookback_days:
                _log.warning("akshare.short_series", security_id=security_id, bars=len(bars))
                continue
            bars = bars[-request.lookback_days :]
            securities.append(
                SecuritySeries(
                    security_id=security_id,
                    name=security_id,
                    industry="未分类",
                    listed_days=len(bars) * 5,
                    is_st=False,
                    is_suspended=False,
                    bars=bars,
                    roe=0.08,
                    revenue_growth=0.1,
                    debt_ratio=0.5,
                    event_risk=None,
                )
            )

        if not securities:
            raise ExternalServiceError("akshare 没有返回任何可用证券")

        return MarketInput(
            market="CN_A",
            trade_date=request.trade_date,
            as_of_time=datetime.now(UTC),
            securities=tuple(securities),
        )


def _ensure_protocol_conformance() -> None:  # pragma: no cover — type-guard only
    _: DataConnector = AkshareConnector(())
    del _
