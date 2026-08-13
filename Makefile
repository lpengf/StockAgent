# Repo-level convenience wrappers.
# Every recipe is safe to run without side effects beyond its stated purpose.

.PHONY: help install lint test test-integration typecheck migrate run compose-up compose-down docker-build

help:
	@echo "Available targets:"
	@echo "  install           - Install backend package + dev extras (editable)"
	@echo "  lint              - Ruff lint on backend/"
	@echo "  typecheck         - mypy on backend/"
	@echo "  test              - Unit tests (skip integration)"
	@echo "  test-integration  - Full pytest suite (needs Postgres/MinIO)"
	@echo "  migrate           - Run alembic upgrade head"
	@echo "  compose-up        - Bring up the full local stack"
	@echo "  compose-down      - Tear the local stack down"
	@echo "  docker-build      - Build the backend image"

install:
	cd backend && pip install -e '.[dev]'

lint:
	cd backend && ruff check .

typecheck:
	cd backend && mypy src

test:
	cd backend && pytest -m 'not integration'

test-integration:
	cd backend && pytest

migrate:
	cd backend && alembic upgrade head

compose-up:
	cd deploy && docker compose up -d --build

compose-down:
	cd deploy && docker compose down -v

docker-build:
	cd backend && docker build -t stock-agent-backend:local .
