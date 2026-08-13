"""Choose the data connector based on configuration.

Kept in a separate module so the connector implementations are only imported
when actually needed (akshare has a slow import path).
"""

from __future__ import annotations

from collections.abc import Iterable

from stock_agent.config import get_settings
from stock_agent.infrastructure.data_connectors.base import DataConnector


def get_data_connector(security_ids: Iterable[str] | None = None) -> DataConnector:
    settings = get_settings()
    if settings.data_connector == "demo":
        from stock_agent.infrastructure.data_connectors.demo import DemoConnector

        return DemoConnector()
    if settings.data_connector == "akshare":
        from stock_agent.infrastructure.data_connectors.akshare_connector import AkshareConnector

        return AkshareConnector(security_ids or ())
    raise ValueError(f"unsupported data connector: {settings.data_connector}")
