"""SQLAlchemy engine + session factory. Single engine per process."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from stock_agent.config import get_settings

_settings = get_settings()

engine: Engine = create_engine(
    _settings.database_url,
    pool_size=_settings.database_pool_size,
    max_overflow=_settings.database_pool_max_overflow,
    pool_pre_ping=True,
    future=True,
)

SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency."""

    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Transactional context manager for workers and scripts."""

    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
