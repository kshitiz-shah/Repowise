from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration owned by the AI service, loaded from its local .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "repowise-ai-service"
    environment: str = "development"
    ai_service_port: int = Field(default=5000, ge=1, le=65535)
    ai_service_api_key: SecretStr = Field(min_length=16)

    qdrant_url: str = Field(default="http://localhost:6333", pattern=r"^https?://")
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = Field(default="repowise_code", min_length=1)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_provider: str = Field(default="gemini", pattern=r"^(gemini|groq)$")
    gemini_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.6-flash"
    groq_model: str = "llama-3.3-70b-versatile"


@lru_cache
def get_settings() -> Settings:
    return Settings()
