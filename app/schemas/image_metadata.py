from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from app.schemas.common import normalize_label


class TagPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    label: str = Field(min_length=1, max_length=100)
    confidence: float = Field(ge=0, le=1)

    @field_validator("label")
    @classmethod
    def normalize_tag_label(cls, value: str) -> str:
        return normalize_label(value)


class PrimarySubjectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    label: str = Field(min_length=1, max_length=100)
    scientific_name: str | None = Field(default=None, max_length=200)
    confidence: float = Field(ge=0, le=1)

    @field_validator("label")
    @classmethod
    def normalize_subject_label(cls, value: str) -> str:
        return normalize_label(value)

    @field_validator("scientific_name")
    @classmethod
    def normalize_scientific_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class ImageMetadataPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: StrictInt = Field(ge=1, le=1)
    caption: str = Field(min_length=1, max_length=500)
    primary_subject: PrimarySubjectPayload
    tags: list[TagPayload] = Field(min_length=1, max_length=10)
    overall_confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def tags_are_unique(self) -> "ImageMetadataPayload":
        labels = [tag.label for tag in self.tags]
        if len(labels) != len(set(labels)):
            raise ValueError("tags must have unique normalized labels")
        return self
