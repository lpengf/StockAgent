# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

```
backend/     Python service: FastAPI + Celery + APScheduler + SQLAlchemy + boto3
frontend/    Next.js 15 App Router (React 19). All data comes from backend/ via REST.
deploy/      docker-compose.yml + supporting init containers for the full local stack
docs/        Chinese design + requirements documents
```

The Python backend is the source of truth for domain logic, persistence, and scheduling. The frontend is a thin presentation layer.

## Commands

The repo-level [Makefile](Makefile) wraps the common flows:

```bash
make install           # pip install -e '.[dev]'  (from backend/)
make lint              # ruff check (backend)
make typecheck         # mypy strict (backend)
make test              # pytest -m 'not integration'
make test-integration  # full pytest (needs Postgres + MinIO reachable)
make migrate           # alembic upgrade head
make compose-up        # bring up postgres/redis/minio/api/worker/scheduler/web
make compose-down      # tear it down
make docker-build      # build the backend image
```

Direct invocations:

- Backend dev: `cd backend && stock-agent serve --reload`
- Celery worker: `cd backend && stock-agent worker`
- Scheduler: `cd backend && stock-agent scheduler`
- Frontend dev: `cd frontend && NEXT_PUBLIC_API_BASE_URL=http://localhost:8989 npm run dev`

Single-test filter (unit): `cd backend && pytest tests/unit/test_orchestrator.py::test_full_run_produces_snapshot_five_agents_and_report -v`

## Architecture

### Domain pipeline — `backend/src/stock_agent/`

Fixed stage order in [`application/orchestrator.py`](backend/src/stock_agent/application/orchestrator.py):

1. [`domain/quality.py`](backend/src/stock_agent/domain/quality.py) — `validate_input()`. Coverage < `COVERAGE_HARD_THRESHOLD` raises `DataQualityError`; runs at exactly 100% get `PASSED`, otherwise `DEGRADED`.
2. [`domain/features.py`](backend/src/stock_agent/domain/features.py) — `compute_features()` per security (numpy vectorised, deterministic).
3. [`domain/market_review.py`](backend/src/stock_agent/domain/market_review.py) — regime classifier: `TREND_UP` / `RANGE` / `RISK_OFF`.
4. [`domain/selection.py`](backend/src/stock_agent/domain/selection.py) — regime-aware scoring + per-industry diversification.
5. Agents 1-4 run ([`agents/roles.py`](backend/src/stock_agent/agents/roles.py)); the **risk-officer's first conclusion must equal the literal `RISK_GATE_PASS_SENTINEL` = `"无未处理硬否决"`**. Otherwise the orchestrator raises `RiskGateError` and the report agent never runs.
6. Report agent runs; [`application/report.py`](backend/src/stock_agent/application/report.py) renders Markdown. Never recomputes numbers.

Changing any of: agent ordering, the risk-gate sentinel string, or `AgentRoleId` requires updating tests and any downstream consumers of the JSON payload.

### Determinism contract

The whole pipeline is deterministic given the same `MarketInput + id_suffix`. **Never introduce `datetime.now()`, `random`, or wall-clock branches inside `domain/` or `agents/`.** The orchestrator threads `id_suffix` in from the caller (API, CLI, worker) so the IDs (`run-<date>-<suffix>`) are also stable.

Tests in [tests/unit/test_orchestrator.py](backend/tests/unit/test_orchestrator.py) rely on this — the "same input, same output" test is a regression guard.

### Persistence — `backend/src/stock_agent/infrastructure/`

- [`db/models.py`](backend/src/stock_agent/infrastructure/db/models.py) — SQLAlchemy 2.x models. Score/confidence stored as basis-points integers (`* 100` and `* 10_000`) to avoid float rounding.
- [`db/session.py`](backend/src/stock_agent/infrastructure/db/session.py) — single engine per process.
- [`storage/object_store.py`](backend/src/stock_agent/infrastructure/storage/object_store.py) — S3-compatible (works against AWS S3 and MinIO). Retries with exponential backoff.
- [`storage/run_repository.py`](backend/src/stock_agent/infrastructure/storage/run_repository.py) — writes three objects per run (raw snapshot, decision JSON, Markdown report) **before** committing the DB transaction, so on crash we may leak an object (small cost, easy to GC) but never end up with a DB row pointing at a missing object.
- [`data_connectors/`](backend/src/stock_agent/infrastructure/data_connectors/) — `DemoConnector` (byte-for-byte parity with the retired TypeScript reference) + `AkshareConnector` (rate-limited, retrying). Selected via `DATA_CONNECTOR` env var.

