from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ALLOWED_TRANSACTION_TYPES = {"BUY", "SELL"}


class TransactionCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    asset_id: int = Field(gt=0)
    transaction_type: str
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    unit_price: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    transaction_date: date

    @field_validator("transaction_type")
    @classmethod
    def validate_transaction_type(cls, value: str) -> str:
        normalized_value = value.upper()
        if normalized_value not in ALLOWED_TRANSACTION_TYPES:
            raise ValueError("Transaction type must be BUY or SELL.")
        return normalized_value