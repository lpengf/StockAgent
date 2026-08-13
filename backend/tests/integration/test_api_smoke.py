"""API smoke test that mounts the FastAPI app in memory.

Uses moto for S3 so no MinIO/AWS is required. Marks itself `integration` so
`pytest -m 'not integration'` in CI can skip it when infra is unavailable.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_livez_ok() -> None:
    from fastapi.testclient import TestClient

    from stock_agent.api.app import create_app

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/livez")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
