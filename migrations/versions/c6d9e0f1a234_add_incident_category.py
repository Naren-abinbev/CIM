"""Add category to incident master.

Revision ID: c6d9e0f1a234
Revises: b5d9e0f1a234
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c6d9e0f1a234"
down_revision: Union[str, Sequence[str], None] = "b5d9e0f1a234"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "incident_master",
        sa.Column("category", sa.String(length=100), nullable=True),
    )
    op.execute(
        "UPDATE incident_master SET category = 'uncategorized' "
        "WHERE category IS NULL"
    )
    with op.batch_alter_table("incident_master", recreate="always") as batch_op:
        batch_op.alter_column(
            "category",
            existing_type=sa.String(length=100),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("incident_master", recreate="always") as batch_op:
        batch_op.drop_column("category")
