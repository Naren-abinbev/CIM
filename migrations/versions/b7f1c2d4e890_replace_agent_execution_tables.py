"""Replace agent execution and fallback tables with one execution log.

Revision ID: b7f1c2d4e890
Revises: 8c2d7e4a1b90
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7f1c2d4e890"
down_revision: Union[str, Sequence[str], None] = "8c2d7e4a1b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Copy existing execution data into the consolidated log table."""
    bind = op.get_bind()
    metadata = sa.MetaData()

    executions = sa.Table(
        "agent_execution",
        metadata,
        sa.Column("execution_id", sa.String(length=36)),
        sa.Column("incident_id", sa.String(length=36)),
        sa.Column("agent_name", sa.String(length=150)),
        sa.Column("model_name", sa.String(length=150)),
        sa.Column("model_type", sa.String(length=50)),
        sa.Column("execution_status", sa.String(length=50)),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("total_tokens", sa.Integer()),
        sa.Column("latency_ms", sa.BigInteger()),
        sa.Column("retry_count", sa.Integer()),
        sa.Column("confidence_score", sa.Numeric(5, 4)),
        sa.Column("evaluation_score", sa.Numeric(5, 4)),
        sa.Column("judge_score", sa.Numeric(5, 4)),
        sa.Column("reasoning_summary", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    fallbacks = sa.Table(
        "model_fallback",
        metadata,
        sa.Column("model_execution_id", sa.String(length=36)),
        sa.Column("execution_id", sa.String(length=36)),
        sa.Column("model_name", sa.String(length=150)),
        sa.Column("fallback_level", sa.String(length=30)),
        sa.Column("success", sa.Boolean()),
        sa.Column("latency_ms", sa.BigInteger()),
        sa.Column("token_count", sa.Integer()),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    execution_rows = bind.execute(sa.select(executions)).mappings().all()
    fallback_rows = bind.execute(sa.select(fallbacks)).mappings().all()

    fallbacks_by_execution: dict[str, list[dict]] = {}
    for row in fallback_rows:
        fallbacks_by_execution.setdefault(row["execution_id"], []).append(
            {
                "model_execution_id": row["model_execution_id"],
                "model_name": row["model_name"],
                "fallback_level": row["fallback_level"],
                "success": row["success"],
                "latency_ms": row["latency_ms"],
                "token_count": row["token_count"],
                "failure_reason": row["failure_reason"],
                "created_at": row["created_at"].isoformat()
                if isinstance(row["created_at"], datetime)
                else row["created_at"],
            }
        )

    op.create_table(
        "agent_execution_log",
        sa.Column("agent_execution_id", sa.String(length=36), nullable=False),
        sa.Column("incident_id", sa.String(length=36), nullable=False),
        sa.Column("agent_name", sa.String(length=150), nullable=False),
        sa.Column("model_name", sa.String(length=150), nullable=False),
        sa.Column("model_type", sa.String(length=50), nullable=False),
        sa.Column("fallback_level", sa.String(length=30), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("fallback_count", sa.Integer(), nullable=False),
        sa.Column("execution_status", sa.String(length=50), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.BigInteger(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("evaluation_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("judge_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("execution_history", sa.JSON(), nullable=True),
        sa.Column("reasoning_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incident_master.incident_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("agent_execution_id"),
    )

    new_table = sa.table(
        "agent_execution_log",
        sa.column("agent_execution_id", sa.String(length=36)),
        sa.column("incident_id", sa.String(length=36)),
        sa.column("agent_name", sa.String(length=150)),
        sa.column("model_name", sa.String(length=150)),
        sa.column("model_type", sa.String(length=50)),
        sa.column("fallback_level", sa.String(length=30)),
        sa.column("fallback_used", sa.Boolean()),
        sa.column("fallback_count", sa.Integer()),
        sa.column("execution_status", sa.String(length=50)),
        sa.column("input_tokens", sa.Integer()),
        sa.column("output_tokens", sa.Integer()),
        sa.column("total_tokens", sa.Integer()),
        sa.column("latency_ms", sa.BigInteger()),
        sa.column("retry_count", sa.Integer()),
        sa.column("confidence_score", sa.Numeric(5, 4)),
        sa.column("evaluation_score", sa.Numeric(5, 4)),
        sa.column("judge_score", sa.Numeric(5, 4)),
        sa.column("execution_history", sa.JSON()),
        sa.column("reasoning_summary", sa.Text()),
        sa.column("error_message", sa.Text()),
        sa.column("started_at", sa.DateTime(timezone=True)),
        sa.column("completed_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    migrated = []
    for row in execution_rows:
        history = fallbacks_by_execution.get(row["execution_id"], [])
        latest_fallback = history[-1] if history else None
        migrated.append(
            {
                "agent_execution_id": row["execution_id"],
                "incident_id": row["incident_id"],
                "agent_name": row["agent_name"],
                "model_name": latest_fallback["model_name"]
                if latest_fallback
                else row["model_name"],
                "model_type": row["model_type"],
                "fallback_level": latest_fallback["fallback_level"]
                if latest_fallback
                else "primary",
                "fallback_used": bool(history),
                "fallback_count": len(history),
                "execution_status": row["execution_status"],
                "input_tokens": row["input_tokens"],
                "output_tokens": row["output_tokens"],
                "total_tokens": row["total_tokens"],
                "latency_ms": row["latency_ms"],
                "retry_count": row["retry_count"] or 0,
                "confidence_score": row["confidence_score"],
                "evaluation_score": row["evaluation_score"],
                "judge_score": row["judge_score"],
                "execution_history": history or None,
                "reasoning_summary": row["reasoning_summary"],
                "error_message": row["error_message"],
                "started_at": None,
                "completed_at": None,
                "created_at": row["created_at"],
            }
        )

    if migrated:
        op.bulk_insert(new_table, migrated)

    op.create_index(
        "ix_agent_execution_log_incident_id",
        "agent_execution_log",
        ["incident_id"],
    )

    op.drop_index("ix_model_fallback_execution_id", table_name="model_fallback")
    op.drop_table("model_fallback")
    op.drop_index("ix_agent_execution_incident_id", table_name="agent_execution")
    op.drop_table("agent_execution")


def downgrade() -> None:
    """Restore the old tables from the consolidated log."""
    # The old two-table structure is retained for rollback compatibility.
    # Execution-history entries are restored as model-fallback rows where
    # possible; the consolidated-only fields are not present in the old schema.
    bind = op.get_bind()
    metadata = sa.MetaData()
    logs = sa.Table(
        "agent_execution_log",
        metadata,
        sa.Column("agent_execution_id", sa.String(length=36)),
        sa.Column("incident_id", sa.String(length=36)),
        sa.Column("agent_name", sa.String(length=150)),
        sa.Column("model_name", sa.String(length=150)),
        sa.Column("model_type", sa.String(length=50)),
        sa.Column("execution_status", sa.String(length=50)),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("total_tokens", sa.Integer()),
        sa.Column("latency_ms", sa.BigInteger()),
        sa.Column("retry_count", sa.Integer()),
        sa.Column("confidence_score", sa.Numeric(5, 4)),
        sa.Column("evaluation_score", sa.Numeric(5, 4)),
        sa.Column("judge_score", sa.Numeric(5, 4)),
        sa.Column("reasoning_summary", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("execution_history", sa.JSON()),
    )
    rows = bind.execute(sa.select(logs)).mappings().all()

    op.create_table(
        "agent_execution",
        sa.Column("execution_id", sa.String(length=36), nullable=False),
        sa.Column("incident_id", sa.String(length=36), nullable=False),
        sa.Column("agent_name", sa.String(length=150), nullable=False),
        sa.Column("model_name", sa.String(length=150), nullable=False),
        sa.Column("model_type", sa.String(length=50), nullable=False),
        sa.Column("execution_status", sa.String(length=50), nullable=False),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("total_tokens", sa.Integer()),
        sa.Column("latency_ms", sa.BigInteger()),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 4)),
        sa.Column("evaluation_score", sa.Numeric(5, 4)),
        sa.Column("judge_score", sa.Numeric(5, 4)),
        sa.Column("reasoning_summary", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incident_master.incident_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("execution_id"),
    )
    old_execution = sa.table(
        "agent_execution",
        sa.column("execution_id", sa.String(length=36)),
        sa.column("incident_id", sa.String(length=36)),
        sa.column("agent_name", sa.String(length=150)),
        sa.column("model_name", sa.String(length=150)),
        sa.column("model_type", sa.String(length=50)),
        sa.column("execution_status", sa.String(length=50)),
        sa.column("input_tokens", sa.Integer()),
        sa.column("output_tokens", sa.Integer()),
        sa.column("total_tokens", sa.Integer()),
        sa.column("latency_ms", sa.BigInteger()),
        sa.column("retry_count", sa.Integer()),
        sa.column("confidence_score", sa.Numeric(5, 4)),
        sa.column("evaluation_score", sa.Numeric(5, 4)),
        sa.column("judge_score", sa.Numeric(5, 4)),
        sa.column("reasoning_summary", sa.Text()),
        sa.column("error_message", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    if rows:
        op.bulk_insert(
            old_execution,
            [
                {
                    key: row[key]
                    for key in (
                        "execution_id",
                        "incident_id",
                        "agent_name",
                        "model_name",
                        "model_type",
                        "execution_status",
                        "input_tokens",
                        "output_tokens",
                        "total_tokens",
                        "latency_ms",
                        "retry_count",
                        "confidence_score",
                        "evaluation_score",
                        "judge_score",
                        "reasoning_summary",
                        "error_message",
                        "created_at",
                    )
                }
                for row in rows
            ],
        )

    op.create_index("ix_agent_execution_incident_id", "agent_execution", ["incident_id"])

    op.create_table(
        "model_fallback",
        sa.Column("model_execution_id", sa.String(length=36), nullable=False),
        sa.Column("execution_id", sa.String(length=36), nullable=False),
        sa.Column("model_name", sa.String(length=150), nullable=False),
        sa.Column("fallback_level", sa.String(length=30), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.BigInteger()),
        sa.Column("token_count", sa.Integer()),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["execution_id"], ["agent_execution.execution_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("model_execution_id"),
    )
    op.create_index("ix_model_fallback_execution_id", "model_fallback", ["execution_id"])
    op.drop_index("ix_agent_execution_log_incident_id", table_name="agent_execution_log")
    op.drop_table("agent_execution_log")
