from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class TefasFundMetricsResponse(BaseModel):
    fund_code: str
    fund_name: str
    data_date: date

    previous_observation_date: date | None

    daily_return_ratio: Decimal | None
    daily_return_baseline_date: date | None

    five_observation_return_ratio: Decimal | None
    five_observation_baseline_date: date | None

    one_month_return_ratio: Decimal | None
    one_month_baseline_date: date | None

    investor_count_change: int | None
    investor_count_growth_ratio: Decimal | None

    aum_change: Decimal | None
    aum_growth_ratio: Decimal | None

    average_aum_per_investor: Decimal | None

    shares_outstanding_change: Decimal | None

    byf_exchange_bulletin_daily_return_ratio: Decimal | None
    byf_exchange_bulletin_daily_return_baseline_date: date | None
    byf_exchange_bulletin_price_to_price_ratio: Decimal | None
