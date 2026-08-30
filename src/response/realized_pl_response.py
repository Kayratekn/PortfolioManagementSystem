from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class RealizedPlItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: int
    asset_code: str
    asset_name: str
    asset_currency: str | None
    status: str
    unavailable_reason: str | None
    sold_quantity: Decimal
    realized_proceeds: Decimal | None
    realized_cost_basis: Decimal | None
    native_realized_pl: Decimal | None


class RealizedPlResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: int
    as_of_date: date
    status: str
    items: list[RealizedPlItemResponse]
