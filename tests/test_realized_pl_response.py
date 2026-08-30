from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.response.realized_pl_response import RealizedPlResponse
from src.services.realized_pl_service import RealizedPlItem, RealizedPlResult


def test_complete_item_dataclass_validates_to_pydantic_response() -> None:
    result = RealizedPlResult(
        portfolio_id=123,
        as_of_date=date(2026, 8, 25),
        status="COMPLETE",
        items=(
            RealizedPlItem(
                asset_id=456,
                asset_code="AAL",
                asset_name="AAL Example Fund",
                asset_currency="TRY",
                status="COMPLETE",
                unavailable_reason=None,
                sold_quantity=Decimal("4.00000000"),
                realized_proceeds=Decimal("120.0000000000000000"),
                realized_cost_basis=Decimal("80.0000000000000000"),
                native_realized_pl=Decimal("40.0000000000000000"),
            ),
        ),
    )

    response = RealizedPlResponse.model_validate(result)

    assert response.portfolio_id == 123
    assert response.as_of_date == date(2026, 8, 25)
    assert response.status == "COMPLETE"
    assert len(response.items) == 1
    item = response.items[0]
    assert item.asset_id == 456
    assert item.asset_code == "AAL"
    assert item.asset_name == "AAL Example Fund"
    assert item.asset_currency == "TRY"
    assert item.status == "COMPLETE"
    assert item.unavailable_reason is None


def test_decimal_fields_remain_decimal_in_python_response() -> None:
    result = RealizedPlResult(
        portfolio_id=1,
        as_of_date=date(2026, 8, 25),
        status="COMPLETE",
        items=(
            RealizedPlItem(
                asset_id=2,
                asset_code="DEC",
                asset_name="Decimal Asset",
                asset_currency="TRY",
                status="COMPLETE",
                unavailable_reason=None,
                sold_quantity=Decimal("1.23456789"),
                realized_proceeds=Decimal("3.0000000000000000"),
                realized_cost_basis=Decimal("1.666666666666666666666666667"),
                native_realized_pl=Decimal("1.333333333333333333333333333"),
            ),
        ),
    )

    response = RealizedPlResponse.model_validate(result)
    item = response.items[0]

    assert isinstance(item.sold_quantity, Decimal)
    assert isinstance(item.realized_proceeds, Decimal)
    assert isinstance(item.realized_cost_basis, Decimal)
    assert isinstance(item.native_realized_pl, Decimal)


def test_json_serialization_outputs_decimal_strings() -> None:
    result = RealizedPlResult(
        portfolio_id=1,
        as_of_date=date(2026, 8, 25),
        status="COMPLETE",
        items=(
            RealizedPlItem(
                asset_id=2,
                asset_code="JSON",
                asset_name="JSON Asset",
                asset_currency="TRY",
                status="COMPLETE",
                unavailable_reason=None,
                sold_quantity=Decimal("1.23456789"),
                realized_proceeds=Decimal("3.0000000000000000"),
                realized_cost_basis=Decimal("1.666666666666666666666666667"),
                native_realized_pl=Decimal("1.333333333333333333333333333"),
            ),
        ),
    )

    payload = RealizedPlResponse.model_validate(result).model_dump(mode="json")
    item = payload["items"][0]

    assert item["sold_quantity"] == "1.23456789"
    assert item["realized_proceeds"] == "3.0000000000000000"
    assert item["realized_cost_basis"] == "1.666666666666666666666666667"
    assert item["native_realized_pl"] == "1.333333333333333333333333333"


def test_unavailable_item_accepts_null_monetary_outputs_and_keeps_sold_quantity() -> None:
    result = RealizedPlResult(
        portfolio_id=1,
        as_of_date=date(2026, 8, 25),
        status="INCOMPLETE",
        items=(
            RealizedPlItem(
                asset_id=2,
                asset_code="NOC",
                asset_name="No Currency Asset",
                asset_currency=None,
                status="UNAVAILABLE",
                unavailable_reason="ASSET_CURRENCY_UNAVAILABLE",
                sold_quantity=Decimal("4.00000000"),
                realized_proceeds=None,
                realized_cost_basis=None,
                native_realized_pl=None,
            ),
        ),
    )

    response = RealizedPlResponse.model_validate(result)
    item = response.items[0]

    assert response.status == "INCOMPLETE"
    assert item.sold_quantity == Decimal("4.00000000")
    assert item.realized_proceeds is None
    assert item.realized_cost_basis is None
    assert item.native_realized_pl is None


def test_response_contract_excludes_portfolio_total_and_fx_fields() -> None:
    field_names = set(RealizedPlResponse.model_fields)

    assert "total_realized_pl" not in field_names
    assert "portfolio_realized_pl" not in field_names
    assert "native_realized_pl" not in field_names
    assert "base_currency" not in field_names
    assert "fx_rate" not in field_names
    assert "fx_date" not in field_names
    assert "market_value" not in field_names
    assert "realized_pl_percent" not in field_names
