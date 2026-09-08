"""Use the original confidence_score name on incident master.

Revision ID: e8f2a3b4c567
Revises: d7e1f2a3b456
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8f2a3b4c567"
down_revision: Union[str, Sequence[str], None] = "d7e1f2a3b456"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("incident_master", recreate="always") as batch_op:
        batch_op.alter_column(
            "analysis_confidence_score",
            new_column_name="confidence_score",
            existing_type=sa.Numeric(5, 4),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("incident_master", recreate="always") as batch_op:
        batch_op.alter_column(
            "confidence_score",
            new_column_name="analysis_confidence_score",
            existing_type=sa.Numeric(5, 4),
            existing_nullable=True,
        )
