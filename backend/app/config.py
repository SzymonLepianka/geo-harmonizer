from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str = "change_me"
    database_url: str = (
        "postgresql+psycopg://geoharmonizer:geoharmonizer_password@localhost:5432/"
        "geoharmonizer"
    )
    admin_email: str = "admin@example.com"
    admin_password: str = "admin12345"
    cors_origins: str = "http://localhost:5173"
    session_hours: int = 8
    max_upload_mb: int = 200
    wfs_timeout_seconds: int = 60
    max_wfs_mb: int = 100
    max_catalog_features: int = 20_000

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", ROOT_DIR / "backend" / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("secret_key")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("SECRET_KEY nie może być pusty")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def secure_cookie(self) -> bool:
        return self.app_env.lower() not in {"development", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
