"""Celery tasks.

The main daily task delegates to the same orchestrator used by the sync API —
there is exactly one code path from `MarketInput` to a persisted `StockAgentRun`.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, date, datetime

from stock_agent.application.orchestrator import run_stock_agent
from stock_agent.infrastructure.data_connectors.base import FetchRequest
from stock_agent.infrastructure.data_connectors.factory import get_data_connector
from stock_agent.infrastructure.db.session import session_scope
from stock_agent.infrastructure.observability.metrics import (
    RUN_DURATION_SECONDS,
    RUNS_FAILED,
    RUNS_STARTED,
    RUNS_SUCCEEDED,
)
from stock_agent.infrastructure.storage.object_store import get_object_store
from stock_agent.infrastructure.storage.run_repository import RunRepository
from stock_agent.logging import get_logger
from stock_agent.workers.celery_app import celery_app

_log = get_logger(__name__)


@celery_app.task(
    name="stock_agent.workers.tasks.run_daily_screening",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    bind=True,
)
def run_daily_screening(self, trade_date_iso: str | None = None, connector: str | None = None) -> dict:
    del self  # bind=True is used only for structured logs
    trade_date = date.fromisoformat(trade_date_iso) if trade_date_iso else datetime.now(UTC).date()
    connector_name = connector or "configured"
    id_suffix = uuid.uuid4().hex[:8]
    _log.info("task.start", trade_date=trade_date.isoformat(), id_suffix=id_suffix)

    RUNS_STARTED.labels(connector=connector_name).inc()
    started = time.perf_counter()
    try:
        conn = get_data_connector()
        market_input = conn.fetch(FetchRequest(trade_date=trade_date))
        run = run_stock_agent(market_input, id_suffix=id_suffix)
        with session_scope() as session:
            repo = RunRepository(session=session, store=get_object_store())
            repo.persist(market_input, run, actor="scheduler")
        RUNS_SUCCEEDED.labels(connector=connector_name, status=run.status).inc()
        return {"run_id": run.run_id, "snapshot_id": run.snapshot_id, "status": run.status}
    except Exception as exc:
        RUNS_FAILED.labels(connector=connector_name, error_code=type(exc).__name__).inc()
        raise
    finally:
        RUN_DURATION_SECONDS.labels(connector=connector_name).observe(time.perf_counter() - started)
