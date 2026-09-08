"""Preserve repeated incident analysis results as JSON history.

Revision ID: a6b1c2d3e456
Revises: f5a0b1c2d345
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6b1c2d3e456"
down_revision: Union[str, Sequence[str], None] = "f5a0b1c2d345"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "incident_master",
        sa.Column("analysis_history", sa.JSON(), nullable=True),
    )
    op.execute(
        "UPDATE incident_master SET analysis_history = '[]' "
        "WHERE analysis_history IS NULL"
    )
    with op.batch_alter_table("incident_master", recreate="always") as batch_op:
        batch_op.alter_column(
            "analysis_history",
            existing_type=sa.JSON(),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("incident_master", recreate="always") as batch_op:
        batch_op.drop_column("analysis_history")
