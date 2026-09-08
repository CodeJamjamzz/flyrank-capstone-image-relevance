from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    AttemptStatus,
    Image,
    ImageMetadata,
    ImageProcessingStatus,
    ImageTag,
    ModelCall,
    ModelCallStatus,
    ModelOperation,
    ProcessingAttempt,
    Tag,
)
from app.schemas.image_metadata import ImageMetadataPayload
from app.services.budget import CostBudgetExceededError, ensure_cost_budget_available
from app.services.embeddings import EmbeddingProvider, embed_image_if_needed
from app.services.vision import VisionProvider, VisionProviderError, VisionResponse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClaimedImage:
    image_id: uuid.UUID
    attempt_id: uuid.UUID
    file_path: str


@dataclass(frozen=True)
class ProcessingOutcome:
    processed: bool
    rate_limited: bool = False
    budget_limited: bool = False


def claim_next_image(session: Session, now: datetime | None = None) -> ClaimedImage | None:
    current_time = now or utc_now()
    image = session.scalar(
        select(Image)
        .where(
            or_(
                Image.processing_status == ImageProcessingStatus.PENDING,
                and_(
                    Image.processing_status == ImageProcessingStatus.RETRY_SCHEDULED,
                    Image.next_retry_at <= current_time,
                ),
            )
        )
        .order_by(Image.created_at, Image.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if image is None:
        return None

    image.retry_count += 1
    image.processing_status = ImageProcessingStatus.PROCESSING
    image.next_retry_at = None
    attempt = ProcessingAttempt(
        image_id=image.id,
        attempt_number=image.retry_count,
        status=AttemptStatus.STARTED,
    )
    session.add(attempt)
    session.flush()
    session.commit()
    return ClaimedImage(image_id=image.id, attempt_id=attempt.id, file_path=image.file_path)


def process_next_image(
    session: Session,
    provider: VisionProvider,
    configuration: Settings,
    project_root: Path,
    embedding_provider: EmbeddingProvider | None = None,
) -> ProcessingOutcome:
    claimed_image = claim_next_image(session)
    if claimed_image is None:
        return ProcessingOutcome(processed=False)

    image = session.get(Image, claimed_image.image_id)
    attempt = session.get(ProcessingAttempt, claimed_image.attempt_id)
    if image is None or attempt is None:
        raise RuntimeError("Claimed image or processing attempt no longer exists")

    try:
        ensure_cost_budget_available(session, image.tenant_id, configuration)
    except CostBudgetExceededError as error:
        _complete_failure(
            session,
            image,
            attempt,
            error,
            retryable=True,
            configuration=configuration,
            budget_limited=True,
        )
        return ProcessingOutcome(processed=True, budget_limited=True)
    try:
        image_path = resolve_image_path(project_root, image.file_path)
        response = provider.analyze_image(image_path)
    except VisionProviderError as error:
        _record_failed_model_call(session, image, provider.model_name)
        _complete_failure(
            session,
            image,
            attempt,
            error,
            error.retryable,
            configuration,
            rate_limited=error.rate_limited,
        )
        return ProcessingOutcome(processed=True, rate_limited=error.rate_limited)
    except OSError as error:
        _record_failed_model_call(session, image, provider.model_name)
        _complete_failure(
            session, image, attempt, error, retryable=False, configuration=configuration
        )
        return ProcessingOutcome(processed=True)

    _record_successful_model_call(session, image, response, configuration)
    try:
        metadata = ImageMetadataPayload.model_validate_json(response.raw_response)
    except ValidationError as error:
        _complete_failure(
            session, image, attempt, error, retryable=True, configuration=configuration
        )
        return ProcessingOutcome(processed=True)

    _persist_metadata(session, image, metadata)
    attempt.status = AttemptStatus.SUCCEEDED
    attempt.finished_at = utc_now()
    image.processing_status = (
        ImageProcessingStatus.ACCEPTED
        if metadata.overall_confidence >= configuration.minimum_image_confidence
        else ImageProcessingStatus.NEEDS_REVIEW
    )
    image.accepted_at = (
        utc_now() if image.processing_status == ImageProcessingStatus.ACCEPTED else None
    )
    session.commit()
    if image.processing_status == ImageProcessingStatus.ACCEPTED and embedding_provider is not None:
        embed_image_if_needed(session, image, embedding_provider, configuration)
    return ProcessingOutcome(processed=True)


def resolve_image_path(project_root: Path, file_path: str) -> Path:
    corpus_root = (project_root / "data" / "corpus" / "raw").resolve()
    image_path = (project_root / file_path).resolve()
    if not image_path.is_relative_to(corpus_root):
        raise OSError("Image path points outside data/corpus/raw")
    if not image_path.is_file():
        raise OSError(f"Image file does not exist: {file_path}")
    return image_path


def estimated_cost_usd(
    input_units: int,
    output_units: int,
    configuration: Settings,
) -> Decimal:
    return (
        Decimal(input_units) * configuration.gemini_vision_input_cost_per_million_units
        + Decimal(output_units) * configuration.gemini_vision_output_cost_per_million_units
    ) / Decimal("1000000")


def retry_delay(attempt_number: int) -> timedelta:
    delays = {1: timedelta(minutes=1), 2: timedelta(minutes=5)}
    return delays[attempt_number]


def utc_now() -> datetime:
    return datetime.now(UTC)


def _record_successful_model_call(
    session: Session,
    image: Image,
    response: VisionResponse,
    configuration: Settings,
) -> None:
    session.add(
        ModelCall(
            image_id=image.id,
            tenant_id=image.tenant_id,
            operation=ModelOperation.VISION,
            model_name=response.model_name,
            input_units=response.input_units,
            output_units=response.output_units,
            estimated_cost_usd=estimated_cost_usd(
                response.input_units, response.output_units, configuration
            ),
            status=ModelCallStatus.SUCCEEDED,
        )
    )


def _record_failed_model_call(session: Session, image: Image, model_name: str) -> None:
    session.add(
        ModelCall(
            image_id=image.id,
            tenant_id=image.tenant_id,
            operation=ModelOperation.VISION,
            model_name=model_name,
            status=ModelCallStatus.FAILED,
        )
    )


def _complete_failure(
    session: Session,
    image: Image,
    attempt: ProcessingAttempt,
    error: Exception,
    retryable: bool,
    configuration: Settings,
    rate_limited: bool = False,
    budget_limited: bool = False,
) -> None:
    now = utc_now()
    attempt.error_code = type(error).__name__
    attempt.error_message = str(error)[:2000]
    attempt.finished_at = now

    if budget_limited:
        next_retry_at = now + timedelta(seconds=configuration.ai_budget_backoff_seconds)
        attempt.status = AttemptStatus.RETRY_SCHEDULED
        attempt.retry_at = next_retry_at
        image.processing_status = ImageProcessingStatus.RETRY_SCHEDULED
        image.next_retry_at = next_retry_at
        logger.warning(
            "AI cost budget reached for tenant %s; deferred %s.", image.tenant_id, image.file_path
        )
    elif rate_limited:
        next_retry_at = now + timedelta(
            seconds=configuration.image_worker_rate_limit_backoff_seconds
        )
        attempt.status = AttemptStatus.RETRY_SCHEDULED
        attempt.retry_at = next_retry_at
        image.processing_status = ImageProcessingStatus.RETRY_SCHEDULED
        image.next_retry_at = next_retry_at
    elif retryable and image.retry_count < configuration.maximum_processing_attempts:
        next_retry_at = now + retry_delay(image.retry_count)
        attempt.status = AttemptStatus.RETRY_SCHEDULED
        attempt.retry_at = next_retry_at
        image.processing_status = ImageProcessingStatus.RETRY_SCHEDULED
        image.next_retry_at = next_retry_at
    else:
        attempt.status = AttemptStatus.FAILED
        image.processing_status = ImageProcessingStatus.FAILED
        image.next_retry_at = None
        logger.error(
            "Image processing permanently failed for %s after attempt %s: %s",
            image.file_path,
            image.retry_count,
            error,
        )
    session.commit()


def _persist_metadata(session: Session, image: Image, metadata: ImageMetadataPayload) -> None:
    session.add(
        ImageMetadata(
            image_id=image.id,
            schema_version=metadata.schema_version,
            caption=metadata.caption,
            primary_subject=metadata.primary_subject.label,
            scientific_name=metadata.primary_subject.scientific_name,
            overall_confidence=Decimal(str(metadata.overall_confidence)),
            raw_response_json=metadata.model_dump(mode="json"),
        )
    )
    for payload_tag in metadata.tags:
        session.execute(
            insert(Tag)
            .values(normalized_label=payload_tag.label)
            .on_conflict_do_nothing(index_elements=[Tag.normalized_label])
        )
        tag = session.scalar(select(Tag).where(Tag.normalized_label == payload_tag.label))
        if tag is None:
            raise RuntimeError(f"Could not persist tag {payload_tag.label}")
        session.add(
            ImageTag(
                image_id=image.id,
                tag_id=tag.id,
                confidence=Decimal(str(payload_tag.confidence)),
            )
        )
