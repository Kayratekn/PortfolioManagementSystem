from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_daily_data import TefasFundDailyData
from src.repositories.asset_repository import AssetRepository
from src.repositories.tefas_fund_daily_data_repository import TefasFundDailyDataRepository
from src.services.tefas_fund_daily_read_service import TefasFundDailyReadService


def _create_asset(
    db_session: Session,
    *,
    asset_code: str = "AAL",
    asset_name: str = "AAL Fund",
    data_source: str = "TEFAS",
    fund_kind: str | None = "YAT",
    currency: str | None = "TRY",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=asset_name,
        asset_type="FUND",
        fund_kind=fund_kind,
        currency=currency,
        data_source=data_source,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def _add_daily_data(
    db_session: Session,
    *,
    asset_id: int,
    data_date: date,
    price: Decimal = Decimal("100.12345678"),
    exchange_bulletin_price: Decimal | None = Decimal("101.12345678"),
    shares_outstanding: Decimal | None = Decimal("1000.0000"),
    investor_count: int | None = 100,
    portfolio_size: Decimal | None = Decimal("10000.0000"),
) -> TefasFundDailyData:
    row = TefasFundDailyData(
        asset_id=asset_id,
        data_date=data_date,
        price=price,
        exchange_bulletin_price=exchange_bulletin_price,
        shares_outstanding=shares_outstanding,
        investor_count=investor_count,
        portfolio_size=portfolio_size,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _service(db_session: Session) -> TefasFundDailyReadService:
    return TefasFundDailyReadService(
        asset_repository=AssetRepository(db_session),
        daily_data_repository=TefasFundDailyDataRepository(db_session),
    )


def test_latest_normalizes_fund_code_and_returns_latest_stored_observation(
    db_session: Session,
) -> None:
    asset = _create_asset(db_session, asset_code="AAL", asset_name="AAL TEST FUND")
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10), price=Decimal("100"))
    latest = _add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        price=Decimal("101.12345678"),
        exchange_bulletin_price=Decimal("102.12345678"),
    )

    result = _service(db_session).get_latest(fund_code="  aal  ")

    assert result.asset_id == asset.id
    assert result.fund_code == "AAL"
    assert result.fund_name == "AAL TEST FUND"
    assert result.fund_kind == "YAT"
    assert result.currency == "TRY"
    assert result.observation.data_date == latest.data_date
    assert result.observation.price == Decimal("101.12345678")
    assert result.observation.exchange_bulletin_price == Decimal("102.12345678")


def test_latest_preserves_nullable_values(db_session: Session) -> None:
    asset = _create_asset(db_session, currency="TRY", fund_kind=None)
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        exchange_bulletin_price=None,
        shares_outstanding=None,
        investor_count=None,
        portfolio_size=None,
    )

    result = _service(db_session).get_latest(fund_code="AAL")

    assert result.fund_kind is None
    assert result.currency == "TRY"
    assert result.observation.exchange_bulletin_price is None
    assert result.observation.shares_outstanding is None
    assert result.observation.investor_count is None
    assert result.observation.portfolio_size is None


def test_latest_missing_tefas_asset_raises_404(db_session: Session) -> None:
    _create_asset(db_session, asset_code="AAL", data_source="MANUAL")

    with pytest.raises(HTTPException) as exc_info:
        _service(db_session).get_latest(fund_code="AAL")

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "TEFAS fund not found."


def test_latest_existing_asset_without_daily_data_raises_404(db_session: Session) -> None:
    _create_asset(db_session)

    with pytest.raises(HTTPException) as exc_info:
        _service(db_session).get_latest(fund_code="AAL")

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "TEFAS fund daily data not found."


def test_history_is_inclusive_ordered_and_asset_isolated(db_session: Session) -> None:
    asset = _create_asset(db_session)
    other_asset = _create_asset(db_session, asset_code="BLH")
    outside_before = _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 9))
    start = _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10), price=Decimal("100"))
    end = _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("101"))
    outside_after = _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 12))
    other_row = _add_daily_data(db_session, asset_id=other_asset.id, data_date=date(2026, 8, 10))

    result = _service(db_session).get_history(
        fund_code="AAL",
        start_date=date(2026, 8, 10),
        end_date=date(2026, 8, 11),
    )

    assert result.total == 2
    assert [item.data_date for item in result.items] == [start.data_date, end.data_date]
    assert [item.price for item in result.items] == [Decimal("100.00000000"), Decimal("101.00000000")]
    assert outside_before.data_date not in [item.data_date for item in result.items]
    assert outside_after.data_date not in [item.data_date for item in result.items]
    assert other_row.price not in [item.price for item in result.items]
    assert all(row.asset_id == asset.id for row in [start, end])


def test_history_valid_empty_range_returns_empty_response(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 9))

    result = _service(db_session).get_history(
        fund_code="AAL",
        start_date=date(2026, 8, 10),
        end_date=date(2026, 8, 11),
    )

    assert result.items == []
    assert result.total == 0


def test_history_start_after_end_raises_422(db_session: Session) -> None:
    with pytest.raises(HTTPException) as exc_info:
        _service(db_session).get_history(
            fund_code="AAL",
            start_date=date(2026, 8, 12),
            end_date=date(2026, 8, 11),
        )

    assert exc_info.value.status_code == 422