from app.db.base import Base
from app.db.models import Embedding, Image, ImageMetadata, ImageTag, ModelCall


def constraint_names(table_name: str) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {constraint.name for constraint in table.constraints if constraint.name is not None}


def test_required_tables_and_constraints_exist() -> None:
    expected_tables = {
        "images",
        "image_metadata",
        "tags",
        "image_tags",
        "embeddings",
        "posts",
        "suggestions",
        "review_decisions",
        "processing_attempts",
        "model_calls",
    }

    assert expected_tables.issubset(Base.metadata.tables)
    assert "ck_images_retry_count_non_negative" in constraint_names(Image.__tablename__)
    assert "ck_image_metadata_confidence_range" in constraint_names(ImageMetadata.__tablename__)
    assert "uq_image_tags_image_tag" in constraint_names(ImageTag.__tablename__)
    assert "ck_embeddings_single_owner" in constraint_names(Embedding.__tablename__)
    assert "ck_model_calls_single_owner" in constraint_names(ModelCall.__tablename__)


def test_required_indexes_exist() -> None:
    assert "ix_images_pending_retry" in {index.name for index in Image.__table__.indexes}
    assert "ix_embeddings_vector_cosine" in {index.name for index in Embedding.__table__.indexes}
    assert "ix_model_calls_created_at" in {index.name for index in ModelCall.__table__.indexes}


def test_embedding_column_uses_768_dimensions() -> None:
    assert Embedding.__table__.c.embedding.type.dim == 768
