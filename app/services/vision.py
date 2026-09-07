from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from google import genai
from google.genai import types

from app.core.config import Settings

VISION_PROMPT = (
    "Analyze this image for an image-relevance corpus. Return only JSON that follows the supplied "
    "schema. Describe the visible scene in caption. Identify the most specific primary subject. "
    "Use lowercase normalized labels and include an optional scientific name only when you are "
    "confident. "
    "provide one to ten distinct tags, and set every confidence from 0.0 through 1.0."
)

VISION_RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "schema_version": types.Schema(type=types.Type.INTEGER, minimum=1, maximum=1),
        "caption": types.Schema(type=types.Type.STRING),
        "primary_subject": types.Schema(
            type=types.Type.OBJECT,
            properties={
                "label": types.Schema(type=types.Type.STRING),
                "scientific_name": types.Schema(type=types.Type.STRING, nullable=True),
                "confidence": types.Schema(type=types.Type.NUMBER, minimum=0, maximum=1),
            },
            required=["label", "confidence"],
        ),
        "tags": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "label": types.Schema(type=types.Type.STRING),
                    "confidence": types.Schema(type=types.Type.NUMBER, minimum=0, maximum=1),
                },
                required=["label", "confidence"],
            ),
            min_items=1,
            max_items=10,
        ),
        "overall_confidence": types.Schema(type=types.Type.NUMBER, minimum=0, maximum=1),
    },
    required=["schema_version", "caption", "primary_subject", "tags", "overall_confidence"],
)


@dataclass(frozen=True)
class VisionResponse:
    raw_response: str
    model_name: str
    input_units: int
    output_units: int


class VisionProviderError(RuntimeError):
    def __init__(self, message: str, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class VisionProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    def analyze_image(self, image_path: Path) -> VisionResponse: ...


class GeminiVisionProvider:
    def __init__(self, configuration: Settings) -> None:
        if configuration.gemini_api_key is None:
            raise ValueError("GEMINI_API_KEY must be configured for image processing")
        if not configuration.gemini_vision_model:
            raise ValueError("GEMINI_VISION_MODEL must be configured for image processing")

        self._client = genai.Client(api_key=configuration.gemini_api_key.get_secret_value())
        self._model_name = configuration.gemini_vision_model

    @property
    def model_name(self) -> str:
        return self._model_name

    def analyze_image(self, image_path: Path) -> VisionResponse:
        mime_type = _image_mime_type(image_path)
        try:
            image_bytes = image_path.read_bytes()
        except OSError as error:
            raise VisionProviderError(str(error), retryable=False) from error

        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=[
                    VISION_PROMPT,
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=VISION_RESPONSE_SCHEMA,
                ),
            )
        except Exception as error:
            raise VisionProviderError(
                str(error), retryable=_is_retryable_provider_error(error)
            ) from error

        usage = response.usage_metadata
        return VisionResponse(
            raw_response=response.text or "",
            model_name=self.model_name,
            input_units=(usage.prompt_token_count if usage and usage.prompt_token_count else 0),
            output_units=(
                usage.candidates_token_count if usage and usage.candidates_token_count else 0
            ),
        )


def _image_mime_type(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    try:
        return mime_types[suffix]
    except KeyError as error:
        raise VisionProviderError(f"Unsupported image type: {suffix}", retryable=False) from error


def _is_retryable_provider_error(error: Exception) -> bool:
    message = str(error).lower()
    return any(
        marker in message
        for marker in ("429", "rate limit", "timeout", "connection", "500", "502", "503", "504")
    )
