"""Liveness and readiness endpoints. Kept unauthenticated so orchestrators
(Kubernetes, Docker Compose, load balancers) can probe them.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from stock_agent import __version__
from stock_agent.api.dependencies import get_db, get_store
from stock_agent.api.schemas import HealthResponse
from stock_agent.infrastructure.storage.object_store import ObjectStore

router = APIRouter(tags=["health"])


@router.get("/livez", response_model=HealthResponse)
def livez() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__, checks={"process": "ok"})


@router.get("/readyz", response_model=HealthResponse)
def readyz(session: Session = Depends(get_db), store: ObjectStore = Depends(get_store)) -> HealthResponse:
    checks: dict[str, str] = {}
    try:
        session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:  # pragma: no cover
        checks["db"] = f"fail: {exc}"

    try:
        store.ensure_bucket()
        checks["object_store"] = "ok"
    except Exception as exc:  # pragma: no cover
        checks["object_store"] = f"fail: {exc}"

    overall = "ok" if all(value == "ok" for value in checks.values()) else "degraded"
    return HealthResponse(status=overall, version=__version__, checks=checks)
