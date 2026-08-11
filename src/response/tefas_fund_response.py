from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class TefasFundAllocationItemResponse(BaseModel):
    label: str | None
    raw_field_name: str | None
    percentage: Decimal
    mapping_status: Literal["VERIFIED", "UNRESOLVED"]


class TefasFundAllocationResponse(BaseModel):
    fund_code: str
    fund_name: str
    data_date: date
    allocations: list[TefasFundAllocationItemResponse]
