from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str
    full_name: str | None
    preferred_currency: str
    risk_profile: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
