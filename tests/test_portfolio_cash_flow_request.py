from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.request.portfolio_cash_flow_request import PortfolioCashFlowCreateRequest


VALID_PAYLOAD = {
    "flow_type": "DEPOSIT",
    "amount": Decimal("123.45678901"),
    "currency": "TRY",
    "flow_date": date(2026, 9, 2),
}


def _build_request(**overrides: object) -> PortfolioCashFlowCreateRequest:
    payload = VALID_PAYLOAD.copy()
    payload.update(overrides)
    return PortfolioCashFlowCreateRequest(**payload)


def test_valid_payload_preserves_decimal() -> None:
    request = _build_request()

    assert request.flow_type == "DEPOSIT"
    assert request.amount == Decimal("123.45678901")
    assert request.currency == "TRY"
    assert request.flow_date == date(2026, 9, 2)


def test_lowercase_whitespace_fields_normalize() -> None:
    request = _build_request(flow_type=" withdrawal ", currency=" usd ")

    assert request.flow_type == "WITHDRAWAL"
    assert request.currency == "USD"


@pytest.mark.parametrize("flow_type", ["BUY", "TRANSFER", ""])
def test_invalid_flow_type_is_rejected(flow_type: str) -> None:
    with pytest.raises(ValidationError):
        _build_request(flow_type=flow_type)


@pytest.mark.parametrize("currency", ["JPY", "USDT", ""])
def test_invalid_currency_is_rejected(currency: str) -> None:
    with pytest.raises(ValidationError):
        _build_request(currency=currency)


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-1.00000000")])
def test_non_positive_amount_is_rejected(amount: Decimal) -> None:
    with pytest.raises(ValidationError):
        _build_request(amount=amount)


def test_more_than_8_decimal_places_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _build_request(amount=Decimal("1.123456789"))


def test_more_than_20_total_digits_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _build_request(amount=Decimal("1234567890123.12345678"))
