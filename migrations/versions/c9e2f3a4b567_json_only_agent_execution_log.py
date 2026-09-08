"""Keep agent execution details only in a JSON history list.

Revision ID: c9e2f3a4b567
Revises: b7f1c2d4e890
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9e2f3a4b567"
down_revision: Union[str, Sequence[str], None] = "b7f1c2d4e890"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    old = sa.Table("agent_execution_log", metadata, autoload_with=bind)
    rows = bind.execute(sa.select(old)).mappings().all()

    op.create_table(
        "agent_execution_log_new",
        sa.Column("agent_execution_id", sa.String(36), nullable=False),
        sa.Column("incident_id", sa.String(36), nullable=False),
        sa.Column("agent_name", sa.String(150), nullable=False),
        sa.Column("execution_history", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incident_master.incident_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("agent_execution_id"),
        sa.UniqueConstraint(
            "incident_id",
            "agent_name",
            name="uq_agent_execution_log_incident_agent",
        ),
    )

    new = sa.table(
        "agent_execution_log_new",
        sa.column("agent_execution_id", sa.String(36)),
        sa.column("incident_id", sa.String(36)),
        sa.column("agent_name", sa.String(150)),
        sa.column("execution_history", sa.JSON()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    migrated = []
    for row in rows:
        history = row["execution_history"] or []
        if isinstance(history, str):
            history = json.loads(history)
        history = list(history)

        # Preserve the scalar values from the previous design inside the JSON
        # list before removing those columns from the table.
        summary = {
            key: _json_value(row[key])
            for key in (
                "model_name",
                "model_type",
                "fallback_level",
                "fallback_used",
                "fallback_count",
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
                "started_at",
                "completed_at",
            )
            if row[key] is not None
        }
        if summary:
            history.insert(0, {"record_type": "execution_summary", **summary})

        migrated.append(
            {
                "agent_execution_id": row["agent_execution_id"],
                "incident_id": row["incident_id"],
                "agent_name": row["agent_name"],
                "execution_history": history,
                "created_at": row["created_at"],
                "updated_at": row["created_at"],
            }
        )

    if migrated:
        op.bulk_insert(new, migrated)

    op.drop_index("ix_agent_execution_log_incident_id", table_name="agent_execution_log")
    op.drop_table("agent_execution_log")
    op.rename_table("agent_execution_log_new", "agent_execution_log")
    op.create_index(
        "ix_agent_execution_log_incident_id",
        "agent_execution_log",
        ["incident_id"],
    )


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade is not supported after converting execution data to JSON-only history."
    )
