"""add retrieval version to workspaces

Revision ID: b7c2d4e5f6a7
Revises: 9a7b8c9d0e1f
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c2d4e5f6a7"
down_revision: str | Sequence[str] | None = "9a7b8c9d0e1f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("retrieval_version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "retrieval_version")