from pathlib import Path


def test_initial_migration_defines_vector_extension_and_schema_creation() -> None:
    migration = Path("alembic/versions/20260905_0001_image_relevance_foundation.py").read_text(
        encoding="utf-8"
    )

    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration
    assert "Base.metadata.create_all" in migration
    assert "20260905_0001" in migration


def test_review_migration_adds_pending_review_index() -> None:
    migration = Path("alembic/versions/20260907_0002_review_index.py").read_text(encoding="utf-8")

    assert "ix_suggestions_status_created_at" in migration
    assert "created_at" in migration


def test_post_idempotency_migration_adds_unique_constraint() -> None:
    migration = Path("alembic/versions/20260908_0003_post_idempotency.py").read_text(
        encoding="utf-8"
    )

    assert "idempotency_key" in migration
    assert "uq_posts_idempotency_key" in migration


def test_tenant_migration_backfills_ownership_and_cost_indexes() -> None:
    migration = Path("alembic/versions/20260908_0004_tenant_budget_guard.py").read_text(
        encoding="utf-8"
    )

    assert "tenants" in migration
    assert "tenant_id" in migration
    assert "uq_posts_tenant_idempotency_key" in migration
    assert "ix_model_calls_tenant_created_at" in migration
