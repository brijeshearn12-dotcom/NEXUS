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
    indian_kanoon_api_token: str = ""
    indian_kanoon_api_key: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    next_public_api_base_url: str = "http://localhost:8000"
    frontend_url: str = "https://nexus-frontend-qtak.onrender.com"
    cors_origins: str = (
        "https://nexus-frontend-qtak.onrender.com," "http://localhost:3000," "http://127.0.0.1:3000"
    )
    app_name: str = "NEXUS — Criminal Network Analysis API"
    debug: bool = False
    low_yield_min_entities_per_1000_chars: float = 0.5

    @property
    def allowed_cors_origins(self) -> list[str]:
        origins: set[str] = {
            "https://nexus-frontend-qtak.onrender.com",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        }
        if self.frontend_url:
            cleaned_frontend = self.frontend_url.strip().rstrip("/")
            if cleaned_frontend and cleaned_frontend != "*":
                origins.add(cleaned_frontend)
        if self.cors_origins:
            for item in self.cors_origins.split(","):
                cleaned = item.strip().rstrip("/")
                if cleaned and cleaned != "*":
                    origins.add(cleaned)
        return sorted(origins)


settings = Settings()
