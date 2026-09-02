from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.request.transaction_request import TransactionCreateRequest


VALID_PAYLOAD = {
    "asset_id": 1,
    "transaction_type": "BUY",
    "quantity": Decimal("1.00000000"),
    "unit_price": Decimal("10.00000000"),
    "transaction_currency": "TRY",
    "transaction_date": date(2026, 8, 25),
}


def _build_request(**overrides: object) -> TransactionCreateRequest:
    payload = VALID_PAYLOAD.copy()
    payload.update(overrides)
    return TransactionCreateRequest(**payload)


def test_valid_buy_payload() -> None:
    request = _build_request()

    assert request.asset_id == 1
    assert request.transaction_type == "BUY"
    assert request.quantity == Decimal("1.00000000")
    assert request.unit_price == Decimal("10.00000000")
    assert request.transaction_currency == "TRY"
    assert request.transaction_date == date(2026, 8, 25)


@pytest.mark.parametrize(
    ("raw_transaction_type", "expected_transaction_type"),
    [
        (" buy ", "BUY"),
        (" sell ", "SELL"),
    ],
)
def test_lowercase_whitespace_transaction_type_normalizes(
    raw_transaction_type: str,
    expected_transaction_type: str,
) -> None:
    request = _build_request(transaction_type=raw_transaction_type)

    assert request.transaction_type == expected_transaction_type

def test_lowercase_whitespace_transaction_currency_normalizes() -> None:
    request = _build_request(transaction_currency=" usd ")

    assert request.transaction_currency == "USD"


def test_invalid_transaction_currency_is_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _build_request(transaction_currency="JPY")

    assert "Transaction currency must be one of TRY, USD, EUR or GBP." in str(exc_info.value)


def test_missing_transaction_currency_is_rejected() -> None:
    payload = VALID_PAYLOAD.copy()
    payload.pop("transaction_currency")

    with pytest.raises(ValidationError):
        TransactionCreateRequest(**payload)


def test_invalid_transaction_type_is_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _build_request(transaction_type="HOLD")

    assert "Transaction type must be BUY or SELL." in str(exc_info.value)


@pytest.mark.parametrize("asset_id", [0, -1])
def test_asset_id_must_be_positive(asset_id: int) -> None:
    with pytest.raises(ValidationError):
        _build_request(asset_id=asset_id)


@pytest.mark.parametrize("quantity", [Decimal("0"), Decimal("-1.00000000")])
def test_quantity_zero_and_negative_are_rejected(quantity: Decimal) -> None:
    with pytest.raises(ValidationError):
        _build_request(quantity=quantity)


@pytest.mark.parametrize("unit_price", [Decimal("0"), Decimal("-1.00000000")])
def test_unit_price_zero_and_negative_are_rejected(unit_price: Decimal) -> None:
    with pytest.raises(ValidationError):
        _build_request(unit_price=unit_price)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("quantity", Decimal("1.123456789")),
        ("unit_price", Decimal("1.123456789")),
    ],
)
def test_more_than_8_decimal_places_is_rejected(
    field_name: str,
    value: Decimal,
) -> None:
    with pytest.raises(ValidationError):
        _build_request(**{field_name: value})


def test_valid_8_decimal_decimal_values_are_preserved_exactly() -> None:
    request = _build_request(
        quantity=Decimal("123456789012.12345678"),
        unit_price=Decimal("987654321012.87654321"),
    )

    assert request.quantity == Decimal("123456789012.12345678")
    assert request.unit_price == Decimal("987654321012.87654321")

@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("quantity", Decimal("1234567890123.12345678")),
        ("unit_price", Decimal("1234567890123.12345678")),
    ],
)
def test_more_than_20_total_digits_is_rejected(
    field_name: str,
    value: Decimal,
) -> None:
    with pytest.raises(ValidationError):
        _build_request(**{field_name: value})