from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_daily_data import TefasFundDailyData
from src.repositories.tefas_fund_daily_data_repository import TefasFundDailyDataRepository
from src.services.tefas_valuation_price_service import TefasValuationPriceService


VALUATION_DATE = date(2026, 8, 26)


def _create_asset(
    db_session: Session,
    *,
    asset_code: str = "AAL",
    fund_kind: str | None = "YAT",
    data_source: str = "TEFAS",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=f"{asset_code} Example Fund",
        asset_type="FUND",
        fund_kind=fund_kind,
        currency="TRY",
        data_source=data_source,
        is_active=True,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def _add_daily_data(
    db_session: Session,
    *,
    asset_id: int,
    data_date: date = VALUATION_DATE,
    price: Decimal = Decimal("12.34567890"),
    exchange_bulletin_price: Decimal | None = None,
) -> TefasFundDailyData:
    daily_data = TefasFundDailyData(
        asset_id=asset_id,
        data_date=data_date,
        price=price,
        shares_outstanding=Decimal("1000.0000"),
        investor_count=100,
        portfolio_size=Decimal("12345.6700"),
        exchange_bulletin_price=exchange_bulletin_price,
    )
    db_session.add(daily_data)
    db_session.flush()
    return daily_data


def _create_service(db_session: Session) -> TefasValuationPriceService:
    return TefasValuationPriceService(TefasFundDailyDataRepository(db_session))


@pytest.mark.parametrize("fund_kind", ["YAT", "EMK", "GYF", "GSYF"])
def test_nav_fund_kinds_use_price_and_nav_kind(
    db_session: Session,
    fund_kind: str,
) -> None:
    asset = _create_asset(db_session, fund_kind=fund_kind)
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        price=Decimal("12.34567890"),
        exchange_bulletin_price=Decimal("99.00000000"),
    )
    service = _create_service(db_session)

    result = service.get_price(asset=asset, valuation_date=VALUATION_DATE)

    assert result is not None
    assert result.price == Decimal("12.34567890")
    assert result.price_date == VALUATION_DATE
    assert result.price_kind == "NAV"
    assert result.source == "TEFAS"


def test_byf_uses_exchange_bulletin_price_and_exchange_market_kind(
    db_session: Session,
) -> None:
    asset = _create_asset(db_session, fund_kind="BYF")
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        price=Decimal("12.34567890"),
        exchange_bulletin_price=Decimal("11.11111111"),
    )
    service = _create_service(db_session)

    result = service.get_price(asset=asset, valuation_date=VALUATION_DATE)

    assert result is not None
    assert result.price == Decimal("11.11111111")
    assert result.price_kind == "EXCHANGE_MARKET"
    assert result.source == "TEFAS"


def test_byf_does_not_use_nav_when_bulletin_price_exists(db_session: Session) -> None:
    asset = _create_asset(db_session, fund_kind="BYF")
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        price=Decimal("99.99999999"),
        exchange_bulletin_price=Decimal("10.00000000"),
    )
    service = _create_service(db_session)

    result = service.get_price(asset=asset, valuation_date=VALUATION_DATE)

    assert result is not None
    assert result.price == Decimal("10.00000000")


def test_byf_missing_exchange_bulletin_price_returns_none(db_session: Session) -> None:
    asset = _create_asset(db_session, fund_kind="BYF")
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        price=Decimal("12.34567890"),
        exchange_bulletin_price=None,
    )
    service = _create_service(db_session)

    result = service.get_price(asset=asset, valuation_date=VALUATION_DATE)

    assert result is None


def test_latest_observation_on_valuation_date_is_used(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 25), price=Decimal("10.00000000"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=VALUATION_DATE, price=Decimal("12.00000000"))
    service = _create_service(db_session)

    result = service.get_price(asset=asset, valuation_date=VALUATION_DATE)

    assert result is not None
    assert result.price == Decimal("12.00000000")
    assert result.price_date == VALUATION_DATE


def test_closest_prior_observation_is_used_when_exact_date_is_absent(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 20), price=Decimal("10.00000000"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 25), price=Decimal("11.00000000"))
    service = _create_service(db_session)

    result = service.get_price(asset=asset, valuation_date=VALUATION_DATE)

    assert result is not None
    assert result.price == Decimal("11.00000000")
    assert result.price_date == date(2026, 8, 25)


def test_future_observation_is_not_used(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 27), price=Decimal("12.00000000"))
    service = _create_service(db_session)

    result = service.get_price(asset=asset, valuation_date=VALUATION_DATE)

    assert result is None


def test_no_observation_returns_none(db_session: Session) -> None:
    asset = _create_asset(db_session)
    service = _create_service(db_session)

    result = service.get_price(asset=asset, valuation_date=VALUATION_DATE)

    assert result is None


def test_non_tefas_asset_is_rejected(db_session: Session) -> None:
    asset = _create_asset(db_session, data_source="MANUAL")
    service = _create_service(db_session)

    with pytest.raises(ValueError, match="TEFAS"):
        service.get_price(asset=asset, valuation_date=VALUATION_DATE)


def test_missing_fund_kind_is_rejected(db_session: Session) -> None:
    asset = _create_asset(db_session, fund_kind=None)
    service = _create_service(db_session)

    with pytest.raises(ValueError, match="fund_kind"):
        service.get_price(asset=asset, valuation_date=VALUATION_DATE)


def test_unsupported_fund_kind_is_rejected(db_session: Session) -> None:
    asset = _create_asset(db_session, fund_kind="UNKNOWN")
    service = _create_service(db_session)

    with pytest.raises(ValueError, match="Unsupported"):
        service.get_price(asset=asset, valuation_date=VALUATION_DATE)


@pytest.mark.parametrize("selected_price", [Decimal("0"), Decimal("-1.00000000")])
def test_non_positive_selected_nav_price_is_rejected(
    db_session: Session,
    selected_price: Decimal,
) -> None:
    asset = _create_asset(db_session, fund_kind="YAT")
    _add_daily_data(db_session, asset_id=asset.id, price=selected_price)
    service = _create_service(db_session)

    with pytest.raises(ValueError, match="greater than 0"):
        service.get_price(asset=asset, valuation_date=VALUATION_DATE)


@pytest.mark.parametrize("selected_price", [Decimal("0"), Decimal("-1.00000000")])
def test_non_positive_selected_byf_exchange_market_price_is_rejected(
    db_session: Session,
    selected_price: Decimal,
) -> None:
    asset = _create_asset(db_session, fund_kind="BYF")
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        price=Decimal("12.00000000"),
        exchange_bulletin_price=selected_price,
    )
    service = _create_service(db_session)

    with pytest.raises(ValueError, match="greater than 0"):
        service.get_price(asset=asset, valuation_date=VALUATION_DATE)


def test_decimal_value_is_preserved_exactly(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("12.12345678"))
    service = _create_service(db_session)

    result = service.get_price(asset=asset, valuation_date=VALUATION_DATE)

    assert result is not None
    assert result.price == Decimal("12.12345678")
    assert isinstance(result.price, Decimal)