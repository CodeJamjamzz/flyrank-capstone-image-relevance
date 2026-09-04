from pathlib import Path


def test_initial_migration_defines_vector_extension_and_schema_creation() -> None:
    migration = Path("alembic/versions/20260905_0001_image_relevance_foundation.py").read_text(
        encoding="utf-8"
    )

    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration
    assert "Base.metadata.create_all" in migration
    assert "20260905_0001" in migration
