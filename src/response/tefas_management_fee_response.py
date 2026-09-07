from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TefasFundCurrentManagementFeeResponse(BaseModel):
    asset_id: int
    fund_code: str
    fund_name: str
    fund_kind: str | None
    management_fee_percentage: Decimal
    first_observed_at: datetime
    last_observed_at: datetime
    source_endpoint: str
    source_field_name: str