"""Run-related endpoints.

`POST /api/runs` triggers a screening run end-to-end and persists the result.
`GET /api/runs` lists recent runs. `GET /api/runs/{run_id}` returns the full
detail including candidates, agent conclusions, and the Markdown report.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from stock_agent.api.dependencies import get_db, get_run_repository
from stock_agent.api.schemas import (
    CreateRunRequest,
    CreateRunResponse,
    RunDetailResponse,
    RunListResponse,
    RunSummary,
)
from stock_agent.api.security import Actor, require_actor, require_admin
from stock_agent.application.orchestrator import run_stock_agent
from stock_agent.config import get_settings
from stock_agent.infrastructure.data_connectors.factory import get_data_connector
from stock_agent.infrastructure.data_connectors.base import FetchRequest
from stock_agent.infrastructure.observability.metrics import (
    RUN_DURATION_SECONDS,
    RUNS_FAILED,
    RUNS_STARTED,
    RUNS_SUCCEEDED,
)
from stock_agent.infrastructure.storage.run_repository import RunRepository
from stock_agent.logging import bind_request_context, get_logger

router = APIRouter(prefix="/api/runs", tags=["runs"])
_log = get_logger(__name__)


@router.get("", response_model=RunListResponse)
def list_runs(
    _actor: Actor = Depends(require_actor),
    repo: RunRepository = Depends(get_run_repository),
) -> RunListResponse:
    rows = repo.list_recent(limit=30)
    return RunListResponse(items=[RunSummary(**row) for row in rows])


@router.get("/{run_id}", response_model=RunDetailResponse)
def get_run(
    run_id: str,
    _actor: Actor = Depends(require_actor),
    repo: RunRepository = Depends(get_run_repository),
) -> RunDetailResponse:
    detail = repo.load_run_detail(run_id)
    return RunDetailResponse(**detail)


@router.post("", response_model=CreateRunResponse, status_code=201)
def create_run(
    body: CreateRunRequest,
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_db),
    repo: RunRepository = Depends(get_run_repository),
) -> CreateRunResponse:
    settings = get_settings()
    connector_name = body.connector or settings.data_connector
    id_suffix = body.id_suffix or uuid.uuid4().hex[:8]
    bind_request_context(actor=actor.subject, id_suffix=id_suffix, connector=connector_name)
    RUNS_STARTED.labels(connector=connector_name).inc()

    started_at = time.perf_counter()
    try:
        connector = get_data_connector()
        fetch_request = FetchRequest(
            trade_date=body.trade_date or datetime.now(UTC).date(),
        )
        market_input = connector.fetch(fetch_request)
        run = run_stock_agent(market_input, id_suffix=id_suffix)
        repo.persist(market_input, run, actor=actor.subject)
        session.commit()
    except Exception as exc:
        session.rollback()
        RUNS_FAILED.labels(connector=connector_name, error_code=type(exc).__name__).inc()
        _log.exception("run.failed", error=str(exc))
        raise
    finally:
        RUN_DURATION_SECONDS.labels(connector=connector_name).observe(time.perf_counter() - started_at)

    RUNS_SUCCEEDED.labels(connector=connector_name, status=run.status).inc()
    _log.info("run.persisted", run_id=run.run_id, candidates=len(run.candidates))

    return CreateRunResponse(
        run_id=run.run_id,
        snapshot_id=run.snapshot_id,
        report_id=run.report_id,
        trade_date=run.trade_date,
        as_of_time=run.as_of_time,
        status=run.status,
        strategy_version=run.strategy_version,
        candidates=len(run.candidates),
        rejected=run.rejected_count,
    )
