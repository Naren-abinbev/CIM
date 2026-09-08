"""Keep blast-radius data inside analysis history only.

Revision ID: d8e2f3a4b567
Revises: c9d0e1f2a345
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e2f3a4b567"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a345"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("incident_master", recreate="always") as batch_op:
        batch_op.drop_column("blast_radius")


def downgrade() -> None:
    with op.batch_alter_table("incident_master", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("blast_radius", sa.JSON(), nullable=True)
        )
