"""Immutable domain models. Pydantic v2 with frozen=True for value semantics."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MarketRegime = Literal["TREND_UP", "RANGE", "RISK_OFF"]
RunStatus = Literal["SUCCEEDED", "DEGRADED_SUCCEEDED", "FAILED"]
CandidateTier = Literal["FOCUS", "WATCH"]
RiskSeverity = Literal["HARD_VETO", "WARNING"]
AgentRoleId = Literal["coordinator", "market_analyst", "quant_analyst", "risk_officer", "report_writer"]
EvidenceType = Literal["METRIC", "RULE", "DATA_QUALITY"]
DataQualityStatus = Literal["PASSED", "DEGRADED"]
Market = Literal["CN_A"]


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True, str_strip_whitespace=True)


class DailyBar(DomainModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float


class SecuritySeries(DomainModel):
    security_id: str
    name: str
    industry: str
    listed_days: int
    is_st: bool
    is_suspended: bool
    bars: tuple[DailyBar, ...]
    roe: float
    revenue_growth: float
    debt_ratio: float
    event_risk: str | None = None


class MarketInput(DomainModel):
    market: Market
    trade_date: date
    as_of_time: datetime
    securities: tuple[SecuritySeries, ...]


class SecurityFeatures(DomainModel):
    security_id: str
    name: str
    industry: str
    close: float
    return_5d: float
    return_20d: float
    volume_ratio_5d: float
    volatility_20d: float
    max_drawdown_20d: float
    liquidity_score: float
    fundamental_score: float
    trend_score: float
    raw_score: float


class RiskDecision(DomainModel):
    rule_id: str
    severity: RiskSeverity
    passed: bool
    message: str


class Candidate(DomainModel):
    id: str
    security_id: str
    name: str
    industry: str
    close: float
    score: float
    confidence: float
    tier: CandidateTier
    reasons: tuple[str, ...]
    risks: tuple[str, ...]
    observation: str
    features: SecurityFeatures
    risk_decisions: tuple[RiskDecision, ...]


class Evidence(DomainModel):
    id: str
    type: EvidenceType
    label: str
    value: str
    as_of_time: datetime


class AgentResult(DomainModel):
    id: str
    role_id: AgentRoleId
    role_label: str
    role_version: Literal["1.0.0"] = "1.0.0"
    status: Literal["SUCCEEDED", "DEGRADED", "FAILED"] = "SUCCEEDED"
    confidence: float
    summary: str
    conclusions: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    risks: tuple[str, ...] = ()
    duration_ms: int


class IndustryChange(DomainModel):
    name: str
    change: float


class MarketReview(DomainModel):
    regime: MarketRegime
    index_change: float
    advance_ratio: float
    total_amount: float
    volume_change: float
    leading_industries: tuple[IndustryChange, ...]
    summary: str


class DataQuality(DomainModel):
    status: DataQualityStatus
    coverage: float
    checks: tuple[str, ...]


class StockAgentRun(DomainModel):
    run_id: str
    snapshot_id: str
    report_id: str
    trade_date: date
    as_of_time: datetime
    strategy_version: str = Field(default="mvp-1.0.0")
    status: RunStatus
    data_quality: DataQuality
    market_review: MarketReview
    candidates: tuple[Candidate, ...]
    rejected_count: int
    agents: tuple[AgentResult, ...]
    report_markdown: str
