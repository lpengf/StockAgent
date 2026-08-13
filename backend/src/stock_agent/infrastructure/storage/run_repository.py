"""Repository persisting a full `StockAgentRun` to Postgres + object storage.

Object-storage writes happen before the DB transaction commits so that on
crash we may leak an object (small cost, easy to garbage-collect) but never
end up with a DB row pointing at a missing object.
"""

from __future__ import annotations

from datetime import UTC, datetime

import orjson
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from stock_agent.config import get_settings
from stock_agent.domain.types import MarketInput, StockAgentRun
from stock_agent.errors import NotFoundError
from stock_agent.infrastructure.db.models import (
    AgentRun,
    AuditLog,
    CandidateRow,
    DataSnapshot,
    Report,
    ScreeningRun,
)
from stock_agent.infrastructure.storage.object_store import ObjectStore
from stock_agent.logging import get_logger

_log = get_logger(__name__)


def _pydantic_dump(model: object) -> object:
    return orjson.loads(orjson.dumps(model, default=str, option=orjson.OPT_NON_STR_KEYS))


def _now() -> datetime:
    return datetime.now(UTC)


class RunRepository:
    def __init__(self, session: Session, store: ObjectStore) -> None:
        self._session = session
        self._store = store
        self._settings = get_settings()

    def persist(self, market_input: MarketInput, run: StockAgentRun, actor: str = "system") -> None:
        created_at = _now()
        snapshot_key = f"raw/market={market_input.market}/trade_date={run.trade_date}/snapshot_id={run.snapshot_id}/snapshot.json"
        report_key = f"report/trade_date={run.trade_date}/run_id={run.run_id}/report.md"
        run_key = f"decision/trade_date={run.trade_date}/run_id={run.run_id}/run.json"

        snapshot_body = orjson.dumps(
            {
                "schema_version": "snapshot/1.0",
                "input": _pydantic_dump(market_input.model_dump(mode="json")),
                "run": {"run_id": run.run_id, "data_quality": _pydantic_dump(run.data_quality.model_dump(mode="json"))},
            }
        )
        put_snapshot = self._store.put_bytes(
            snapshot_key,
            snapshot_body,
            content_type="application/json; charset=utf-8",
            metadata={"snapshot_id": run.snapshot_id},
        )
        self._store.put_bytes(
            report_key,
            run.report_markdown.encode("utf-8"),
            content_type="text/markdown; charset=utf-8",
        )
        self._store.put_bytes(
            run_key,
            orjson.dumps(_pydantic_dump(run.model_dump(mode="json"))),
            content_type="application/json; charset=utf-8",
        )

        # Snapshot metadata (idempotent upsert on primary key).
        snapshot_stmt = pg_insert(DataSnapshot).values(
            id=run.snapshot_id,
            market=market_input.market,
            trade_date=run.trade_date,
            as_of_time=run.as_of_time,
            status="PUBLISHED",
            object_key=put_snapshot.key,
            checksum=put_snapshot.checksum,
            record_count=len(market_input.securities),
            created_at=created_at,
        )
        self._session.execute(
            snapshot_stmt.on_conflict_do_update(
                index_elements=[DataSnapshot.id],
                set_={
                    "status": snapshot_stmt.excluded.status,
                    "object_key": snapshot_stmt.excluded.object_key,
                    "checksum": snapshot_stmt.excluded.checksum,
                    "record_count": snapshot_stmt.excluded.record_count,
                },
            )
        )

        run_stmt = pg_insert(ScreeningRun).values(
            id=run.run_id,
            snapshot_id=run.snapshot_id,
            trade_date=run.trade_date,
            strategy_version=run.strategy_version,
            status=run.status,
            market_regime=run.market_review.regime,
            summary=run.market_review.summary,
            market_review_json=_pydantic_dump(run.market_review.model_dump(mode="json")),
            data_quality_json=_pydantic_dump(run.data_quality.model_dump(mode="json")),
            rejected_count=run.rejected_count,
            created_at=created_at,
            completed_at=created_at,
        )
        self._session.execute(
            run_stmt.on_conflict_do_update(
                index_elements=[ScreeningRun.id],
                set_={
                    "status": run_stmt.excluded.status,
                    "market_regime": run_stmt.excluded.market_regime,
                    "summary": run_stmt.excluded.summary,
                    "market_review_json": run_stmt.excluded.market_review_json,
                    "data_quality_json": run_stmt.excluded.data_quality_json,
                    "rejected_count": run_stmt.excluded.rejected_count,
                    "completed_at": run_stmt.excluded.completed_at,
                },
            )
        )

        # Idempotent per-agent rows.
        self._session.query(AgentRun).filter(AgentRun.run_id == run.run_id).delete()
        for agent in run.agents:
            self._session.add(
                AgentRun(
                    id=f"{run.run_id}:{agent.role_id}",
                    run_id=run.run_id,
                    role_id=agent.role_id,
                    role_version=agent.role_version,
                    status=agent.status,
                    confidence_bps=round(agent.confidence * 10_000),
                    result_json=_pydantic_dump(agent.model_dump(mode="json")),
                    created_at=created_at,
                )
            )

        self._session.query(CandidateRow).filter(CandidateRow.run_id == run.run_id).delete()
        for candidate in run.candidates:
            self._session.add(
                CandidateRow(
                    id=f"{run.run_id}:{candidate.security_id}",
                    run_id=run.run_id,
                    security_id=candidate.security_id,
                    name=candidate.name,
                    industry=candidate.industry,
                    tier=candidate.tier,
                    score_bps=round(candidate.score * 100),
                    confidence_bps=round(candidate.confidence * 10_000),
                    reasons_json=list(candidate.reasons),
                    risks_json=list(candidate.risks),
                    created_at=created_at,
                )
            )

        report_stmt = pg_insert(Report).values(
            id=run.report_id,
            run_id=run.run_id,
            trade_date=run.trade_date,
            title=f"{run.trade_date.isoformat()} A 股复盘",
            object_key=report_key,
            markdown=run.report_markdown,
            created_at=created_at,
        )
        self._session.execute(
            report_stmt.on_conflict_do_update(
                index_elements=[Report.id],
                set_={
                    "markdown": report_stmt.excluded.markdown,
                    "object_key": report_stmt.excluded.object_key,
                },
            )
        )

        self._session.add(
            AuditLog(
                actor=actor,
                action="run.persist",
                entity_type="run",
                entity_id=run.run_id,
                payload={
                    "snapshot_id": run.snapshot_id,
                    "status": run.status,
                    "candidates": len(run.candidates),
                },
                created_at=created_at,
            )
        )
        _log.info(
            "run_repository.persist",
            run_id=run.run_id,
            snapshot_id=run.snapshot_id,
            candidates=len(run.candidates),
        )

    def list_recent(self, limit: int = 30) -> list[dict[str, object]]:
        result = self._session.execute(
            select(ScreeningRun).order_by(ScreeningRun.created_at.desc()).limit(limit)
        )
        rows = []
        for (row,) in result.all():
            rows.append(
                {
                    "run_id": row.id,
                    "snapshot_id": row.snapshot_id,
                    "trade_date": row.trade_date.isoformat(),
                    "strategy_version": row.strategy_version,
                    "status": row.status,
                    "market_regime": row.market_regime,
                    "summary": row.summary,
                    "created_at": row.created_at.isoformat(),
                }
            )
        return rows

    def load_run_detail(self, run_id: str) -> dict[str, object]:
        run_row = self._session.get(ScreeningRun, run_id)
        if run_row is None:
            raise NotFoundError(f"未找到运行 {run_id}", details={"run_id": run_id})
        report_row = self._session.execute(
            select(Report).where(Report.run_id == run_id).limit(1)
        ).scalar_one_or_none()
        agent_rows = self._session.execute(
            select(AgentRun).where(AgentRun.run_id == run_id).order_by(AgentRun.role_id)
        ).scalars().all()
        candidate_rows = self._session.execute(
            select(CandidateRow).where(CandidateRow.run_id == run_id).order_by(CandidateRow.score_bps.desc())
        ).scalars().all()
        return {
            "run_id": run_row.id,
            "snapshot_id": run_row.snapshot_id,
            "trade_date": run_row.trade_date.isoformat(),
            "strategy_version": run_row.strategy_version,
            "status": run_row.status,
            "market_regime": run_row.market_regime,
            "summary": run_row.summary,
            "market_review": run_row.market_review_json,
            "data_quality": run_row.data_quality_json,
            "rejected_count": run_row.rejected_count,
            "created_at": run_row.created_at.isoformat(),
            "completed_at": run_row.completed_at.isoformat(),
            "report": {
                "id": report_row.id if report_row else None,
                "markdown": report_row.markdown if report_row else None,
                "object_key": report_row.object_key if report_row else None,
            },
            "agents": [row.result_json for row in agent_rows],
            "candidates": [
                {
                    "security_id": row.security_id,
                    "name": row.name,
                    "industry": row.industry,
                    "tier": row.tier,
                    "score": row.score_bps / 100,
                    "confidence": row.confidence_bps / 10_000,
                    "reasons": row.reasons_json,
                    "risks": row.risks_json,
                }
                for row in candidate_rows
            ],
        }
