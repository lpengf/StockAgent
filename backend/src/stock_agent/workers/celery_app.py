"""Celery entry point.

Run with:
    celery -A stock_agent.workers.celery_app worker -Q data,agent,report -l info

Queues match the roles described in the design doc's deployment section, but
initial deploys can consume all queues on the same worker.
"""

from __future__ import annotations

from celery import Celery

from stock_agent.config import get_settings
from stock_agent.logging import configure_logging

configure_logging()
_settings = get_settings()

celery_app = Celery(
    "stock_agent",
    broker=_settings.celery_broker_url,
    backend=_settings.celery_result_backend,
    include=["stock_agent.workers.tasks"],
)
celery_app.conf.update(
    task_default_queue="default",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=_settings.scheduler_timezone,
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=15 * 60,
    task_soft_time_limit=10 * 60,
    broker_connection_retry_on_startup=True,
    task_routes={
        "stock_agent.workers.tasks.run_daily_screening": {"queue": "agent"},
    },
)
