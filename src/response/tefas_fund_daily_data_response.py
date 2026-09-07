from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class TefasFundDailyObservationResponse(BaseModel):
    data_date: date
    price: Decimal
    exchange_bulletin_price: Decimal | None
    shares_outstanding: Decimal | None
    investor_count: int | None
    portfolio_size: Decimal | None


class TefasFundDailyLatestResponse(BaseModel):
    asset_id: int
    fund_code: str
    fund_name: str
    fund_kind: str | None
    currency: str | None
    observation: TefasFundDailyObservationResponse


class TefasFundDailyHistoryResponse(BaseModel):
    asset_id: int
    fund_code: str
    fund_name: str
    fund_kind: str | None
    currency: str | None
    items: list[TefasFundDailyObservationResponse]
    total: int