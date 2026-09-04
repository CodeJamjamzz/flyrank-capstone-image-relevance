import pytest
from pydantic import ValidationError

from app.schemas.image_metadata import ImageMetadataPayload


def valid_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "caption": "A red fox standing in a snowy forest.",
        "primary_subject": {
            "label": " Red Fox ",
            "scientific_name": "Vulpes vulpes",
            "confidence": 0.96,
        },
        "tags": [
            {"label": "Red Fox", "confidence": 0.98},
            {"label": "Snow", "confidence": 0.93},
        ],
        "overall_confidence": 0.95,
    }


def test_valid_metadata_is_normalized() -> None:
    metadata = ImageMetadataPayload.model_validate(valid_payload())

    assert metadata.primary_subject.label == "red fox"
    assert [tag.label for tag in metadata.tags] == ["red fox", "snow"]


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_version", 2), ("overall_confidence", 1.01), ("caption", "")],
)
def test_invalid_metadata_fields_are_rejected(field: str, value: object) -> None:
    payload = valid_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        ImageMetadataPayload.model_validate(payload)


def test_duplicate_normalized_tags_are_rejected() -> None:
    payload = valid_payload()
    payload["tags"] = [
        {"label": "Red Fox", "confidence": 0.98},
        {"label": " red   fox ", "confidence": 0.90},
    ]

    with pytest.raises(ValidationError, match="unique normalized labels"):
        ImageMetadataPayload.model_validate(payload)


def test_unknown_metadata_field_is_rejected() -> None:
    payload = valid_payload()
    payload["untrusted"] = "value"

    with pytest.raises(ValidationError):
        ImageMetadataPayload.model_validate(payload)
