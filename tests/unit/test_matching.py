from __future__ import annotations

import uuid
from decimal import Decimal
from typing import cast

from sqlalchemy.dialects import postgresql

from app.core.config import Settings
from app.db.models import DatasetLabel, Embedding, Image, ImageMetadata, ImageProcessingStatus, Post
from app.services.matching import (
    RankedCandidate,
    guard_candidate,
    rank_candidates,
    recognize_subject,
)


def build_candidate(
    subject: str, scientific_name: str | None, similarity: float
) -> RankedCandidate:
    image = Image(
        id=uuid.uuid4(),
        file_path=f"data/corpus/raw/{subject}/example.jpg",
        sha256="a" * 64,
        dataset_label=DatasetLabel.WOLF if subject == "wolf" else DatasetLabel.RED_FOX,
        source_url="https://example.test/source",
        license_url="https://example.test/license",
        processing_status=ImageProcessingStatus.ACCEPTED,
    )
    metadata = ImageMetadata(
        image_id=image.id,
        schema_version=1,
        caption=f"A {subject} in snow.",
        primary_subject=subject,
        scientific_name=scientific_name,
        overall_confidence=Decimal("0.95"),
    )
    return RankedCandidate(image=image, metadata=metadata, similarity_score=similarity)


def test_taxonomy_recognizes_scientific_name_alias() -> None:
    assert recognize_subject("A Vulpes vulpes in snow") == "red fox"
    assert recognize_subject("A domestic dog in a park") == "dog"
    assert recognize_subject("An unidentified animal") is None


def test_guard_rejects_wolf_for_red_fox_post_with_required_explanation() -> None:
    post = Post(text="A red fox in a snowy forest", recognized_subject="red fox")
    candidate = build_candidate("wolf", "Canis lupus", 0.99)

    reason = guard_candidate(post, candidate, Settings())

    assert reason == (
        "subject_mismatch",
        "Rejected because the post requests red fox, while the image primary subject is wolf.",
    )


def test_guard_accepts_equivalent_red_fox_subject() -> None:
    post = Post(
        text="A Vulpes vulpes in snow", recognized_subject=recognize_subject("Vulpes vulpes")
    )
    candidate = build_candidate("red fox", "Vulpes vulpes", 0.90)

    assert guard_candidate(post, candidate, Settings()) is None


def test_guard_rejects_low_similarity_candidate() -> None:
    post = Post(text="A red fox in snow", recognized_subject="red fox")
    candidate = build_candidate("red fox", "Vulpes vulpes", 0.74)

    reason = guard_candidate(post, candidate, Settings(minimum_similarity_score=0.75))

    assert reason is not None
    assert reason[0] == "similarity_below_threshold"


class FakeResult:
    def __init__(self, rows: list[tuple[Image, ImageMetadata, float]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[Image, ImageMetadata, float]]:
        return self.rows


class FakeSession:
    def execute(self, statement: object) -> FakeResult:
        statement.compile(dialect=postgresql.dialect())
        red_fox = build_candidate("red fox", "Vulpes vulpes", 0.0)
        wolf = build_candidate("wolf", "Canis lupus", 0.0)
        return FakeResult(
            [(red_fox.image, red_fox.metadata, 0.10), (wolf.image, wolf.metadata, 0.20)]
        )


def test_similarity_ranking_converts_cosine_distance_and_orders_candidates() -> None:
    post_embedding = Embedding(
        post_id=uuid.uuid4(),
        model_name="gemini-test",
        content_sha256="b" * 64,
        embedding=[0.1] * 768,
    )

    candidates = rank_candidates(cast(object, FakeSession()), post_embedding, Settings())

    assert [candidate.metadata.primary_subject for candidate in candidates] == ["red fox", "wolf"]
    assert [candidate.similarity_score for candidate in candidates] == [0.9, 0.8]
