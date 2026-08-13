"""Data-connector Protocol. Any adapter that returns `MarketInput` may be
plugged in (akshare, tushare, baostock, an in-house feed …) with no changes
to the domain or application layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from stock_agent.domain.types import MarketInput


@dataclass(frozen=True, slots=True)
class FetchRequest:
    trade_date: date
    security_ids: tuple[str, ...] | None = None
    lookback_days: int = 22


class DataConnector(Protocol):
    """Fetch a fully-validated `MarketInput` for a given trade date."""

    source_id: str

    def fetch(self, request: FetchRequest) -> MarketInput: ...
