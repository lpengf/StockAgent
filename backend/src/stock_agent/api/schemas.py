"""Pydantic v2 request/response schemas.

Keeping API schemas separate from domain models so the wire format can evolve
independently — never expose ORM rows directly to the client.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ApiModel(BaseModel):
    model_config = {"populate_by_name": True}


class RunSummary(ApiModel):
    run_id: str
    snapshot_id: str
    trade_date: str
    strategy_version: str
    status: str
    market_regime: str
    summary: str
    created_at: str


class RunListResponse(ApiModel):
    items: list[RunSummary]


class ErrorPayload(ApiModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorResponse(ApiModel):
    error: ErrorPayload


class CreateRunRequest(ApiModel):
    trade_date: date | None = Field(default=None, description="留空则使用连接器的默认交易日")
    connector: str | None = Field(default=None, description="覆盖默认连接器；未提供则读取配置")
    id_suffix: str | None = Field(default=None, description="幂等键，重复请求会重放同一个 run_id")


class CreateRunResponse(ApiModel):
    run_id: str
    snapshot_id: str
    report_id: str
    trade_date: date
    as_of_time: datetime
    status: str
    strategy_version: str
    candidates: int
    rejected: int


class RunDetailResponse(ApiModel):
    run_id: str
    snapshot_id: str
    trade_date: str
    strategy_version: str
    status: str
    market_regime: str
    summary: str
    market_review: dict
    data_quality: dict
    rejected_count: int
    created_at: str
    completed_at: str
    report: dict
    agents: list[dict]
    candidates: list[dict]


class HealthResponse(ApiModel):
    status: str
    version: str
    checks: dict[str, str]
