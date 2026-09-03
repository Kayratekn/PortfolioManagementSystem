from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PortfolioPerformancePointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    portfolio_value: Decimal | None
    external_flow: Decimal | None
    daily_return: Decimal | None
    cumulative_return: Decimal | None
    status: str
    unavailable_reason: str | None


class PortfolioPerformanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: int
    base_currency: str
    start_date: date
    end_date: date
    status: str
    cumulative_return: Decimal | None
    points: list[PortfolioPerformancePointResponse]