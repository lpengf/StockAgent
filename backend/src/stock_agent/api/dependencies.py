"""FastAPI dependency providers."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from stock_agent.infrastructure.db.session import get_session
from stock_agent.infrastructure.storage.object_store import ObjectStore, get_object_store
from stock_agent.infrastructure.storage.run_repository import RunRepository


def get_db() -> Generator[Session, None, None]:
    yield from get_session()


def get_store() -> ObjectStore:
    return get_object_store()


def get_run_repository(
    session: Session = Depends(get_db),
    store: ObjectStore = Depends(get_store),
) -> RunRepository:
    return RunRepository(session=session, store=store)
