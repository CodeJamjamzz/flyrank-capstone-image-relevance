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


def upgrade() -> None:
    op.add_column("posts", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_posts_idempotency_key", "posts", ["idempotency_key"])


def downgrade() -> None:
    op.drop_constraint("uq_posts_idempotency_key", "posts", type_="unique")
    op.drop_column("posts", "idempotency_key")