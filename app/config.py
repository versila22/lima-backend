"""Application configuration via environment variables."""

from functools import lru_cache
from typing import List, Union

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_JWT_SECRET = "insecure_dev_secret_change_me"
DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://localhost:5173"


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
    JWT_SECRET: str = DEFAULT_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # App
    APP_ENV: str = "development"
    DEBUG: bool = False
    FRONTEND_URL: str = "https://improv-cabaret-planner.lovable.app"

    # CORS
    # Production must set CORS_ORIGINS explicitly via environment variables.
    CORS_ORIGINS: Union[str, List[str]] = DEFAULT_CORS_ORIGINS

    # Email
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@lima.asso.fr"
    SMTP_TLS: bool = True

    # Server
    PORT: int = 8000

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> "Settings":
        if self.JWT_SECRET == DEFAULT_JWT_SECRET and not self.DEBUG:
            raise ValueError(
                "JWT_SECRET uses the insecure default value. "
                "Set JWT_SECRET in the environment before starting outside debug mode."
            )
        return self

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
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
