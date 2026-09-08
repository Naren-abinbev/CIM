"""Remove server-side refresh-token persistence.

Revision ID: f4c9d0e1a234
Revises: e8f2a3b4c567
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "f4c9d0e1a234"
down_revision: Union[str, Sequence[str], None] = "e8f2a3b4c567"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_token_family", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")


def downgrade() -> None:
    raise NotImplementedError(
        "Refresh-token records cannot be restored without a backup."
    )
