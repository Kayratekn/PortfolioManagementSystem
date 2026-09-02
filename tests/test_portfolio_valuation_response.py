from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.response.portfolio_valuation_response import PortfolioValuationResponse
from src.services.market_data_freshness import (
    not_applicable_market_data_freshness,
    observed_market_data_freshness,
    unavailable_market_data_freshness,
)
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
        price_freshness=observed_market_data_freshness(
            requested_date=date(2026, 8, 26),
            effective_date=date(2026, 8, 26),
        ),
        price_kind="NAV",
        price_source="TEFAS",
        fx_rate=Decimal("1"),
        fx_rate_date=None,
        fx_freshness=not_applicable_market_data_freshness(
            requested_date=date(2026, 8, 26),
        ),
        fx_rate_kind="IDENTITY",
        fx_source="IDENTITY",
        native_market_value=Decimal("32.5000000000000000"),
        market_value=Decimal("32.5000000000000000"),
        weight=Decimal("1"),
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
    assert response.items[0].price_freshness.status == "CURRENT"
    assert response.items[0].price_freshness.age_days == 0
    assert response.items[0].fx_freshness.status == "NOT_APPLICABLE"
    assert response.items[0].market_value == Decimal("32.5000000000000000")
    assert response.items[0].weight == Decimal("1")


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
        price_freshness=observed_market_data_freshness(
            requested_date=date(2026, 8, 26),
            effective_date=date(2026, 8, 26),
        ),
        price_kind="NAV",
        price_source="TEFAS",
        fx_rate=None,
        fx_rate_date=None,
        fx_freshness=unavailable_market_data_freshness(
            requested_date=date(2026, 8, 26),
        ),
        fx_rate_kind=None,
        fx_source=None,
        native_market_value=None,
        market_value=None,
        weight=None,
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
    assert response.items[0].weight is None


def test_portfolio_valuation_response_serializes_item_weight_as_string() -> None:
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
        price_freshness=observed_market_data_freshness(
            requested_date=date(2026, 8, 26),
            effective_date=date(2026, 8, 26),
        ),
        price_kind="NAV",
        price_source="TEFAS",
        fx_rate=Decimal("1"),
        fx_rate_date=None,
        fx_freshness=not_applicable_market_data_freshness(
            requested_date=date(2026, 8, 26),
        ),
        fx_rate_kind="IDENTITY",
        fx_source="IDENTITY",
        native_market_value=Decimal("32.5000000000000000"),
        market_value=Decimal("32.5000000000000000"),
        weight=Decimal("0.25"),
    )
    result = PortfolioValuationResult(
        portfolio_id=10,
        base_currency="TRY",
        valuation_date=date(2026, 8, 26),
        status="COMPLETE",
        total_market_value=Decimal("130.0000000000000000"),
        items=(item,),
    )

    dumped = PortfolioValuationResponse.model_validate(result).model_dump(mode="json")

    assert dumped["items"][0]["weight"] == "0.25"
    assert isinstance(dumped["items"][0]["weight"], str)


def test_portfolio_valuation_response_serializes_none_weight_as_null() -> None:
    item = PortfolioValuationItem(
        asset_id=1,
        asset_code="AAL",
        asset_name="AAL Example Fund",
        quantity=Decimal("10.00000000"),
        asset_currency="TRY",
        status="UNAVAILABLE",
        unavailable_reason="PRICE_UNAVAILABLE",
        price=None,
        price_date=None,
        price_freshness=unavailable_market_data_freshness(
            requested_date=date(2026, 8, 26),
        ),
        price_kind=None,
        price_source=None,
        fx_rate=None,
        fx_rate_date=None,
        fx_freshness=unavailable_market_data_freshness(
            requested_date=date(2026, 8, 26),
        ),
        fx_rate_kind=None,
        fx_source=None,
        native_market_value=None,
        market_value=None,
        weight=None,
    )
    result = PortfolioValuationResult(
        portfolio_id=10,
        base_currency="TRY",
        valuation_date=date(2026, 8, 26),
        status="INCOMPLETE",
        total_market_value=None,
        items=(item,),
    )

    dumped = PortfolioValuationResponse.model_validate(result).model_dump(mode="json")

    assert dumped["items"][0]["weight"] is None

def test_portfolio_valuation_response_serializes_freshness_fields() -> None:
    item = PortfolioValuationItem(
        asset_id=1,
        asset_code="AAL",
        asset_name="AAL Example Fund",
        quantity=Decimal("10.00000000"),
        asset_currency="USD",
        status="COMPLETE",
        unavailable_reason=None,
        price=Decimal("3.25000000"),
        price_date=date(2026, 8, 25),
        price_freshness=observed_market_data_freshness(
            requested_date=date(2026, 8, 26),
            effective_date=date(2026, 8, 25),
        ),
        price_kind="NAV",
        price_source="TEFAS",
        fx_rate=Decimal("40"),
        fx_rate_date=date(2026, 8, 24),
        fx_freshness=observed_market_data_freshness(
            requested_date=date(2026, 8, 26),
            effective_date=date(2026, 8, 24),
        ),
        fx_rate_kind="TCMB_MIDPOINT",
        fx_source="TCMB",
        native_market_value=Decimal("32.5000000000000000"),
        market_value=Decimal("1300.0000000000000000"),
        weight=Decimal("1"),
    )
    result = PortfolioValuationResult(
        portfolio_id=10,
        base_currency="TRY",
        valuation_date=date(2026, 8, 26),
        status="COMPLETE",
        total_market_value=Decimal("1300.0000000000000000"),
        items=(item,),
    )

    dumped = PortfolioValuationResponse.model_validate(result).model_dump(mode="json")

    assert dumped["items"][0]["price_freshness"] == {
        "requested_date": "2026-08-26",
        "effective_date": "2026-08-25",
        "age_days": 1,
        "status": "STALE",
    }
    assert dumped["items"][0]["fx_freshness"] == {
        "requested_date": "2026-08-26",
        "effective_date": "2026-08-24",
        "age_days": 2,
        "status": "STALE",
    }
