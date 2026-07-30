from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PortfolioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    base_currency: str
    created_at: datetime
    updated_at: datetime


class PortfolioListResponse(BaseModel):
    items: list[PortfolioResponse]
    total: int
    skip: int
    limit: int
