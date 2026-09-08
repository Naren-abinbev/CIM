"""Normalize incident ownership, assignments, and blast-radius JSON.

Revision ID: f5a0b1c2d345
Revises: f4c9d0e1a234
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f5a0b1c2d345"
down_revision: Union[str, Sequence[str], None] = "f4c9d0e1a234"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Add the incident owner and convert blast_radius to structured JSON.
    incident_columns = {
        column["name"] for column in inspector.get_columns("incident_master")
    }
    if "user_id" not in incident_columns:
        with op.batch_alter_table("incident_master", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("user_id", sa.String(36), nullable=True))
            batch_op.alter_column(
                "blast_radius",
                existing_type=sa.Text(),
                type_=sa.JSON(),
                existing_nullable=True,
            )
            batch_op.create_foreign_key(
                "fk_incident_master_user_id_users",
                "users",
                ["user_id"],
                ["id"],
                ondelete="SET NULL",
            )

    op.execute(
        "UPDATE incident_master SET user_id = "
        "(SELECT id FROM users WHERE users.email = incident_master.user_email) "
        "WHERE user_id IS NULL"
    )
    op.create_index("ix_incident_master_user_id", "incident_master", ["user_id"])

    # Assignment IDs describe an incident assignment, not a commander.
    assignment_columns = {
        column["name"]
        for column in inspector.get_columns("incident_commanders")
    }
    if "assignment_id" not in assignment_columns:
        with op.batch_alter_table("incident_commanders", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("assignment_id", sa.String(100), nullable=True))

    op.execute(
        "UPDATE incident_commanders SET assignment_id = "
        "(SELECT assignment_id FROM commanders "
        "WHERE commanders.commander_id = incident_commanders.commander_id) "
        "WHERE assignment_id IS NULL"
    )
    if "ix_incident_commanders_assignment_id" not in {
        index["name"] for index in inspector.get_indexes("incident_commanders")
    }:
        op.create_index(
            "ix_incident_commanders_assignment_id",
            "incident_commanders",
            ["assignment_id"],
        )

    commander_indexes = {
        index["name"] for index in inspector.get_indexes("commanders")
    }
    if "ix_commanders_assignment_id" in commander_indexes:
        op.drop_index("ix_commanders_assignment_id", table_name="commanders")
    with op.batch_alter_table("commanders", recreate="always") as batch_op:
        commander_columns = {
            column["name"] for column in inspector.get_columns("commanders")
        }
        if "assignment_id" in commander_columns:
            batch_op.drop_column("assignment_id")

    if "uq_incident_commanders_active_primary" not in {
        index["name"] for index in sa.inspect(bind).get_indexes("incident_commanders")
    }:
        op.create_index(
            "uq_incident_commanders_active_primary",
            "incident_commanders",
            ["incident_id"],
            unique=True,
            sqlite_where=sa.text("is_primary = 1 AND unassigned_at IS NULL"),
        )


def downgrade() -> None:
    raise NotImplementedError(
        "This normalization should be reverted from a database backup if needed."
    )
