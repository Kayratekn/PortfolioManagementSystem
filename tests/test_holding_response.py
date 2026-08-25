from __future__ import annotations

from decimal import Decimal

from src.response.holding_response import HoldingListResponse, HoldingResponse


def test_holding_response_preserves_all_fields() -> None:
    response = HoldingResponse(
        asset_id=1,
        asset_code="AAL",
        asset_name="Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        currency="TRY",
        data_source="TEFAS",
        quantity=Decimal("10.50000000"),
    )

    assert response.asset_id == 1
    assert response.asset_code == "AAL"
    assert response.asset_name == "Example Fund"
    assert response.asset_type == "FUND"
    assert response.fund_kind == "YAT"
    assert response.currency == "TRY"
    assert response.data_source == "TEFAS"
    assert response.quantity == Decimal("10.50000000")


def test_holding_response_quantity_remains_decimal() -> None:
    response = HoldingResponse(
        asset_id=1,
        asset_code="AAL",
        asset_name="Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        currency="TRY",
        data_source="TEFAS",
        quantity=Decimal("1.23456789"),
    )

    assert isinstance(response.quantity, Decimal)


def test_holding_response_serializes_quantity_as_json_string() -> None:
    response = HoldingResponse(
        asset_id=1,
        asset_code="AAL",
        asset_name="Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        currency="TRY",
        data_source="TEFAS",
        quantity=Decimal("10.50000000"),
    )

    assert '"quantity":"10.50000000"' in response.model_dump_json()


def test_holding_response_does_not_expose_valuation_cost_or_profit_loss_fields() -> None:
    response = HoldingResponse(
        asset_id=1,
        asset_code="AAL",
        asset_name="Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        currency="TRY",
        data_source="TEFAS",
        quantity=Decimal("10.50000000"),
    )

    assert set(response.model_dump()) == {
        "asset_id",
        "asset_code",
        "asset_name",
        "asset_type",
        "fund_kind",
        "currency",
        "data_source",
        "quantity",
    }


def test_holding_list_response_preserves_items_and_total() -> None:
    item = HoldingResponse(
        asset_id=1,
        asset_code="AAL",
        asset_name="Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        currency="TRY",
        data_source="TEFAS",
        quantity=Decimal("10.50000000"),
    )

    response = HoldingListResponse(items=[item], total=1)

    assert response.items == [item]
    assert response.total == 1