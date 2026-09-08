"""Use agent IDs in the JSON-only execution log.

Revision ID: d1f4a5b6c789
Revises: c9e2f3a4b567
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1f4a5b6c789"
down_revision: Union[str, Sequence[str], None] = "c9e2f3a4b567"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("agent_execution_log", schema=None) as batch_op:
        batch_op.alter_column(
            "agent_name",
            new_column_name="agent_id",
            existing_type=sa.String(length=150),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_execution_log", schema=None) as batch_op:
        batch_op.alter_column(
            "agent_id",
            new_column_name="agent_name",
            existing_type=sa.String(length=150),
            existing_nullable=False,
        )
