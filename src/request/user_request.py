from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class UserCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    preferred_currency: str = Field(default="TRY", min_length=3, max_length=3)
    risk_profile: str | None = Field(default=None, max_length=50)


class UserLoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred_currency: str | None = None
    risk_profile: str | None = Field(default=None, max_length=50)

    @field_validator("preferred_currency", mode="before")
    @classmethod
    def normalize_preferred_currency(cls, value: object) -> object:
        if value is None:
            raise ValueError("Preferred currency cannot be null.")
        if not isinstance(value, str):
            return value

        normalized_value = value.strip().upper()
        if normalized_value not in {"TRY", "USD", "EUR", "GBP"}:
            raise ValueError("Unsupported preferred currency.")
        return normalized_value

    @field_validator("risk_profile", mode="before")
    @classmethod
    def normalize_risk_profile(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value

        normalized_value = value.strip().casefold()
        aliases = {
            "conservative": "muhafazakar",
            "low": "muhafazakar",
            "dusuk": "muhafazakar",
            "düşük": "muhafazakar",
            "defansif": "muhafazakar",
            "muhafazakar": "muhafazakar",
            "moderate": "dengeli",
            "balanced": "dengeli",
            "medium": "dengeli",
            "orta": "dengeli",
            "dengeli": "dengeli",
            "aggressive": "agresif",
            "high": "agresif",
            "yuksek": "agresif",
            "yüksek": "agresif",
            "dinamik": "agresif",
            "agresif": "agresif",
        }
        canonical_value = aliases.get(normalized_value)
        if canonical_value is None:
            raise ValueError("Unsupported risk profile.")
        return canonical_value

    @model_validator(mode="after")
    def require_at_least_one_update(self) -> "UserUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one profile field must be provided.")
        return self
