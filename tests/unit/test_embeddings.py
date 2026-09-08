from __future__ import annotations

import uuid
from decimal import Decimal
from typing import cast

from app.core.config import Settings
from app.db.models import Embedding, ModelCall, ModelCallStatus, ModelOperation
from app.services.embeddings import (
    EMBEDDING_DIMENSIONS,
    EmbeddingResponse,
    content_checksum,
    embed_post_if_needed,
    estimated_embedding_cost_usd,
    image_embedding_text,
)


class FakeProvider:
    model_name = "gemini-embedding-test"

    def __init__(self, values: list[float]) -> None:
        self.values = values
        self.calls: list[str] = []

    def embed_text(self, text: str) -> EmbeddingResponse:
        self.calls.append(text)
        return EmbeddingResponse(values=self.values, model_name=self.model_name, input_units=250)


class FakeSession:
    def __init__(self, existing: Embedding | None = None) -> None:
        self.existing = existing
        self.items: list[object] = []
        self.commit_count = 0

    def scalar(self, statement: object) -> Embedding | None:
        del statement
        return self.existing

    def add(self, item: object) -> None:
        self.items.append(item)

    def add_all(self, items: list[object]) -> None:
        self.items.extend(items)

    def commit(self) -> None:
        self.commit_count += 1


def test_post_embedding_persists_vector_and_model_call() -> None:
    session = FakeSession()
    provider = FakeProvider([0.01] * EMBEDDING_DIMENSIONS)
    post_id = uuid.uuid4()

    embedded = embed_post_if_needed(
        cast(object, session),
        post_id,
        "A red fox in a snowy forest",
        provider,
        Settings(gemini_embedding_input_cost_per_million_units=Decimal("2")),
    )

    embedding = next(item for item in session.items if isinstance(item, Embedding))
    model_call = next(item for item in session.items if isinstance(item, ModelCall))
    assert embedded is True
    assert provider.calls == ["A red fox in a snowy forest"]
    assert embedding.post_id == post_id
    assert embedding.content_sha256 == content_checksum("A red fox in a snowy forest")
    assert len(embedding.embedding) == EMBEDDING_DIMENSIONS
    assert model_call.operation == ModelOperation.EMBEDDING
    assert model_call.status == ModelCallStatus.SUCCEEDED
    assert model_call.input_units == 250
    assert model_call.estimated_cost_usd == Decimal("0.000500")


def test_existing_embedding_skips_duplicate_provider_call() -> None:
    session = FakeSession(existing=Embedding())
    provider = FakeProvider([0.01] * EMBEDDING_DIMENSIONS)

    embedded = embed_post_if_needed(
        cast(object, session), uuid.uuid4(), "A red fox", provider, Settings()
    )

    assert embedded is True
    assert provider.calls == []
    assert session.items == []


def test_invalid_embedding_dimension_records_failed_call() -> None:
    session = FakeSession()
    provider = FakeProvider([0.01, 0.02])
    post_id = uuid.uuid4()

    embedded = embed_post_if_needed(
        cast(object, session), post_id, "A red fox", provider, Settings()
    )

    model_call = next(item for item in session.items if isinstance(item, ModelCall))
    assert embedded is False
    assert model_call.post_id == post_id
    assert model_call.status == ModelCallStatus.FAILED


def test_embedding_cost_uses_configured_free_tier_rate() -> None:
    assert estimated_embedding_cost_usd(1_000_000, Settings()) == Decimal("0")
    configuration = Settings(gemini_embedding_input_cost_per_million_units=Decimal("3"))
    assert estimated_embedding_cost_usd(1_000_000, configuration) == Decimal("3")


class FakeImageTextResult:
    def all(self) -> list[str]:
        return ["red fox", "snow", "wildlife"]


class FakeImageTextSession:
    def scalar(self, statement: object) -> object:
        del statement
        return type("Metadata", (), {"caption": "A red fox in snow."})()

    def scalars(self, statement: object) -> FakeImageTextResult:
        del statement
        return FakeImageTextResult()


def test_image_embedding_input_combines_caption_and_sorted_tags() -> None:
    text = image_embedding_text(cast(object, FakeImageTextSession()), uuid.uuid4())

    assert text == "A red fox in snow.\nTags: red fox, snow, wildlife"


class BudgetBlockedSession:
    def __init__(self) -> None:
        self.scalar_calls = 0
        self.items: list[object] = []

    def scalar(self, statement: object) -> object:
        del statement
        self.scalar_calls += 1
        return None if self.scalar_calls == 1 else Decimal("1.00")

    def add_all(self, items: list[object]) -> None:
        self.items.extend(items)

    def add(self, item: object) -> None:
        self.items.append(item)

    def commit(self) -> None:
        return None


def test_embedding_budget_guard_skips_provider_call() -> None:
    session = BudgetBlockedSession()
    provider = FakeProvider([0.01] * EMBEDDING_DIMENSIONS)

    embedded = embed_post_if_needed(
        cast(object, session),
        uuid.uuid4(),
        "A red fox in a snowy forest",
        provider,
        Settings(ai_cost_budget_usd=Decimal("1.00")),
    )

    assert embedded is False
    assert provider.calls == []
    assert session.items == []
