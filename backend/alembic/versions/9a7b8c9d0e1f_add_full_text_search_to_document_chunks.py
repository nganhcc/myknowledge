"""add full text search to document chunks

Revision ID: 9a7b8c9d0e1f
Revises: 5d25bb7eb546
Create Date: 2026-09-03

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9a7b8c9d0e1f"
down_revision: str | Sequence[str] | None = "5d25bb7eb546"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column(
            "content_search",
            sa.dialects.postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple', content)", persisted=True),
            nullable=False,
        ),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_content_search "
        "ON document_chunks USING gin (content_search)"
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_content_search", table_name="document_chunks")
    op.drop_column("document_chunks", "content_search")