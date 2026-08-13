"""Structured logging with request-scoped context.

`configure_logging()` is called once at process start (API entry, workers, CLI).
Every log record carries service/env/request_id/run_id when present.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, merge_contextvars

from stock_agent.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared: list[Any] = [
        merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer = structlog.processors.JSONRenderer() if settings.log_json else structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
    for noisy in ("uvicorn.access", "botocore", "boto3", "urllib3"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))


def bind_request_context(**kwargs: Any) -> None:
    bind_contextvars(**{k: v for k, v in kwargs.items() if v is not None})


def clear_request_context() -> None:
    clear_contextvars()


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
