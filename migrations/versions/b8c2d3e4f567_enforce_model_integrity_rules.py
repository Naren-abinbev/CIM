"""Enforce ownership, assignment, and one-record-per-incident rules.

Revision ID: b8c2d3e4f567
Revises: a6b1c2d3e456
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8c2d3e4f567"
down_revision: Union[str, Sequence[str], None] = "a6b1c2d3e456"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    missing_owners = bind.execute(
        sa.text("SELECT COUNT(*) FROM incident_master WHERE user_id IS NULL")
    ).scalar_one()
    if missing_owners:
        raise RuntimeError(
            "Cannot make incident_master.user_id required: "
            f"{missing_owners} incident(s) have no matching user."
        )

    with op.batch_alter_table("incident_master", recreate="always") as batch_op:
        batch_op.alter_column(
            "user_id",
            existing_type=sa.String(36),
            nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_incident_master_category_not_blank",
            "length(trim(category)) > 0",
        )
        batch_op.create_check_constraint(
            "ck_incident_master_status_not_blank",
            "length(trim(status)) > 0",
        )
        batch_op.create_check_constraint(
            "ck_incident_master_source_not_blank",
            "length(trim(source)) > 0",
        )

    with op.batch_alter_table("war_room", recreate="always") as batch_op:
        batch_op.create_unique_constraint("uq_war_room_incident_id", ["incident_id"])

    with op.batch_alter_table(
        "incident_performance_metrics", recreate="always"
    ) as batch_op:
        batch_op.create_unique_constraint(
            "uq_incident_performance_metrics_incident_id",
            ["incident_id"],
        )

    with op.batch_alter_table("incident_commanders", recreate="always") as batch_op:
        batch_op.create_unique_constraint(
            "uq_incident_commanders_assignment_id",
            ["assignment_id"],
        )


def downgrade() -> None:
    raise NotImplementedError(
        "Model integrity constraints should be reverted from a database backup if needed."
    )
