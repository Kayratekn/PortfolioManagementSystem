from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.response.portfolio_valuation_response import PortfolioValuationResponse
from src.services.portfolio_valuation_service import (
    PortfolioValuationItem,
    PortfolioValuationResult,
)


def test_portfolio_valuation_response_maps_from_service_dataclasses() -> None:
    item = PortfolioValuationItem(
        asset_id=1,
        asset_code="AAL",
        asset_name="AAL Example Fund",
        quantity=Decimal("10.00000000"),
        asset_currency="TRY",
        status="COMPLETE",
        unavailable_reason=None,
        price=Decimal("3.25000000"),
        price_date=date(2026, 8, 26),
        price_kind="NAV",
        price_source="TEFAS",
        fx_rate=Decimal("1"),
        fx_rate_date=None,
        fx_rate_kind="IDENTITY",
        fx_source="IDENTITY",
        native_market_value=Decimal("32.5000000000000000"),
        market_value=Decimal("32.5000000000000000"),
    )
    result = PortfolioValuationResult(
        portfolio_id=10,
        base_currency="TRY",
        valuation_date=date(2026, 8, 26),
        status="COMPLETE",
        total_market_value=Decimal("32.5000000000000000"),
        items=(item,),
    )

    response = PortfolioValuationResponse.model_validate(result)

    assert response.portfolio_id == 10
    assert response.base_currency == "TRY"
    assert response.valuation_date == date(2026, 8, 26)
    assert response.status == "COMPLETE"
    assert response.total_market_value == Decimal("32.5000000000000000")
    assert isinstance(response.items, list)
    assert len(response.items) == 1
    assert response.items[0].asset_code == "AAL"
    assert response.items[0].market_value == Decimal("32.5000000000000000")


def test_portfolio_valuation_response_serializes_decimals_as_strings() -> None:
    result = PortfolioValuationResult(
        portfolio_id=10,
        base_currency="TRY",
        valuation_date=date(2026, 8, 26),
        status="COMPLETE",
        total_market_value=Decimal("1.23456789"),
        items=(),
    )

    dumped = PortfolioValuationResponse.model_validate(result).model_dump(mode="json")

    assert dumped["total_market_value"] == "1.23456789"
    assert isinstance(dumped["total_market_value"], str)
    assert dumped["items"] == []


def test_portfolio_valuation_response_preserves_nullable_provenance_fields() -> None:
    item = PortfolioValuationItem(
        asset_id=1,
        asset_code="AAL",
        asset_name="AAL Example Fund",
        quantity=Decimal("10.00000000"),
        asset_currency=None,
        status="UNAVAILABLE",
        unavailable_reason="ASSET_CURRENCY_UNAVAILABLE",
        price=Decimal("3.25000000"),
        price_date=date(2026, 8, 26),
        price_kind="NAV",
        price_source="TEFAS",
        fx_rate=None,
        fx_rate_date=None,
        fx_rate_kind=None,
        fx_source=None,
        native_market_value=None,
        market_value=None,
    )
    result = PortfolioValuationResult(
        portfolio_id=10,
        base_currency="TRY",
        valuation_date=date(2026, 8, 26),
        status="INCOMPLETE",
        total_market_value=None,
        items=(item,),
    )

    response = PortfolioValuationResponse.model_validate(result)

    assert response.total_market_value is None
    assert response.items[0].asset_currency is None
    assert response.items[0].unavailable_reason == "ASSET_CURRENCY_UNAVAILABLE"
    assert response.items[0].price == Decimal("3.25000000")
    assert response.items[0].fx_rate is None
    assert response.items[0].market_value is None