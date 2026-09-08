"""Remove analysis, duplicate, blast-radius, and resolution tables.

Revision ID: f3b8c9d0e123
Revises: e2a6b7c8d901
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "f3b8c9d0e123"
down_revision: Union[str, Sequence[str], None] = "e2a6b7c8d901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop indexes first because these tables were created with indexed
    # incident-id columns. The duplicate table also references incident twice.
    op.drop_index("ix_resolution_intelligence_incident_id", table_name="resolution_intelligence")
    op.drop_table("resolution_intelligence")

    op.drop_index("ix_incident_analysis_incident_id", table_name="incident_analysis")
    op.drop_table("incident_analysis")

    op.drop_index("ix_duplicate_identification_matched_incident_id", table_name="duplicate_identification")
    op.drop_index("ix_duplicate_identification_incident_id", table_name="duplicate_identification")
    op.drop_table("duplicate_identification")

    op.drop_index("ix_blast_radius_incident_id", table_name="blast_radius")
    op.drop_table("blast_radius")


def downgrade() -> None:
    raise NotImplementedError(
        "The removed analysis tables must be restored from a backup if needed."
    )
