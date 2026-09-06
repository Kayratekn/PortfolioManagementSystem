from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WatchlistItemResponse(BaseModel):
    id: int
    asset_id: int
    asset_code: str
    asset_name: str
    asset_type: str
    fund_kind: str | None
    isin: str | None
    currency: str | None
    data_source: str
    created_at: datetime


class WatchlistResponse(BaseModel):
    items: list[WatchlistItemResponse]
    total: int
    skip: int
    limit: int
