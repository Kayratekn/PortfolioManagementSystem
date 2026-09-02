from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from src.services.market_data_freshness import MarketDataFreshnessStatus


class MarketDataFreshnessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    requested_date: date
    effective_date: date | None
    age_days: int | None
    status: MarketDataFreshnessStatus
