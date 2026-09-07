import enum
import uuid
from datetime import datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def enum_values(enum_type: type[enum.Enum]) -> list[str]:
    return [str(member.value) for member in enum_type]


class DatasetLabel(enum.StrEnum):
    RED_FOX = "red_fox"
    WOLF = "wolf"
    DOG = "dog"
    BEAR = "bear"
    DEER = "deer"


class ImageProcessingStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    ACCEPTED = "accepted"
    NEEDS_REVIEW = "needs_review"
    RETRY_SCHEDULED = "retry_scheduled"
    FAILED = "failed"


class SuggestionStatus(enum.StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NO_CONFIDENT_MATCH = "no_confident_match"


class ReviewDecisionType(enum.StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class AttemptStatus(enum.StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    RETRY_SCHEDULED = "retry_scheduled"
    FAILED = "failed"


class ModelOperation(enum.StrEnum):
    VISION = "vision"
    EMBEDDING = "embedding"


class ModelCallStatus(enum.StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Image(Base):
    __tablename__ = "images"
    __table_args__ = (
        CheckConstraint("retry_count >= 0", name="ck_images_retry_count_non_negative"),
        Index(
            "ix_images_pending_retry",
            "processing_status",
            "next_retry_at",
            postgresql_where=text("processing_status IN ('pending', 'retry_scheduled')"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    file_path: Mapped[str] = mapped_column(String(500), unique=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    dataset_label: Mapped[DatasetLabel] = mapped_column(
        SqlEnum(DatasetLabel, name="dataset_label", values_callable=enum_values)
    )
    source_url: Mapped[str] = mapped_column(Text)
    license_url: Mapped[str] = mapped_column(Text)
    processing_status: Mapped[ImageProcessingStatus] = mapped_column(
        SqlEnum(ImageProcessingStatus, name="image_processing_status", values_callable=enum_values),
        default=ImageProcessingStatus.PENDING,
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImageMetadata(Base):
    __tablename__ = "image_metadata"
    __table_args__ = (
        CheckConstraint(
            "overall_confidence >= 0 AND overall_confidence <= 1",
            name="ck_image_metadata_confidence_range",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    image_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("images.id", ondelete="CASCADE"), unique=True
    )
    schema_version: Mapped[int] = mapped_column(Integer)
    caption: Mapped[str] = mapped_column(String(500))
    primary_subject: Mapped[str] = mapped_column(String(100))
    scientific_name: Mapped[str | None] = mapped_column(String(200))
    overall_confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    raw_response_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    normalized_label: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImageTag(Base):
    __tablename__ = "image_tags"
    __table_args__ = (
        UniqueConstraint("image_id", "tag_id", name="uq_image_tags_image_tag"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_image_tags_confidence_range"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    image_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"))
    tag_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"))
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    text: Mapped[str] = mapped_column(Text)
    recognized_subject: Mapped[str | None] = mapped_column(String(100))
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        CheckConstraint(
            "(image_id IS NOT NULL) <> (post_id IS NOT NULL)", name="ck_embeddings_single_owner"
        ),
        Index(
            "ix_embeddings_vector_cosine",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    image_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"))
    post_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    model_name: Mapped[str] = mapped_column(String(200))
    model_version: Mapped[str | None] = mapped_column(String(100))
    content_sha256: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list[float]] = mapped_column(Vector(768))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Suggestion(Base):
    __tablename__ = "suggestions"
    __table_args__ = (
        CheckConstraint(
            "similarity_score >= -1 AND similarity_score <= 1",
            name="ck_suggestions_similarity_range",
        ),
        Index("ix_suggestions_post_status", "post_id", "status"),
        Index("ix_suggestions_status_created_at", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    image_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("images.id", ondelete="SET NULL"))
    similarity_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    status: Mapped[SuggestionStatus] = mapped_column(
        SqlEnum(SuggestionStatus, name="suggestion_status", values_callable=enum_values)
    )
    reason_code: Mapped[str] = mapped_column(String(100))
    reason_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    __table_args__ = (Index("ix_review_decisions_suggestion", "suggestion_id"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    suggestion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suggestions.id", ondelete="CASCADE")
    )
    decision: Mapped[ReviewDecisionType] = mapped_column(
        SqlEnum(ReviewDecisionType, name="review_decision_type", values_callable=enum_values)
    )
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProcessingAttempt(Base):
    __tablename__ = "processing_attempts"
    __table_args__ = (
        UniqueConstraint("image_id", "attempt_number", name="uq_processing_attempts_image_attempt"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    image_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"))
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[AttemptStatus] = mapped_column(
        SqlEnum(AttemptStatus, name="attempt_status", values_callable=enum_values)
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ModelCall(Base):
    __tablename__ = "model_calls"
    __table_args__ = (
        CheckConstraint(
            "(image_id IS NOT NULL) <> (post_id IS NOT NULL)", name="ck_model_calls_single_owner"
        ),
        Index("ix_model_calls_created_at", "created_at"),
        CheckConstraint("input_units >= 0", name="ck_model_calls_input_units_non_negative"),
        CheckConstraint("output_units >= 0", name="ck_model_calls_output_units_non_negative"),
        CheckConstraint("estimated_cost_usd >= 0", name="ck_model_calls_cost_non_negative"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    image_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"))
    post_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    operation: Mapped[ModelOperation] = mapped_column(
        SqlEnum(ModelOperation, name="model_operation", values_callable=enum_values)
    )
    model_name: Mapped[str] = mapped_column(String(200))
    input_units: Mapped[int] = mapped_column(Integer, default=0)
    output_units: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    status: Mapped[ModelCallStatus] = mapped_column(
        SqlEnum(ModelCallStatus, name="model_call_status", values_callable=enum_values)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
