"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from stock_agent import __version__
from stock_agent.api.middleware import RequestContextMiddleware
from stock_agent.api.routes import health as health_routes
from stock_agent.api.routes import runs as runs_routes
from stock_agent.config import get_settings
from stock_agent.errors import ErrorEnvelope, StockAgentError
from stock_agent.logging import configure_logging, get_logger


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    logger = get_logger(__name__)

    limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_minute}/minute"])
    app = FastAPI(
        title="Stock Agent API",
        version=__version__,
        root_path=settings.api_root_path,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.limiter = limiter

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Admin-Key", "X-Request-Id"],
        expose_headers=["X-Request-Id"],
    )

    @app.exception_handler(StockAgentError)
    async def _handle_domain_error(_request: Request, exc: StockAgentError) -> JSONResponse:
        logger.warning("api.domain_error", code=exc.code, message=exc.message, details=exc.details)
        envelope = ErrorEnvelope(code=exc.code, message=exc.message, details=exc.details)
        return JSONResponse(status_code=exc.http_status, content=envelope.as_dict())

    @app.exception_handler(RateLimitExceeded)
    async def _handle_rate_limit(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
        envelope = ErrorEnvelope(code="RATE_LIMITED", message=str(exc.detail))
        return JSONResponse(status_code=429, content=envelope.as_dict())

    @app.exception_handler(Exception)
    async def _handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("api.unhandled_error", error=str(exc))
        envelope = ErrorEnvelope(code="INTERNAL_ERROR", message="服务器内部错误")
        return JSONResponse(status_code=500, content=envelope.as_dict())

    app.include_router(health_routes.router)
    app.include_router(runs_routes.router)

    if settings.prometheus_enabled:
        app.mount("/metrics", make_asgi_app())

    logger.info("api.started", env=settings.env, version=__version__)
    return app


app = create_app()
