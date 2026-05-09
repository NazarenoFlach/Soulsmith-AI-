from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SoulSmith AI"
    api_prefix: str = "/api"
    environment: str = "development"

    openai_api_key: str | None = None
    openai_model: str = "gpt-5.4-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    request_timeout_seconds: int = 45

    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    app_dir: Path = Path(__file__).resolve().parents[1]
    project_dir: Path = Path(__file__).resolve().parents[2]
    chroma_dir: Path = Path(__file__).resolve().parents[2] / ".chroma"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def data_dir(self) -> Path:
        return self.app_dir / "data"


@lru_cache
def get_settings() -> Settings:
    return Settings()
