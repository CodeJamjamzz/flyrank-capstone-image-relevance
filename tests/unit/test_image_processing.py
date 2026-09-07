from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    AttemptStatus,
    DatasetLabel,
    Image,
    ImageMetadata,
    ImageProcessingStatus,
    ImageTag,
    ModelCall,
    ProcessingAttempt,
    Tag,
)
from app.services import image_processing
from app.services.image_processing import estimated_cost_usd, process_next_image, retry_delay
from app.services.vision import VisionProviderError, VisionResponse


class FakeSession:
    def __init__(self, image: Image, attempt: ProcessingAttempt) -> None:
        self.image = image
        self.attempt = attempt
        self.items: list[object] = []
        self.commit_count = 0
        self.tag = Tag(id=uuid.uuid4(), normalized_label="red fox")

    def get(self, model: type[object], identifier: uuid.UUID) -> object | None:
        if model is Image and identifier == self.image.id:
            return self.image
        if model is ProcessingAttempt and identifier == self.attempt.id:
            return self.attempt
        return None

    def add(self, item: object) -> None:
        self.items.append(item)

    def execute(self, statement: object) -> None:
        del statement

    def scalar(self, statement: object) -> Tag:
        del statement
        return self.tag

    def commit(self) -> None:
        self.commit_count += 1


class FakeProvider:
    model_name = "gemini-test-flash"

    def __init__(self, response: str) -> None:
        self.response = response

    def analyze_image(self, image_path: Path) -> VisionResponse:
        assert image_path.is_file()
        return VisionResponse(
            raw_response=self.response,
            model_name=self.model_name,
            input_units=100,
            output_units=20,
        )


def metadata_json(confidence: float = 0.95) -> str:
    return (
        "{"
        '"schema_version":1,'
        '"caption":"A red fox in snow.",'
        '"primary_subject":{"label":"red fox","scientific_name":"Vulpes vulpes",'
        '"confidence":0.95},'
        '"tags":[{"label":"red fox","confidence":0.95}],'
        f'"overall_confidence":{confidence}'
        "}"
    )


def build_image() -> Image:
    return Image(
        id=uuid.uuid4(),
        file_path="data/corpus/raw/red_fox/red_fox_001.jpg",
        sha256="a" * 64,
        dataset_label=DatasetLabel.RED_FOX,
        source_url="https://images.pexels.com/example",
        license_url="https://www.pexels.com/license/",
        processing_status=ImageProcessingStatus.PROCESSING,
        retry_count=1,
    )


def build_attempt(image: Image) -> ProcessingAttempt:
    return ProcessingAttempt(
        id=uuid.uuid4(),
        image_id=image.id,
        attempt_number=1,
        status=AttemptStatus.STARTED,
    )


@pytest.mark.parametrize(
    ("confidence", "expected_status"),
    [
        (0.95, ImageProcessingStatus.ACCEPTED),
        (0.50, ImageProcessingStatus.NEEDS_REVIEW),
    ],
)
def test_process_next_image_persists_valid_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    confidence: float,
    expected_status: ImageProcessingStatus,
) -> None:
    image_path = tmp_path / "data/corpus/raw/red_fox/red_fox_001.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"image-content")
    image = build_image()
    attempt = build_attempt(image)
    session = FakeSession(image, attempt)
    claimed = image_processing.ClaimedImage(image.id, attempt.id, image.file_path)
    monkeypatch.setattr(image_processing, "claim_next_image", lambda _: claimed)

    processed = process_next_image(
        cast(Session, session),
        FakeProvider(metadata_json(confidence)),
        Settings(),
        tmp_path,
    )

    assert processed.processed is True
    assert image.processing_status == expected_status
    assert attempt.status == AttemptStatus.SUCCEEDED
    assert any(isinstance(item, ImageMetadata) for item in session.items)
    assert any(isinstance(item, ImageTag) for item in session.items)
    assert any(isinstance(item, ModelCall) for item in session.items)
    assert (image.accepted_at is not None) is (expected_status == ImageProcessingStatus.ACCEPTED)


def test_invalid_model_output_schedules_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image_path = tmp_path / "data/corpus/raw/red_fox/red_fox_001.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"image-content")
    image = build_image()
    attempt = build_attempt(image)
    session = FakeSession(image, attempt)
    claimed = image_processing.ClaimedImage(image.id, attempt.id, image.file_path)
    monkeypatch.setattr(image_processing, "claim_next_image", lambda _: claimed)

    process_next_image(cast(Session, session), FakeProvider("not-json"), Settings(), tmp_path)

    assert image.processing_status == ImageProcessingStatus.RETRY_SCHEDULED
    assert attempt.status == AttemptStatus.RETRY_SCHEDULED
    assert attempt.retry_at is not None
    assert any(isinstance(item, ModelCall) for item in session.items)


def test_retry_and_cost_rules_are_visible() -> None:
    configuration = Settings(
        gemini_vision_input_cost_per_million_units=Decimal("2"),
        gemini_vision_output_cost_per_million_units=Decimal("3"),
    )

    assert retry_delay(1).total_seconds() == 60
    assert retry_delay(2).total_seconds() == 300
    assert estimated_cost_usd(1_000_000, 1_000_000, configuration) == Decimal("5")


class ErrorProvider:
    model_name = "gemini-test-flash"

    def __init__(self, error: VisionProviderError) -> None:
        self.error = error

    def analyze_image(self, image_path: Path) -> VisionResponse:
        del image_path
        raise self.error


def test_rate_limit_defers_image_without_marking_it_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image_path = tmp_path / "data/corpus/raw/red_fox/red_fox_001.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"image-content")
    image = build_image()
    image.retry_count = 3
    attempt = build_attempt(image)
    session = FakeSession(image, attempt)
    claimed = image_processing.ClaimedImage(image.id, attempt.id, image.file_path)
    monkeypatch.setattr(image_processing, "claim_next_image", lambda _: claimed)

    outcome = process_next_image(
        cast(Session, session),
        ErrorProvider(VisionProviderError("429 rate limit", retryable=True, rate_limited=True)),
        Settings(image_worker_rate_limit_backoff_seconds=3600),
        tmp_path,
    )

    assert outcome.processed is True
    assert outcome.rate_limited is True
    assert image.processing_status == ImageProcessingStatus.RETRY_SCHEDULED
    assert image.next_retry_at is not None
    assert attempt.status == AttemptStatus.RETRY_SCHEDULED


def test_permanent_provider_failure_is_logged_and_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    image_path = tmp_path / "data/corpus/raw/red_fox/red_fox_001.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"image-content")
    image = build_image()
    image.retry_count = 3
    attempt = build_attempt(image)
    session = FakeSession(image, attempt)
    claimed = image_processing.ClaimedImage(image.id, attempt.id, image.file_path)
    monkeypatch.setattr(image_processing, "claim_next_image", lambda _: claimed)

    outcome = process_next_image(
        cast(Session, session),
        ErrorProvider(VisionProviderError("unsupported image", retryable=False)),
        Settings(),
        tmp_path,
    )

    assert outcome.processed is True
    assert image.processing_status == ImageProcessingStatus.FAILED
    assert attempt.status == AttemptStatus.FAILED
    assert "Image processing permanently failed" in caplog.text
