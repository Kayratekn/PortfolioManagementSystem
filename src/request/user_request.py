from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
