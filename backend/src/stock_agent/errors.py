"""Typed domain errors mapped to stable API error codes.

Do not raise these outside of application/domain code; infrastructure adapters
should wrap third-party exceptions into one of these.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class StockAgentError(Exception):
    code: str = "STOCK_AGENT_ERROR"
    http_status: int = 500

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(StockAgentError):
    code = "VALIDATION_ERROR"
    http_status = 422


class DataQualityError(StockAgentError):
    code = "DATA_QUALITY_ERROR"
    http_status = 422


class RiskGateError(StockAgentError):
    code = "RISK_GATE_FAILED"
    http_status = 409


class NotFoundError(StockAgentError):
    code = "NOT_FOUND"
    http_status = 404


class ConflictError(StockAgentError):
    code = "CONFLICT"
    http_status = 409


class ExternalServiceError(StockAgentError):
    code = "EXTERNAL_SERVICE_ERROR"
    http_status = 503


class UnauthorizedError(StockAgentError):
    code = "UNAUTHORIZED"
    http_status = 401


class ForbiddenError(StockAgentError):
    code = "FORBIDDEN"
    http_status = 403


@dataclass(slots=True)
class ErrorEnvelope:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}
