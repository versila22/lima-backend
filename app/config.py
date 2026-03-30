"""Application configuration via environment variables."""

from functools import lru_cache
from typing import List, Optional, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://lima:password@localhost:5432/lima_db"

    # JWT
    JWT_SECRET: str = "insecure_dev_secret_change_me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # App
    APP_ENV: str = "development"
    DEBUG: bool = True
    FRONTEND_URL: str = "http://localhost:5173"

    # CORS
    CORS_ORIGINS: Union[str, List[str]] = "*"

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "LIMA <noreply@lima-impro.fr>"
    EMAIL_ENABLED: bool = False

    # Server
    PORT: int = 8000

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if v == "*":
            return ["*"]
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def sync_database_url(self) -> str:
        """Synchronous URL for Alembic migrations."""
        return self.DATABASE_URL.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