Schema changes require: update the ORM model, add an Alembic revision in [`alembic/versions/`](backend/alembic/versions/), update `run_repository.py` and the API schema in [`api/schemas.py`](backend/src/stock_agent/api/schemas.py). No runtime `CREATE TABLE IF NOT EXISTS` — Alembic is the sole DDL source.

### API surface — `backend/src/stock_agent/api/`

- `GET /livez` / `GET /readyz` — orchestrator probes (unauthenticated).
- `GET /api/runs` — recent runs (JWT required).
- `GET /api/runs/{run_id}` — full detail incl. Markdown + agents + candidates (JWT required).
- `POST /api/runs` — trigger a run. **admin only** (`X-Admin-Key` or JWT with `role=admin`). Body: `CreateRunRequest`.
- `GET /metrics` — Prometheus scrape endpoint.

Auth precedence in [`api/security.py`](backend/src/stock_agent/api/security.py): `X-Admin-Key` header wins over `Authorization: Bearer`. Rate limit is per-IP via SlowAPI, tuned by `RATE_LIMIT_PER_MINUTE`. Every request gets a `X-Request-Id` echoed back and bound into structured logs.

Errors go through the `StockAgentError` hierarchy in [`errors.py`](backend/src/stock_agent/errors.py); each subclass carries an HTTP status + stable error code. The FastAPI exception handler in [`api/app.py`](backend/src/stock_agent/api/app.py) is the single place that serialises them.

### Workers + scheduler

- Celery config in [`workers/celery_app.py`](backend/src/stock_agent/workers/celery_app.py) declares three queues (`agent`, `data`, `report`). `task_acks_late=True` + `worker_prefetch_multiplier=1` — DO NOT change without understanding the retry-on-loss guarantees this gives.
- [`workers/tasks.py::run_daily_screening`](backend/src/stock_agent/workers/tasks.py) is the ONLY entry from scheduled runs. It shares the same orchestrator path as the sync API — one code path, always.
- [`scheduler/main.py`](backend/src/stock_agent/scheduler/main.py) is a thin APScheduler process that enqueues the task at `SCHEDULER_RUN_CRON`. Keep it dumb — never do heavy work here.

## Conventions

- Domain vocabulary and user-facing strings are Chinese by design (角色 / 候选 / 硬风控 / 复盘). Don't translate them to English.
- `mypy strict` is on. New code must be fully typed. `Any` is the exception, not the rule.
- Numeric confidence/score persistence uses integer basis points — remember to `* 10_000` (confidence) or `* 100` (score) when writing and divide when reading.
- Pydantic domain models are `frozen=True` — copy with `.model_copy(update=...)` rather than mutating.
- Test markers: `@pytest.mark.integration` gates any test that touches Postgres/MinIO. Unit tests default to fast + pure.
- The disclaimer `不构成投资建议` is asserted in [tests/unit/test_report.py](backend/tests/unit/test_report.py) — don't drop it from the report.

## Frontend

Thin React 19 layer in [`frontend/`](frontend/). All server data goes through the typed client in [`lib/api/client.ts`](frontend/lib/api/client.ts). Types in [`lib/api/types.ts`](frontend/lib/api/types.ts) mirror the Pydantic response schemas — regenerate when the API changes.

- Browser calls hit `/api/backend/*`, rewritten by [`next.config.ts`](frontend/next.config.ts) to `${NEXT_PUBLIC_API_BASE_URL}/api/*`.
- Server components read directly via `API_BASE_URL` (defaults to the docker-compose service name in production).
- The admin key is entered by the user in the UI (dev-only convenience) — production should replace with a real JWT flow.

## Local full stack

```bash
make compose-up
# API:   http://localhost:8989/docs
# Web:   http://localhost:3000
# MinIO: http://localhost:9001  (minioadmin / minioadmin)
# Postgres: localhost:5432       (stock / stock)
```

The `migrator` service runs `alembic upgrade head` once and exits; `api`, `worker`, `scheduler`, and `web` all wait for it.
