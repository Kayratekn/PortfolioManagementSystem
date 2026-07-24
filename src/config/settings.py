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
    jwt_secret_key: str = Field(default="change-this-secret-in-env")
    jwt_access_token_expire_minutes: int = Field(default=60)
    jwt_issuer: str = Field(default="portfolio-management-system")


@lru_cache
def get_settings() -> Settings:
    return Settings()
