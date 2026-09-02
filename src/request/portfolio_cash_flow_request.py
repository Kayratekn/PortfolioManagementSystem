from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ALLOWED_PORTFOLIO_CASH_FLOW_TYPES = {"DEPOSIT", "WITHDRAWAL"}
ALLOWED_PORTFOLIO_CASH_FLOW_CURRENCIES = {"TRY", "USD", "EUR", "GBP"}


class PortfolioCashFlowCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    flow_type: str
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    currency: str
    flow_date: date

    @field_validator("flow_type")
    @classmethod
    def validate_flow_type(cls, value: str) -> str:
        normalized_value = value.upper()
        if normalized_value not in ALLOWED_PORTFOLIO_CASH_FLOW_TYPES:
            raise ValueError("Flow type must be DEPOSIT or WITHDRAWAL.")
        return normalized_value

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        normalized_value = value.upper()
        if normalized_value not in ALLOWED_PORTFOLIO_CASH_FLOW_CURRENCIES:
            raise ValueError("Currency must be one of TRY, USD, EUR or GBP.")
        return normalized_value
