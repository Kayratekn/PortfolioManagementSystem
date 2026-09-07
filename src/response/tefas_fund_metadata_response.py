from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TefasFundLatestMetadataResponse(BaseModel):
    asset_id: int
    fund_code: str
    fund_name: str
    fund_kind: str | None
    isin: str | None
    currency: str | None
    observed_at: datetime
    source_page: str
    fund_category: str
    category_rank: int | None
    category_fund_count: int | None
    market_share_raw: Decimal | None
    risk_value: int | None
    tefas_status: str | None
    transaction_start_time: str | None
    transaction_end_time: str | None
    entry_commission_raw: Decimal | None
    exit_commission_raw: Decimal | None
    interest_content: str | None
    fund_sale_valor: int | None
    fund_redemption_valor: int | None