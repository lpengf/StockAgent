"""`stock-agent` CLI.

Common operations:
  * `run` — trigger a screening run synchronously and print the run_id.
  * `backfill` — run against a list of past dates (uses configured connector).
  * `replay` — reconstruct a past run from persisted snapshot for regression.
  * `serve` — launch the FastAPI app under uvicorn (dev convenience).
  * `worker` / `scheduler` — spawn the corresponding process.
"""

from __future__ import annotations

import sys
import uuid
from datetime import UTC, date, datetime

import typer

from stock_agent.application.orchestrator import run_stock_agent
from stock_agent.config import get_settings
from stock_agent.infrastructure.data_connectors.base import FetchRequest
from stock_agent.infrastructure.data_connectors.factory import get_data_connector
from stock_agent.infrastructure.db.session import session_scope
from stock_agent.infrastructure.storage.object_store import get_object_store
from stock_agent.infrastructure.storage.run_repository import RunRepository
from stock_agent.logging import configure_logging, get_logger

app = typer.Typer(help="Stock Agent 操作命令行")


@app.callback()
def _bootstrap() -> None:
    configure_logging()


@app.command("run")
def cmd_run(
    trade_date: str | None = typer.Option(None, help="YYYY-MM-DD；不填则用今天"),
    suffix: str | None = typer.Option(None, help="幂等键"),
) -> None:
    """同步执行一次收盘复盘。"""

    log = get_logger("cli")
    parsed = date.fromisoformat(trade_date) if trade_date else datetime.now(UTC).date()
    connector = get_data_connector()
    market_input = connector.fetch(FetchRequest(trade_date=parsed))
    run = run_stock_agent(market_input, id_suffix=suffix or uuid.uuid4().hex[:8])
    with session_scope() as session:
        RunRepository(session=session, store=get_object_store()).persist(market_input, run, actor="cli")
    log.info("cli.run.done", run_id=run.run_id, status=run.status, candidates=len(run.candidates))
    typer.echo(run.run_id)


@app.command("backfill")
def cmd_backfill(
    start_date: str = typer.Argument(..., help="起始交易日 YYYY-MM-DD"),
    end_date: str = typer.Argument(..., help="结束交易日 YYYY-MM-DD"),
) -> None:
    """按日期区间批量执行（顺序，同步）。生产环境请改用 Celery beat。"""

    from datetime import timedelta

    log = get_logger("cli")
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if end < start:
        raise typer.BadParameter("end_date 必须不早于 start_date")
    current = start
    while current <= end:
        log.info("cli.backfill.day", trade_date=current.isoformat())
        try:
            cmd_run(trade_date=current.isoformat(), suffix=f"backfill-{current.isoformat()}")
        except Exception as exc:
            log.warning("cli.backfill.skip", trade_date=current.isoformat(), error=str(exc))
        current += timedelta(days=1)


@app.command("serve")
def cmd_serve(
    host: str | None = typer.Option(None),
    port: int | None = typer.Option(None),
    reload: bool = typer.Option(False, "--reload"),
) -> None:
    """本地启动 API（生产环境请用 gunicorn/uvicorn 直接跑）。"""

    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "stock_agent.api.app:app",
        host=host or settings.api_host,
        port=port or settings.api_port,
        reload=reload,
        access_log=True,
    )


@app.command("worker")
def cmd_worker() -> None:
    """启动 Celery worker（等价于 celery -A stock_agent.workers.celery_app worker）。"""

    from celery.bin.celery import celery as celery_cli

    sys.argv = [
        "celery",
        "-A",
        "stock_agent.workers.celery_app",
        "worker",
        "-Q",
        "agent,data,report,default",
        "-l",
        "info",
    ]
    celery_cli()


@app.command("scheduler")
def cmd_scheduler() -> None:
    """启动 APScheduler 触发器进程。"""

    from stock_agent.scheduler.main import main

    main()


if __name__ == "__main__":  # pragma: no cover
    app()
