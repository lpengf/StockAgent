"""APScheduler process that enqueues the daily Celery task.

Kept intentionally minimal: this is *just* the trigger. All heavy work lives
inside the worker task so the scheduler can crash-restart without losing a
run in flight.

Run with:
    python -m stock_agent.scheduler.main
"""

from __future__ import annotations

import signal
import threading

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from stock_agent.config import get_settings
from stock_agent.logging import configure_logging, get_logger
from stock_agent.workers.tasks import run_daily_screening


def _trigger(**kwargs: str) -> None:  # noqa: ARG001 — signature kept for APScheduler compatibility
    log = get_logger(__name__)
    task = run_daily_screening.delay()
    log.info("scheduler.enqueued", task_id=task.id)


def main() -> None:
    configure_logging()
    settings = get_settings()
    log = get_logger(__name__)

    scheduler = BlockingScheduler(timezone=settings.scheduler_timezone)
    trigger = CronTrigger.from_crontab(settings.scheduler_run_cron, timezone=settings.scheduler_timezone)
    scheduler.add_job(_trigger, trigger=trigger, id="daily_screening", replace_existing=True)

    stop_event = threading.Event()

    def _handle_signal(signum: int, frame: object) -> None:  # noqa: ARG001
        del signum, frame
        log.info("scheduler.shutdown")
        scheduler.shutdown(wait=False)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    log.info("scheduler.start", cron=settings.scheduler_run_cron, tz=settings.scheduler_timezone)
    scheduler.start()


if __name__ == "__main__":  # pragma: no cover
    main()
