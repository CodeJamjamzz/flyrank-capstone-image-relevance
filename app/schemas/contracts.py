import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models import DatasetLabel, ReviewDecisionType


class ImageRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    file_path: str = Field(min_length=1, max_length=500)
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    dataset_label: DatasetLabel
    source_url: str = Field(min_length=1)
    license_url: str = Field(min_length=1)

    @field_validator("sha256")
    @classmethod
    def normalize_checksum(cls, value: str) -> str:
        return value.lower()


class PostCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1)


class SuggestionInspectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    post_id: uuid.UUID
    image_id: uuid.UUID | None
    similarity_score: float | None
    status: str
    reason_code: str
    reason_text: str
    created_at: datetime


class ReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: ReviewDecisionType
    reviewer_note: str | None = Field(default=None, max_length=2_000)
