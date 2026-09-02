from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal

from src.model.transaction import Transaction
from src.response.transaction_response import TransactionListResponse, TransactionResponse


CREATED_AT = datetime(2026, 8, 25, 9, 30, tzinfo=timezone.utc)
UPDATED_AT = datetime(2026, 8, 25, 10, 45, tzinfo=timezone.utc)


def _build_transaction() -> Transaction:
    return Transaction(
        id=7,
        portfolio_id=11,
        asset_id=13,
        transaction_type="BUY",
        quantity=Decimal("1.23456789"),
        unit_price=Decimal("98.76543210"),
        transaction_currency="TRY",
        transaction_date=date(2026, 8, 25),
        created_at=CREATED_AT,
        updated_at=UPDATED_AT,
    )


def test_transaction_response_can_be_built_from_transaction_orm_object() -> None:
    transaction = _build_transaction()

    response = TransactionResponse.model_validate(transaction)

    assert isinstance(response, TransactionResponse)


def test_transaction_response_preserves_all_fields() -> None:
    transaction = _build_transaction()

    response = TransactionResponse.model_validate(transaction)

    assert response.id == 7
    assert response.portfolio_id == 11
    assert response.asset_id == 13
    assert response.transaction_type == "BUY"
    assert response.quantity == Decimal("1.23456789")
    assert response.unit_price == Decimal("98.76543210")
    assert response.transaction_currency == "TRY"
    assert response.transaction_date == date(2026, 8, 25)
    assert response.created_at == CREATED_AT
    assert response.updated_at == UPDATED_AT


def test_transaction_response_keeps_quantity_and_unit_price_as_decimal() -> None:
    response = TransactionResponse.model_validate(_build_transaction())

    assert isinstance(response.quantity, Decimal)
    assert isinstance(response.unit_price, Decimal)


def test_transaction_response_json_serializes_decimal_values_as_strings() -> None:
    response = TransactionResponse.model_validate(_build_transaction())

    body = json.loads(response.model_dump_json())

    assert body["quantity"] == "1.23456789"
    assert body["unit_price"] == "98.76543210"
    assert body["transaction_currency"] == "TRY"


def test_transaction_list_response_preserves_pagination_metadata() -> None:
    item = TransactionResponse.model_validate(_build_transaction())

    response = TransactionListResponse(items=[item], total=3, skip=1, limit=1)

    assert response.items == [item]
    assert response.total == 3
    assert response.skip == 1
    assert response.limit == 1


def test_transaction_list_response_json_serializes_decimal_values_as_strings() -> None:
    item = TransactionResponse.model_validate(_build_transaction())
    response = TransactionListResponse(items=[item], total=1, skip=0, limit=50)

    body = json.loads(response.model_dump_json())

    assert body["items"][0]["quantity"] == "1.23456789"
    assert body["items"][0]["unit_price"] == "98.76543210"
    assert body["items"][0]["transaction_currency"] == "TRY"
