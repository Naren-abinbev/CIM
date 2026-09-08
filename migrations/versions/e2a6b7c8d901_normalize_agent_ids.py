"""Convert legacy agent names in execution logs to stable agent IDs.

Revision ID: e2a6b7c8d901
Revises: d1f4a5b6c789
"""

from __future__ import annotations

import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


AGENT_IDS = {
    "sample-investigation-agent": os.getenv(
        "AGENT_ID_SAMPLE_INVESTIGATION_AGENT",
        "sample-investigation-agent",
    )
}


revision: str = "e2a6b7c8d901"
down_revision: Union[str, Sequence[str], None] = "d1f4a5b6c789"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    table = sa.table(
        "agent_execution_log",
        sa.column("agent_id", sa.String(length=150)),
    )
    for agent_name, agent_id in AGENT_IDS.items():
        bind.execute(
            table.update()
            .where(table.c.agent_id == agent_name)
            .values(agent_id=agent_id)
        )


def downgrade() -> None:
    bind = op.get_bind()
    table = sa.table(
        "agent_execution_log",
        sa.column("agent_id", sa.String(length=150)),
    )
    for agent_name, agent_id in AGENT_IDS.items():
        bind.execute(
            table.update()
            .where(table.c.agent_id == agent_id)
            .values(agent_id=agent_name)
        )
