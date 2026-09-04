"""Create image relevance foundation tables.

Revision ID: 20260905_0001
Revises:
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import app.db.models  # noqa: F401
from alembic import op
from app.db.base import Base

revision: str = "20260905_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind())
