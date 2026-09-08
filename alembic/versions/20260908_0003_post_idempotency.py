"""Add post idempotency key.

Revision ID: 20260908_0003
Revises: 20260907_0002
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0003"
down_revision: str | None = "20260907_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    return column_name in {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)
    }


def upgrade() -> None:
    if _has_column("posts", "idempotency_key"):
        return
    op.add_column("posts", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_posts_idempotency_key", "posts", ["idempotency_key"])


def downgrade() -> None:
    if not _has_column("posts", "idempotency_key"):
        return
    op.drop_constraint("uq_posts_idempotency_key", "posts", type_="unique")
    op.drop_column("posts", "idempotency_key")