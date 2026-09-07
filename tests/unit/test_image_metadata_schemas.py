import pytest
from google.genai import types
from pydantic import ValidationError

from app.schemas.image_metadata import ImageMetadataPayload
from app.services.vision import VISION_RESPONSE_SCHEMA


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
    [("schema_version", 2), ("schema_version", "1"), ("overall_confidence", 1.01), ("caption", "")],
)
def test_invalid_metadata_fields_are_rejected(field: str, value: object) -> None:
    payload = valid_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        ImageMetadataPayload.model_validate(payload)


def test_schema_version_uses_gemini_compatible_integer_constraints() -> None:
    schema = ImageMetadataPayload.model_json_schema()
    schema_version = schema["properties"]["schema_version"]

    assert schema_version == {
        "maximum": 1,
        "minimum": 1,
        "title": "Schema Version",
        "type": "integer",
    }


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


def test_gemini_response_schema_avoids_unsupported_pydantic_conversion_fields() -> None:
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=VISION_RESPONSE_SCHEMA,
    )
    request_config = config.model_dump(by_alias=True, exclude_none=True)

    assert "responseSchema" in request_config
    assert "responseJsonSchema" not in request_config
    assert "additionalProperties" not in str(request_config["responseSchema"])
    assert "minLength" not in str(request_config["responseSchema"])
    assert "maxLength" not in str(request_config["responseSchema"])
