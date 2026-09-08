"""Add tenant isolation and AI cost budget indexes.

Revision ID: 20260908_0004
Revises: 20260908_0003
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

DEFAULT_TENANT_ID = "00000000-0000-4000-8000-000000000001"

revision: str = "20260908_0004"
down_revision: str | None = "20260908_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("tenants"):
        op.create_table(
            "tenants",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False, unique=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    op.execute(
        "INSERT INTO tenants (id, name) VALUES "
        "('00000000-0000-4000-8000-000000000001'::uuid, 'default') "
        "ON CONFLICT (id) DO NOTHING"
    )

    for table_name in ("images", "posts", "model_calls"):
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "tenant_id" not in columns:
            op.add_column(table_name, sa.Column("tenant_id", sa.Uuid(), nullable=True))
        op.execute(
            f"UPDATE {table_name} SET tenant_id = "
            "'00000000-0000-4000-8000-000000000001'::uuid WHERE tenant_id IS NULL"
        )
        op.alter_column(table_name, "tenant_id", existing_type=sa.Uuid(), nullable=False)
        foreign_keys = {foreign_key["name"] for foreign_key in inspector.get_foreign_keys(table_name)}
        foreign_key_name = f"{table_name}_tenant_id_fkey"
        if foreign_key_name not in foreign_keys:
            op.create_foreign_key(
                foreign_key_name,
                table_name,
                "tenants",
                ["tenant_id"],
                ["id"],
                ondelete="RESTRICT",
            )

    post_constraints = {constraint["name"] for constraint in inspector.get_unique_constraints("posts")}
    if "uq_posts_idempotency_key" in post_constraints:
        op.drop_constraint("uq_posts_idempotency_key", "posts", type_="unique")
    if "uq_posts_tenant_idempotency_key" not in post_constraints:
        op.create_unique_constraint(
            "uq_posts_tenant_idempotency_key",
            "posts",
            ["tenant_id", "idempotency_key"],
        )

    index_definitions = (
        ("ix_images_tenant_status_retry", "images", ["tenant_id", "processing_status", "next_retry_at"]),
        ("ix_posts_tenant_created_at", "posts", ["tenant_id", "created_at"]),
        ("ix_model_calls_tenant_created_at", "model_calls", ["tenant_id", "created_at"]),
    )
    for index_name, table_name, columns in index_definitions:
        existing_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
        if index_name not in existing_indexes:
            op.create_index(index_name, table_name, columns)


def downgrade() -> None:
    op.drop_index("ix_model_calls_tenant_created_at", table_name="model_calls")
    op.drop_index("ix_posts_tenant_created_at", table_name="posts")
    op.drop_index("ix_images_tenant_status_retry", table_name="images")
    op.drop_constraint("uq_posts_tenant_idempotency_key", "posts", type_="unique")
    op.create_unique_constraint("uq_posts_idempotency_key", "posts", ["idempotency_key"])
    for table_name in ("model_calls", "posts", "images"):
        op.drop_constraint(f"{table_name}_tenant_id_fkey", table_name, type_="foreignkey")
        op.drop_column(table_name, "tenant_id")
    op.drop_table("tenants")