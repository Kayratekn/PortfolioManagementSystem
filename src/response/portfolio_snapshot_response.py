from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PortfolioSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    portfolio_id: int
    snapshot_date: date
    total_value_try: Decimal
    total_value_usd: Decimal
    total_value_eur: Decimal
    total_value_gbp: Decimal
    created_at: datetime


class PortfolioSnapshotListResponse(BaseModel):
    portfolio_id: int
    start_date: date
    end_date: date
    items: list[PortfolioSnapshotResponse]
