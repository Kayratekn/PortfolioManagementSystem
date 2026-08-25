from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class HoldingResponse(BaseModel):
    asset_id: int
    asset_code: str
    asset_name: str
    asset_type: str
    fund_kind: str | None
    currency: str | None
    data_source: str
    quantity: Decimal


class HoldingListResponse(BaseModel):
    items: list[HoldingResponse]
    total: int