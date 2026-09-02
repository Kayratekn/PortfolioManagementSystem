from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.response.unrealized_pl_response import UnrealizedPlResponse
from src.services.market_data_freshness import (
    observed_market_data_freshness,
    unavailable_market_data_freshness,
)
from src.services.unrealized_pl_service import UnrealizedPlItem, UnrealizedPlResult


def test_unrealized_pl_dataclass_validates_to_pydantic_response() -> None:
    result = UnrealizedPlResult(
        portfolio_id=123,
        as_of_date=date(2026, 8, 25),
        status="COMPLETE",
        items=(
            UnrealizedPlItem(
                asset_id=456,
                asset_code="AAL",
                asset_name="AAL Example Fund",
                asset_currency="TRY",
                status="COMPLETE",
                unavailable_reason=None,
                quantity=Decimal("10.00000000"),
                total_cost_basis=Decimal("200.0000000000000000"),
                average_cost_per_unit=Decimal("20.00000000"),
                price=Decimal("25.00000000"),
                price_date=date(2026, 8, 24),
                price_freshness=observed_market_data_freshness(
                    requested_date=date(2026, 8, 25),
                    effective_date=date(2026, 8, 24),
                ),
                price_kind="NAV",
                price_source="TEFAS",
                native_market_value=Decimal("250.0000000000000000"),
                native_unrealized_pl=Decimal("50.0000000000000000"),
            ),
        ),
    )

    response = UnrealizedPlResponse.model_validate(result)

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
    assert item.price_freshness.status == "STALE"
    assert item.price_freshness.age_days == 1
    assert item.price_kind == "NAV"
    assert item.price_source == "TEFAS"


def test_unavailable_nullable_fields_are_accepted() -> None:
    result = UnrealizedPlResult(
        portfolio_id=1,
        as_of_date=date(2026, 8, 25),
        status="INCOMPLETE",
        items=(
            UnrealizedPlItem(
                asset_id=2,
                asset_code="NOC",
                asset_name="No Currency Asset",
                asset_currency=None,
                status="UNAVAILABLE",
                unavailable_reason="ASSET_CURRENCY_UNAVAILABLE",
                quantity=Decimal("10.00000000"),
                total_cost_basis=None,
                average_cost_per_unit=None,
                price=None,
                price_date=None,
                price_freshness=unavailable_market_data_freshness(
                    requested_date=date(2026, 8, 25),
                ),
                price_kind=None,
                price_source=None,
                native_market_value=None,
                native_unrealized_pl=None,
            ),
        ),
    )

    response = UnrealizedPlResponse.model_validate(result)
    item = response.items[0]

    assert response.status == "INCOMPLETE"
    assert item.asset_currency is None
    assert item.status == "UNAVAILABLE"
    assert item.unavailable_reason == "ASSET_CURRENCY_UNAVAILABLE"
    assert item.total_cost_basis is None
    assert item.average_cost_per_unit is None
    assert item.price is None
    assert item.native_market_value is None
    assert item.native_unrealized_pl is None


def test_decimal_fields_remain_decimal_in_python_response() -> None:
    result = UnrealizedPlResult(
        portfolio_id=1,
        as_of_date=date(2026, 8, 25),
        status="COMPLETE",
        items=(
            UnrealizedPlItem(
                asset_id=2,
                asset_code="DEC",
                asset_name="Decimal Asset",
                asset_currency="TRY",
                status="COMPLETE",
                unavailable_reason=None,
                quantity=Decimal("1.23456789"),
                total_cost_basis=Decimal("3.333333333333333333333333333"),
                average_cost_per_unit=Decimal("1.666666666666666666666666667"),
                price=Decimal("2.50000000"),
                price_date=date(2026, 8, 25),
                price_freshness=observed_market_data_freshness(
                    requested_date=date(2026, 8, 25),
                    effective_date=date(2026, 8, 25),
                ),
                price_kind="NAV",
                price_source="TEFAS",
                native_market_value=Decimal("3.0864197250000000"),
                native_unrealized_pl=Decimal("-0.246913608333333333333333333"),
            ),
        ),
    )

    response = UnrealizedPlResponse.model_validate(result)
    item = response.items[0]

    assert isinstance(item.quantity, Decimal)
    assert isinstance(item.total_cost_basis, Decimal)
    assert isinstance(item.average_cost_per_unit, Decimal)
    assert isinstance(item.price, Decimal)
    assert isinstance(item.native_market_value, Decimal)
    assert isinstance(item.native_unrealized_pl, Decimal)


def test_portfolio_id_as_of_date_status_and_items_are_preserved() -> None:
    result = UnrealizedPlResult(
        portfolio_id=7,
        as_of_date=date(2026, 8, 26),
        status="COMPLETE",
        items=(),
    )

    response = UnrealizedPlResponse.model_validate(result)

    assert response.portfolio_id == 7
    assert response.as_of_date == date(2026, 8, 26)
    assert response.status == "COMPLETE"
    assert response.items == []


def test_response_contract_excludes_portfolio_total_and_fx_fields() -> None:
    field_names = set(UnrealizedPlResponse.model_fields)

    assert "native_unrealized_pl" not in field_names
    assert "total_unrealized_pl" not in field_names
    assert "portfolio_unrealized_pl" not in field_names
    assert "base_currency" not in field_names
    assert "fx_rate" not in field_names
    assert "fx_date" not in field_names
    assert "market_value" not in field_names
    assert "unrealized_pl_percent" not in field_names

def test_unrealized_pl_response_serializes_price_freshness() -> None:
    result = UnrealizedPlResult(
        portfolio_id=123,
        as_of_date=date(2026, 8, 25),
        status="COMPLETE",
        items=(
            UnrealizedPlItem(
                asset_id=456,
                asset_code="AAL",
                asset_name="AAL Example Fund",
                asset_currency="TRY",
                status="COMPLETE",
                unavailable_reason=None,
                quantity=Decimal("10.00000000"),
                total_cost_basis=Decimal("200.0000000000000000"),
                average_cost_per_unit=Decimal("20.00000000"),
                price=Decimal("25.00000000"),
                price_date=date(2026, 8, 25),
                price_freshness=observed_market_data_freshness(
                    requested_date=date(2026, 8, 25),
                    effective_date=date(2026, 8, 25),
                ),
                price_kind="NAV",
                price_source="TEFAS",
                native_market_value=Decimal("250.0000000000000000"),
                native_unrealized_pl=Decimal("50.0000000000000000"),
            ),
        ),
    )

    dumped = UnrealizedPlResponse.model_validate(result).model_dump(mode="json")

    assert dumped["items"][0]["price_freshness"] == {
        "requested_date": "2026-08-25",
        "effective_date": "2026-08-25",
        "age_days": 0,
        "status": "CURRENT",
    }
