from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ALLOWED_CURRENCIES = {"TRY", "USD", "EUR", "GBP"}


class PortfolioCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    base_currency: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value:
            raise ValueError("String should have at least 1 character")
        return value

    @field_validator("base_currency")
    @classmethod
    def validate_base_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized_value = value.upper()
        if normalized_value not in ALLOWED_CURRENCIES:
            raise ValueError("Base currency must be one of TRY, USD, EUR or GBP.")
        return normalized_value


class PortfolioUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=100)
    base_currency: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value:
            raise ValueError("String should have at least 1 character")
        return value

    @field_validator("base_currency")
    @classmethod
    def validate_base_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized_value = value.upper()
        if normalized_value not in ALLOWED_CURRENCIES:
            raise ValueError("Base currency must be one of TRY, USD, EUR or GBP.")
        return normalized_value

    @model_validator(mode="before")
    @classmethod
    def validate_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        if not data:
            raise ValueError("At least one field must be provided.")

        for field_name in ("name", "base_currency"):
            if field_name in data and data[field_name] is None:
                raise ValueError(f"{field_name} cannot be null.")

        return data
