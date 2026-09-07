from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from google import genai
from google.genai import types
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    Embedding,
    Image,
    ImageMetadata,
    ImageTag,
    ModelCall,
    ModelCallStatus,
    ModelOperation,
    Tag,
)

EMBEDDING_DIMENSIONS = 768


@dataclass(frozen=True)
class EmbeddingResponse:
    values: list[float]
    model_name: str
    input_units: int


class EmbeddingProviderError(RuntimeError):
    def __init__(self, message: str, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class EmbeddingProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    def embed_text(self, text: str) -> EmbeddingResponse: ...


class GeminiEmbeddingProvider:
    def __init__(self, configuration: Settings) -> None:
        if configuration.gemini_api_key is None:
            raise ValueError("GEMINI_API_KEY must be configured for embeddings")
        self._client = genai.Client(api_key=configuration.gemini_api_key.get_secret_value())
        self._model_name = configuration.embedding_model

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_text(self, text: str) -> EmbeddingResponse:
        try:
            response = self._client.models.embed_content(
                model=self.model_name,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type="SEMANTIC_SIMILARITY",
                    output_dimensionality=EMBEDDING_DIMENSIONS,
                ),
            )
        except Exception as error:
            raise EmbeddingProviderError(
                str(error), retryable=_is_retryable_provider_error(error)
            ) from error

        if not response.embeddings or not response.embeddings[0].values:
            raise EmbeddingProviderError("Embedding provider returned no vector", retryable=True)

        values = response.embeddings[0].values
        if len(values) != EMBEDDING_DIMENSIONS:
            raise EmbeddingProviderError(
                f"Expected {EMBEDDING_DIMENSIONS} embedding dimensions, received {len(values)}",
                retryable=False,
            )
        metadata = response.metadata
        input_units = metadata.billable_character_count if metadata else 0
        return EmbeddingResponse(
            values=values,
            model_name=self.model_name,
            input_units=input_units or 0,
        )


def content_checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def image_embedding_text(session: Session, image_id: uuid.UUID) -> str:
    metadata = session.scalar(select(ImageMetadata).where(ImageMetadata.image_id == image_id))
    if metadata is None:
        raise ValueError("Accepted image metadata is required before embedding")
    tag_labels = session.scalars(
        select(Tag.normalized_label)
        .join(ImageTag, ImageTag.tag_id == Tag.id)
        .where(ImageTag.image_id == image_id)
        .order_by(Tag.normalized_label)
    ).all()
    return f"{metadata.caption}\nTags: {', '.join(tag_labels)}"


def embed_image_if_needed(
    session: Session,
    image: Image,
    provider: EmbeddingProvider,
    configuration: Settings,
) -> bool:
    text = image_embedding_text(session, image.id)
    return _embed_if_needed(
        session=session,
        owner_id=image.id,
        owner_type="image",
        text=text,
        provider=provider,
        configuration=configuration,
    )


def embed_post_if_needed(
    session: Session,
    post_id: uuid.UUID,
    text: str,
    provider: EmbeddingProvider,
    configuration: Settings,
) -> bool:
    return _embed_if_needed(
        session=session,
        owner_id=post_id,
        owner_type="post",
        text=text,
        provider=provider,
        configuration=configuration,
    )


def latest_embedding_for_post(session: Session, post_id: uuid.UUID) -> Embedding | None:
    return session.scalar(
        select(Embedding)
        .where(Embedding.post_id == post_id)
        .order_by(Embedding.created_at.desc(), Embedding.id.desc())
        .limit(1)
    )


def _embed_if_needed(
    session: Session,
    owner_id: uuid.UUID,
    owner_type: str,
    text: str,
    provider: EmbeddingProvider,
    configuration: Settings,
) -> bool:
    checksum = content_checksum(text)
    owner_column = Embedding.image_id if owner_type == "image" else Embedding.post_id
    existing = session.scalar(
        select(Embedding).where(
            owner_column == owner_id,
            Embedding.model_name == provider.model_name,
            Embedding.content_sha256 == checksum,
        )
    )
    if existing is not None:
        return True

    try:
        response = provider.embed_text(text)
    except EmbeddingProviderError:
        _record_failed_model_call(session, owner_id, owner_type, provider.model_name)
        session.commit()
        return False

    if len(response.values) != EMBEDDING_DIMENSIONS:
        _record_failed_model_call(session, owner_id, owner_type, response.model_name)
        session.commit()
        return False

    embedding = Embedding(
        model_name=response.model_name,
        content_sha256=checksum,
        embedding=response.values,
    )
    model_call = ModelCall(
        operation=ModelOperation.EMBEDDING,
        model_name=response.model_name,
        input_units=response.input_units,
        estimated_cost_usd=estimated_embedding_cost_usd(response.input_units, configuration),
        status=ModelCallStatus.SUCCEEDED,
    )
    if owner_type == "image":
        embedding.image_id = owner_id
        model_call.image_id = owner_id
    else:
        embedding.post_id = owner_id
        model_call.post_id = owner_id
    session.add_all([embedding, model_call])
    session.commit()
    return True


def estimated_embedding_cost_usd(input_units: int, configuration: Settings) -> Decimal:
    return (
        Decimal(input_units) * configuration.gemini_embedding_input_cost_per_million_units
    ) / Decimal("1000000")


def _record_failed_model_call(
    session: Session,
    owner_id: uuid.UUID,
    owner_type: str,
    model_name: str,
) -> None:
    model_call = ModelCall(
        operation=ModelOperation.EMBEDDING,
        model_name=model_name,
        status=ModelCallStatus.FAILED,
    )
    if owner_type == "image":
        model_call.image_id = owner_id
    else:
        model_call.post_id = owner_id
    session.add(model_call)


def _is_retryable_provider_error(error: Exception) -> bool:
    message = str(error).lower()
    return any(
        marker in message
        for marker in ("429", "rate limit", "timeout", "connection", "500", "502", "503", "504")
    )
