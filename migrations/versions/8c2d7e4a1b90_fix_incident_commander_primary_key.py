"""Fix incident commander assignment primary key.

Revision ID: 8c2d7e4a1b90
Revises: da5cb4114a40
Create Date: 2026-09-07

The previous schema used (incident_id, commander_id) as the primary key.
The current model uses incident_commander_id so assignment history can be
represented when the same commander is assigned again later.
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8c2d7e4a1b90"
down_revision: Union[str, Sequence[str], None] = "da5cb4114a40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rebuild the table with incident_commander_id as its primary key."""
    bind = op.get_bind()

    old_table = sa.Table(
        "incident_commanders",
        sa.MetaData(),
        sa.Column("incident_id", sa.String(length=36)),
        sa.Column("commander_id", sa.String(length=36)),
        sa.Column("incident_commander_id", sa.String(length=36)),
        sa.Column("assigned_at", sa.DateTime(timezone=True)),
        sa.Column("unassigned_at", sa.DateTime(timezone=True)),
        sa.Column("is_primary", sa.Boolean()),
    )

    rows = bind.execute(
        sa.select(
            old_table.c.incident_id,
            old_table.c.commander_id,
            old_table.c.incident_commander_id,
            old_table.c.assigned_at,
            old_table.c.unassigned_at,
            old_table.c.is_primary,
        ).select_from(old_table)
    ).mappings().all()

    op.drop_index(
        "ix_incident_commanders_incident_id",
        table_name="incident_commanders",
    )
    op.drop_index(
        "ix_incident_commanders_commander_id",
        table_name="incident_commanders",
    )

    op.rename_table(
        "incident_commanders",
        "incident_commanders_old",
    )

    op.create_table(
        "incident_commanders",
        sa.Column("incident_commander_id", sa.String(length=36), nullable=False),
        sa.Column("incident_id", sa.String(length=36), nullable=False),
        sa.Column("commander_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unassigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incident_master.incident_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["commander_id"],
            ["commanders.commander_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("incident_commander_id"),
    )

    new_table = sa.table(
        "incident_commanders",
        sa.column("incident_commander_id", sa.String(length=36)),
        sa.column("incident_id", sa.String(length=36)),
        sa.column("commander_id", sa.String(length=36)),
        sa.column("assigned_at", sa.DateTime(timezone=True)),
        sa.column("unassigned_at", sa.DateTime(timezone=True)),
        sa.column("is_primary", sa.Boolean()),
    )

    migrated_rows = [
        {
            "incident_commander_id": (
                row["incident_commander_id"] or str(uuid.uuid4())
            ),
            "incident_id": row["incident_id"],
            "commander_id": row["commander_id"],
            "assigned_at": row["assigned_at"],
            "unassigned_at": row["unassigned_at"],
            "is_primary": row["is_primary"],
        }
        for row in rows
    ]

    if migrated_rows:
        op.bulk_insert(new_table, migrated_rows)

    op.create_index(
        "ix_incident_commanders_incident_id",
        "incident_commanders",
        ["incident_id"],
    )
    op.create_index(
        "ix_incident_commanders_commander_id",
        "incident_commanders",
        ["commander_id"],
    )

    op.drop_table("incident_commanders_old")


def downgrade() -> None:
    """Restore the previous composite primary key.

    Downgrade can fail if the table contains repeated assignments for the
    same incident/commander pair, because that pair was unique previously.
    """
    bind = op.get_bind()

    current_table = sa.Table(
        "incident_commanders",
        sa.MetaData(),
        sa.Column("incident_commander_id", sa.String(length=36)),
        sa.Column("incident_id", sa.String(length=36)),
        sa.Column("commander_id", sa.String(length=36)),
        sa.Column("assigned_at", sa.DateTime(timezone=True)),
        sa.Column("unassigned_at", sa.DateTime(timezone=True)),
        sa.Column("is_primary", sa.Boolean()),
    )

    rows = bind.execute(
        sa.select(
            current_table.c.incident_id,
            current_table.c.commander_id,
            current_table.c.assigned_at,
            current_table.c.unassigned_at,
            current_table.c.is_primary,
        ).select_from(current_table)
    ).mappings().all()

    op.drop_index(
        "ix_incident_commanders_incident_id",
        table_name="incident_commanders",
    )
    op.drop_index(
        "ix_incident_commanders_commander_id",
        table_name="incident_commanders",
    )

    op.rename_table(
        "incident_commanders",
        "incident_commanders_new",
    )

    op.create_table(
        "incident_commanders",
        sa.Column("incident_id", sa.String(length=36), nullable=False),
        sa.Column("commander_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unassigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incident_master.incident_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["commander_id"],
            ["commanders.commander_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("incident_id", "commander_id"),
    )

    old_table = sa.table(
        "incident_commanders",
        sa.column("incident_id", sa.String(length=36)),
        sa.column("commander_id", sa.String(length=36)),
        sa.column("assigned_at", sa.DateTime(timezone=True)),
        sa.column("unassigned_at", sa.DateTime(timezone=True)),
        sa.column("is_primary", sa.Boolean()),
    )

    if rows:
        op.bulk_insert(old_table, [dict(row) for row in rows])

    op.create_index(
        "ix_incident_commanders_incident_id",
        "incident_commanders",
        ["incident_id"],
    )
    op.create_index(
        "ix_incident_commanders_commander_id",
        "incident_commanders",
        ["commander_id"],
    )

    op.drop_table("incident_commanders_new")
