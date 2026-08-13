"""Request-scoped middleware: request ID + structured log context."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from stock_agent.logging import bind_request_context, clear_request_context, get_logger

_log = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        bind_request_context(request_id=request_id, path=request.url.path, method=request.method)
        try:
            response = await call_next(request)
        finally:
            clear_request_context()
        response.headers["x-request-id"] = request_id
        return response
