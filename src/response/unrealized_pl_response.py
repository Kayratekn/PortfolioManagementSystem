from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from src.response.market_data_freshness_response import MarketDataFreshnessResponse


class UnrealizedPlItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: int
    asset_code: str
    asset_name: str
    asset_currency: str | None
    status: str
    unavailable_reason: str | None
    quantity: Decimal
    total_cost_basis: Decimal | None
    average_cost_per_unit: Decimal | None
    price: Decimal | None
    price_date: date | None
    price_freshness: MarketDataFreshnessResponse
    price_kind: str | None
    price_source: str | None
    native_market_value: Decimal | None
    native_unrealized_pl: Decimal | None


class UnrealizedPlResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: int
    as_of_date: date
    status: str
    items: list[UnrealizedPlItemResponse]