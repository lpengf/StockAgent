# Stock Agent — Python backend

Production-oriented rewrite of the A-share close-of-day research agent.

## Run locally

```bash
uv venv && source .venv/bin/activate    # or: python -m venv .venv
uv pip install -e '.[dev]'              # or: pip install -e '.[dev]'
stock-agent serve --reload              # local API on http://localhost:8989/docs
```

Full stack (Postgres + MinIO + Redis + API + worker + scheduler) is available
via `docker compose up` from the repo root.

## CLI

```
stock-agent run                # trigger a screening run synchronously
stock-agent backfill 2026-08-01 2026-08-11
stock-agent worker             # celery worker
stock-agent scheduler          # APScheduler trigger
```

## Tests

```
pytest -m 'not integration'   # fast unit + determinism suite
pytest                        # full suite (needs Postgres + MinIO)
```
