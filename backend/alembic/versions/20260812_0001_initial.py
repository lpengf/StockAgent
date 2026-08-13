"""Initial schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "data_snapshots",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("market", sa.String(16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("as_of_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_snapshots_trade_date", "data_snapshots", ["market", "trade_date"])

    op.create_table(
        "screening_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("snapshot_id", sa.String(64), sa.ForeignKey("data_snapshots.id"), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("strategy_version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("market_regime", sa.String(16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("market_review_json", postgresql.JSONB(), nullable=False),
        sa.Column("data_quality_json", postgresql.JSONB(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_runs_trade_date", "screening_runs", ["trade_date", "created_at"])

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("screening_runs.id"), nullable=False),
        sa.Column("role_id", sa.String(32), nullable=False),
        sa.Column("role_version", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("confidence_bps", sa.Integer(), nullable=False),
        sa.Column("result_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_agents_run_id", "agent_runs", ["run_id", "role_id"])

    op.create_table(
        "candidates",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("screening_runs.id"), nullable=False),
        sa.Column("security_id", sa.String(32), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("industry", sa.String(64), nullable=False),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("score_bps", sa.BigInteger(), nullable=False),
        sa.Column("confidence_bps", sa.Integer(), nullable=False),
        sa.Column("reasons_json", postgresql.JSONB(), nullable=False),
        sa.Column("risks_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_candidates_run_id", "candidates", ["run_id", "tier", "score_bps"])

    op.create_table(
        "reports",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("screening_runs.id"), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_reports_trade_date", "reports", ["trade_date", "created_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_audit_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("idx_audit_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_audit_created_at", table_name="audit_logs")
    op.drop_index("idx_audit_entity", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("idx_reports_trade_date", table_name="reports")
    op.drop_table("reports")
    op.drop_index("idx_candidates_run_id", table_name="candidates")
    op.drop_table("candidates")
    op.drop_index("idx_agents_run_id", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("idx_runs_trade_date", table_name="screening_runs")
    op.drop_table("screening_runs")
    op.drop_index("idx_snapshots_trade_date", table_name="data_snapshots")
    op.drop_table("data_snapshots")
