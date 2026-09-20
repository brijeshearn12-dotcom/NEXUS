"""Application configuration — reads from the single root-level .env file."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Root of the repo is three levels up from this file:
# backend/app/core/config.py → backend/app/core → backend/app → backend → NEXUS/
ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_ENV),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mongodb_uri: str = ""
    indian_kanoon_api_key: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    next_public_api_base_url: str = "http://localhost:8000"
    app_name: str = "SIH26189GREEN — Criminal Network Analysis API"
    debug: bool = False


settings = Settings()
