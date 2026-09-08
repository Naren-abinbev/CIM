"""Add former incident-analysis fields to incident master.

Revision ID: d7e1f2a3b456
Revises: c6d9e0f1a234
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7e1f2a3b456"
down_revision: Union[str, Sequence[str], None] = "c6d9e0f1a234"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = (
        sa.Column("intent", sa.String(100), nullable=True),
        sa.Column("intent_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("severity_prediction", sa.String(20), nullable=True),
        sa.Column("severity_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("business_impact", sa.Text(), nullable=True),
        sa.Column("risk_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("next_best_action", sa.Text(), nullable=True),
        sa.Column("root_cause_hypothesis", sa.Text(), nullable=True),
        sa.Column("blast_radius", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("author_input_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("resolution_evaluation_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("recommendation_status", sa.String(30), nullable=True),
        sa.Column("analysis_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in columns:
        op.add_column("incident_master", column)


def downgrade() -> None:
    column_names = (
        "analysis_created_at",
        "recommendation_status",
        "resolution_evaluation_score",
        "author_input_score",
        "confidence_score",
        "blast_radius",
        "root_cause_hypothesis",
        "next_best_action",
        "risk_score",
        "business_impact",
        "severity_confidence",
        "severity_prediction",
        "intent_confidence",
        "intent",
    )
    for column_name in column_names:
        op.drop_column("incident_master", column_name)
