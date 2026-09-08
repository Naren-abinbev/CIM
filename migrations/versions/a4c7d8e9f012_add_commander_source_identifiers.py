"""Add original user and assignment identifiers to commanders.

Revision ID: a4c7d8e9f012
Revises: f3b8c9d0e123
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4c7d8e9f012"
down_revision: Union[str, Sequence[str], None] = "f3b8c9d0e123"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    commander_columns = {
        column["name"] for column in inspector.get_columns("commanders")
    }

    # SQLite requires a table rebuild when adding a foreign-key constraint.
    with op.batch_alter_table("commanders", recreate="always") as batch_op:
        if "original_user_id" not in commander_columns:
            batch_op.add_column(
                sa.Column("original_user_id", sa.String(length=36), nullable=True)
            )
        if "assignment_id" not in commander_columns:
            batch_op.add_column(
                sa.Column("assignment_id", sa.String(length=100), nullable=True)
            )
        batch_op.create_foreign_key(
            "fk_commanders_original_user_id_users",
            "users",
            ["original_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_commanders_original_user_id",
        "commanders",
        ["original_user_id"],
    )
    op.create_index(
        "ix_commanders_assignment_id",
        "commanders",
        ["assignment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_commanders_assignment_id", table_name="commanders")
    op.drop_index("ix_commanders_original_user_id", table_name="commanders")
    op.drop_constraint(
        "fk_commanders_original_user_id_users",
        "commanders",
        type_="foreignkey",
    )
    op.drop_column("commanders", "assignment_id")
    op.drop_column("commanders", "original_user_id")
