from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_daily_data import TefasFundDailyData
from src.repositories.tefas_fund_daily_data_repository import TefasFundDailyDataRepository


def _create_asset(
    db_session: Session,
    *,
    asset_code: str = "AAL",
    data_source: str = "TEFAS",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=f"{asset_code} Fund",
        asset_type="FUND",
        fund_kind="YAT",
        data_source=data_source,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def _daily_data(
    *,
    asset_id: int,
    data_date: date,
    price: Decimal = Decimal("100.00000000"),
) -> TefasFundDailyData:
    return TefasFundDailyData(
        asset_id=asset_id,
        data_date=data_date,
        price=price,
        shares_outstanding=Decimal("1000.0000"),
        investor_count=100,
        portfolio_size=Decimal("10000.0000"),
    )


def test_get_latest_by_asset_returns_latest_date(db_session: Session) -> None:
    asset = _create_asset(db_session)
    other_asset = _create_asset(db_session, asset_code="BLH")
    repository = TefasFundDailyDataRepository(db_session)
    older = repository.add(_daily_data(asset_id=asset.id, data_date=date(2026, 8, 10)))
    latest = repository.add(_daily_data(asset_id=asset.id, data_date=date(2026, 8, 12)))
    other_latest = repository.add(_daily_data(asset_id=other_asset.id, data_date=date(2026, 8, 13)))

    result = repository.get_latest_by_asset(asset_id=asset.id)

    assert latest.id > older.id
    assert result is latest
    assert result is not other_latest


def test_list_by_asset_between_is_inclusive_ordered_and_asset_isolated(
    db_session: Session,
) -> None:
    asset = _create_asset(db_session)
    other_asset = _create_asset(db_session, asset_code="BLH")
    repository = TefasFundDailyDataRepository(db_session)
    outside_before = repository.add(_daily_data(asset_id=asset.id, data_date=date(2026, 8, 9)))
    start = repository.add(_daily_data(asset_id=asset.id, data_date=date(2026, 8, 10)))
    middle = repository.add(_daily_data(asset_id=asset.id, data_date=date(2026, 8, 11)))
    end = repository.add(_daily_data(asset_id=asset.id, data_date=date(2026, 8, 12)))
    outside_after = repository.add(_daily_data(asset_id=asset.id, data_date=date(2026, 8, 13)))
    other_asset_row = repository.add(_daily_data(asset_id=other_asset.id, data_date=date(2026, 8, 11)))

    result = repository.list_by_asset_between(
        asset_id=asset.id,
        start_date=date(2026, 8, 10),
        end_date=date(2026, 8, 12),
    )

    assert result == [start, middle, end]
    assert outside_before not in result
    assert outside_after not in result
    assert other_asset_row not in result