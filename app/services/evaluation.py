from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Embedding, Image, ImageProcessingStatus, Post, SuggestionStatus
from app.schemas.evaluation import (
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationDataset,
    EvaluationReport,
)
from app.services.embeddings import EmbeddingProvider, embed_post_if_needed
from app.services.matching import create_suggestions_if_needed, recognize_subject


class EvaluationReadinessError(RuntimeError):
    pass


def load_evaluation_dataset(path: Path) -> EvaluationDataset:
    return EvaluationDataset.model_validate_json(path.read_text(encoding="utf-8"))


def run_evaluation(
    session: Session,
    dataset: EvaluationDataset,
    provider: EmbeddingProvider,
    configuration: Settings,
) -> EvaluationReport:
    expected_images = _expected_images(session, dataset)
    results = [
        _evaluate_case(
            session, case, expected_images[case.expected_image_path], provider, configuration
        )
        for case in dataset.cases
    ]
    correct_top_1 = sum(result.passed for result in results)
    return EvaluationReport(
        created_at=datetime.now(UTC),
        total_cases=len(results),
        correct_top_1=correct_top_1,
        top_1_precision=correct_top_1 / len(results),
        cases=results,
    )


def _expected_images(session: Session, dataset: EvaluationDataset) -> dict[str, Image]:
    images = {
        image.file_path: image
        for image in session.scalars(
            select(Image).where(
                Image.file_path.in_([case.expected_image_path for case in dataset.cases])
            )
        )
    }
    unavailable_paths: list[str] = []
    for case in dataset.cases:
        image = images.get(case.expected_image_path)
        if image is None or image.processing_status != ImageProcessingStatus.ACCEPTED:
            unavailable_paths.append(case.expected_image_path)
            continue
        has_embedding = session.scalar(
            select(Embedding.id).where(Embedding.image_id == image.id).limit(1)
        )
        if has_embedding is None:
            unavailable_paths.append(case.expected_image_path)
    if unavailable_paths:
        joined_paths = ", ".join(sorted(set(unavailable_paths)))
        raise EvaluationReadinessError(
            f"Expected images must be accepted and embedded before evaluation: {joined_paths}"
        )
    return images


def _evaluate_case(
    session: Session,
    case: EvaluationCase,
    expected_image: Image,
    provider: EmbeddingProvider,
    configuration: Settings,
) -> EvaluationCaseResult:
    post = Post(text=case.post_text, recognized_subject=recognize_subject(case.post_text))
    session.add(post)
    session.flush()
    if not embed_post_if_needed(session, post.id, post.text, provider, configuration):
        raise RuntimeError(f"Could not create an embedding for evaluation case {case.id}")

    suggestions = create_suggestions_if_needed(session, post.id, configuration)
    top_suggestion = next(
        (
            suggestion
            for suggestion in suggestions
            if suggestion.status == SuggestionStatus.PENDING_REVIEW
        ),
        None,
    )
    top_image = (
        session.get(Image, top_suggestion.image_id)
        if top_suggestion is not None and top_suggestion.image_id is not None
        else None
    )
    return EvaluationCaseResult(
        case_id=case.id,
        expected_image_path=expected_image.file_path,
        expected_subject=case.expected_subject,
        top_image_path=top_image.file_path if top_image is not None else None,
        top_suggestion_status=(top_suggestion.status.value if top_suggestion is not None else None),
        passed=top_image is not None and top_image.file_path == expected_image.file_path,
        rejection_reasons=[
            suggestion.reason_text
            for suggestion in suggestions
            if suggestion.status == SuggestionStatus.REJECTED
        ],
    )
