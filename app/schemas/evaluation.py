from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import normalize_label


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    post_text: str = Field(min_length=1, max_length=5_000)
    expected_image_path: str = Field(pattern=r"^data/corpus/raw/.+\.(jpg|jpeg|png|webp)$")
    expected_subject: str = Field(min_length=1, max_length=100)

    @field_validator("expected_subject")
    @classmethod
    def normalize_subject(cls, value: str) -> str:
        return normalize_label(value)


class EvaluationDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    cases: list[EvaluationCase] = Field(min_length=10)

    @model_validator(mode="after")
    def require_unique_case_ids(self) -> EvaluationDataset:
        case_ids = [case.id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Evaluation case IDs must be unique")
        return self


class EvaluationCaseResult(BaseModel):
    case_id: str
    expected_image_path: str
    expected_subject: str
    top_image_path: str | None
    top_suggestion_status: str | None
    passed: bool
    rejection_reasons: list[str]


class EvaluationReport(BaseModel):
    schema_version: Literal[1] = 1
    created_at: datetime
    total_cases: int
    correct_top_1: int
    top_1_precision: float
    cases: list[EvaluationCaseResult]
