from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from src.response.market_data_freshness_response import MarketDataFreshnessResponse


class PortfolioValuationItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: int
    asset_code: str
    asset_name: str
    quantity: Decimal
    asset_currency: str | None
    status: str
    unavailable_reason: str | None
    price: Decimal | None
    price_date: date | None
    price_freshness: MarketDataFreshnessResponse
    price_kind: str | None
    price_source: str | None
    fx_rate: Decimal | None
    fx_rate_date: date | None
    fx_freshness: MarketDataFreshnessResponse
    fx_rate_kind: str | None
    fx_source: str | None
    native_market_value: Decimal | None
    market_value: Decimal | None
    weight: Decimal | None


class PortfolioValuationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: int
    base_currency: str
    valuation_date: date
    status: str
    total_market_value: Decimal | None
    items: list[PortfolioValuationItemResponse]