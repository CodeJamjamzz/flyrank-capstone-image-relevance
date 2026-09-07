"""Add pending review suggestion index.

Revision ID: 20260907_0002
Revises: 20260905_0001
Create Date: 2026-09-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260907_0002"
down_revision: str | None = "20260905_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_suggestions_status_created_at",
        "suggestions",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_suggestions_status_created_at", table_name="suggestions")