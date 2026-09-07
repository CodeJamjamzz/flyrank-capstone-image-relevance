from decimal import Decimal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://metering:metering@localhost:5432/metering"
    gemini_api_key: SecretStr | None = None
    gemini_vision_model: str | None = None
    embedding_model: str = "gemini-embedding-001"
    minimum_image_confidence: float = 0.70
    minimum_similarity_score: float = 0.75
    maximum_processing_attempts: int = 3
    image_worker_poll_interval_seconds: int = 5
    image_worker_processing_delay_seconds: int = Field(default=30, ge=0)
    image_worker_rate_limit_backoff_seconds: int = Field(default=3600, ge=60)
    gemini_vision_input_cost_per_million_units: Decimal = Decimal("0")
    gemini_vision_output_cost_per_million_units: Decimal = Decimal("0")
    gemini_embedding_input_cost_per_million_units: Decimal = Decimal("0")
    maximum_suggestions: int = Field(default=3, ge=1)


settings = Settings()
