"""Remove the display name from commanders.

Revision ID: b5d9e0f1a234
Revises: a4c7d8e9f012
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5d9e0f1a234"
down_revision: Union[str, Sequence[str], None] = "a4c7d8e9f012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("commanders", recreate="always") as batch_op:
        batch_op.drop_column("name")


def downgrade() -> None:
    with op.batch_alter_table("commanders", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "name",
                sa.String(length=255),
                nullable=True,
            )
        )
