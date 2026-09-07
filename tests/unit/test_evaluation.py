from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.evaluation import EvaluationCase, EvaluationCaseResult, EvaluationDataset
from app.services import evaluation
from app.services.evaluation import EvaluationReadinessError, _expected_images, run_evaluation


def build_case(case_id: str) -> EvaluationCase:
    return EvaluationCase(
        id=case_id,
        post_text=f"Evaluation case {case_id}",
        expected_image_path="data/corpus/raw/red_fox/red_fox_003.jpg",
        expected_subject="Red Fox",
    )


def test_evaluation_dataset_requires_ten_cases() -> None:
    with pytest.raises(ValidationError):
        EvaluationDataset(schema_version=1, cases=[build_case("one")])


def test_evaluation_dataset_rejects_duplicate_case_ids() -> None:
    cases = [build_case(f"case_{index}") for index in range(10)]
    cases[-1] = build_case("case_0")

    with pytest.raises(ValidationError, match="must be unique"):
        EvaluationDataset(schema_version=1, cases=cases)


def test_evaluation_dataset_rejects_unknown_fields() -> None:
    payload = {
        "schema_version": 1,
        "cases": [
            {
                "id": f"case_{index}",
                "post_text": "A red fox",
                "expected_image_path": "data/corpus/raw/red_fox/red_fox_003.jpg",
                "expected_subject": "red fox",
                "unexpected": True,
            }
            for index in range(10)
        ],
    }

    with pytest.raises(ValidationError):
        EvaluationDataset.model_validate(payload)


class EmptySession:
    def scalars(self, statement: object) -> list[object]:
        del statement
        return []


def test_readiness_rejects_unavailable_expected_images() -> None:
    dataset = EvaluationDataset(
        schema_version=1, cases=[build_case(f"case_{index}") for index in range(10)]
    )

    with pytest.raises(EvaluationReadinessError, match="accepted and embedded"):
        _expected_images(cast(object, EmptySession()), dataset)


def test_evaluation_scores_top_one_precision(monkeypatch: pytest.MonkeyPatch) -> None:
    dataset = EvaluationDataset(
        schema_version=1, cases=[build_case(f"case_{index}") for index in range(10)]
    )
    expected_images = {case.expected_image_path: cast(object, object()) for case in dataset.cases}
    monkeypatch.setattr(evaluation, "_expected_images", lambda *args: expected_images)
    results = [
        EvaluationCaseResult(
            case_id=case.id,
            expected_image_path=case.expected_image_path,
            expected_subject=case.expected_subject,
            top_image_path=case.expected_image_path if index < 7 else None,
            top_suggestion_status="pending_review" if index < 7 else None,
            passed=index < 7,
            rejection_reasons=[],
        )
        for index, case in enumerate(dataset.cases)
    ]
    monkeypatch.setattr(evaluation, "_evaluate_case", lambda *args: results.pop(0))

    report = run_evaluation(cast(object, object()), dataset, cast(object, object()), Settings())

    assert report.correct_top_1 == 7
    assert report.total_cases == 10
    assert report.top_1_precision == 0.7


def test_evaluation_dataset_file_is_valid() -> None:
    dataset = evaluation.load_evaluation_dataset(Path("data/evaluation/post_image_relevance.json"))

    assert dataset.schema_version == 1
    assert len(dataset.cases) == 10
