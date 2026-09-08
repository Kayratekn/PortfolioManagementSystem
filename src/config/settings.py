from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Portfolio Management System"
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:4173",
            "http://localhost:4173",
        ]
    )

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
    tcmb_base_url: str = Field(default="https://www.tcmb.gov.tr")
    tcmb_timeout_seconds: float = Field(default=30.0, gt=0)
    tcmb_max_retries: int = Field(default=3, ge=0)
    tcmb_retry_wait_seconds: float = Field(default=10.0, ge=0)
    ai_service_url: str = Field(default="http://127.0.0.1:8001")
    ai_timeout_seconds: float = Field(default=15.0, gt=0)
    report_storage_dir: Path = Field(default=Path("data/reports"))
    report_max_file_size_bytes: int = Field(default=10485760, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
