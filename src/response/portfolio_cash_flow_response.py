from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PortfolioCashFlowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    portfolio_id: int
    flow_type: str
    amount: Decimal
    currency: str
    flow_date: date
    created_at: datetime
    updated_at: datetime


class PortfolioCashFlowListResponse(BaseModel):
    items: list[PortfolioCashFlowResponse]
    total: int
    skip: int
    limit: int
