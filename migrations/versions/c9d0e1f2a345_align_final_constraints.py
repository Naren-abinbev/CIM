"""Align final ORM constraint names and uniqueness definitions.

Revision ID: c9d0e1f2a345
Revises: b8c2d3e4f567
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d0e1f2a345"
down_revision: Union[str, Sequence[str], None] = "b8c2d3e4f567"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(
        "ix_incident_commanders_assignment_id",
        table_name="incident_commanders",
    )
    with op.batch_alter_table("incident_master", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "fk_incident_master_user_id_users",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_incident_master_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("incident_master", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "fk_incident_master_user_id_users",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_incident_master_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_incident_commanders_assignment_id",
        "incident_commanders",
        ["assignment_id"],
    )
