from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.services.cost_basis_service import CostBasisItem, CostBasisResult
from src.response.cost_basis_response import CostBasisResponse


def test_cost_basis_dataclass_validates_to_pydantic_response() -> None:
    result = CostBasisResult(
        portfolio_id=123,
        as_of_date=date(2026, 8, 25),
        status="COMPLETE",
        items=(
            CostBasisItem(
                asset_id=456,
                asset_code="AAL",
                asset_name="AAL Example Fund",
                asset_currency="TRY",
                status="COMPLETE",
                unavailable_reason=None,
                quantity=Decimal("10.00000000"),
                total_cost_basis=Decimal("200.0000000000000000"),
                average_cost_per_unit=Decimal("20.00000000"),
            ),
        ),
    )

    response = CostBasisResponse.model_validate(result)

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
    result = CostBasisResult(
        portfolio_id=1,
        as_of_date=date(2026, 8, 25),
        status="COMPLETE",
        items=(
            CostBasisItem(
                asset_id=2,
                asset_code="DEC",
                asset_name="Decimal Asset",
                asset_currency="TRY",
                status="COMPLETE",
                unavailable_reason=None,
                quantity=Decimal("1.23456789"),
                total_cost_basis=Decimal("3.333333333333333333333333333"),
                average_cost_per_unit=Decimal("1.666666666666666666666666667"),
            ),
        ),
    )

    response = CostBasisResponse.model_validate(result)
    item = response.items[0]

    assert isinstance(item.quantity, Decimal)
    assert isinstance(item.total_cost_basis, Decimal)
    assert isinstance(item.average_cost_per_unit, Decimal)
    assert item.quantity == Decimal("1.23456789")
    assert item.total_cost_basis == Decimal("3.333333333333333333333333333")
    assert item.average_cost_per_unit == Decimal("1.666666666666666666666666667")


def test_unavailable_nullable_fields_are_accepted() -> None:
    result = CostBasisResult(
        portfolio_id=1,
        as_of_date=date(2026, 8, 25),
        status="INCOMPLETE",
        items=(
            CostBasisItem(
                asset_id=2,
                asset_code="NOC",
                asset_name="No Currency Asset",
                asset_currency=None,
                status="UNAVAILABLE",
                unavailable_reason="ASSET_CURRENCY_UNAVAILABLE",
                quantity=Decimal("10.00000000"),
                total_cost_basis=None,
                average_cost_per_unit=None,
            ),
        ),
    )

    response = CostBasisResponse.model_validate(result)
    item = response.items[0]

    assert response.status == "INCOMPLETE"
    assert item.asset_currency is None
    assert item.status == "UNAVAILABLE"
    assert item.unavailable_reason == "ASSET_CURRENCY_UNAVAILABLE"
    assert item.total_cost_basis is None
    assert item.average_cost_per_unit is None


def test_as_of_date_status_and_items_are_preserved() -> None:
    result = CostBasisResult(
        portfolio_id=7,
        as_of_date=date(2026, 8, 26),
        status="COMPLETE",
        items=(),
    )

    response = CostBasisResponse.model_validate(result)

    assert response.portfolio_id == 7
    assert response.as_of_date == date(2026, 8, 26)
    assert response.status == "COMPLETE"
    assert response.items == []