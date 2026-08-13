"""Prometheus metrics. Registered against the default global registry so
`prometheus_client.make_asgi_app()` can expose them from the FastAPI app.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

RUNS_STARTED = Counter(
    "stock_agent_runs_started_total",
    "Number of screening runs started",
    labelnames=("connector",),
)
RUNS_SUCCEEDED = Counter(
    "stock_agent_runs_succeeded_total",
    "Number of screening runs that completed successfully",
    labelnames=("connector", "status"),
)
RUNS_FAILED = Counter(
    "stock_agent_runs_failed_total",
    "Number of screening runs that failed",
    labelnames=("connector", "error_code"),
)
RUN_DURATION_SECONDS = Histogram(
    "stock_agent_run_duration_seconds",
    "Screening run wall-clock duration",
    labelnames=("connector",),
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)
