from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Portfolio Management System"
    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/ai_portfolio"
    )
    jwt_secret_key: str = Field(default="change-this-secret-in-env")
    jwt_access_token_expire_minutes: int = Field(default=60)
    jwt_issuer: str = Field(default="portfolio-management-system")
    tefas_base_url: str = Field(default="https://www.tefas.gov.tr")
    tefas_timeout_seconds: float = Field(default=30.0, gt=0)
    tefas_max_retries: int = Field(default=3, ge=0)
    tefas_retry_wait_seconds: float = Field(default=10.0, ge=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
