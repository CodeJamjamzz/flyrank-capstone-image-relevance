from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://metering:metering@localhost:5432/metering"
    gemini_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    gemini_vision_model: str | None = None
    groq_vision_model: str | None = None
    embedding_model: str = "gemini-embedding-001"
    minimum_image_confidence: float = 0.70
    minimum_similarity_score: float = 0.75
    maximum_processing_attempts: int = 3


settings = Settings()
