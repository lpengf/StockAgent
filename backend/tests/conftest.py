"""Shared pytest fixtures.

Environment defaults are set at module import so any settings-reading code
loaded during collection sees test values, not developer secrets.
"""

from __future__ import annotations

import os
from datetime import date

os.environ.setdefault("DATA_CONNECTOR", "demo")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("ADMIN_API_KEY", "test-admin")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://stock:stock@localhost:5432/stock_agent_test")
os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:9000")

import pytest

from stock_agent.domain.types import MarketInput
from stock_agent.infrastructure.data_connectors.base import FetchRequest
from stock_agent.infrastructure.data_connectors.demo import DemoConnector


@pytest.fixture
def demo_connector() -> DemoConnector:
    return DemoConnector()


@pytest.fixture
def demo_input(demo_connector: DemoConnector) -> MarketInput:
    return demo_connector.fetch(FetchRequest(trade_date=date(2026, 8, 11)))
