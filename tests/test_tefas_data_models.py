from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_daily_data import TefasFundDailyData


def test_asset_can_be_inserted_with_expected_defaults(db_session: Session) -> None:
    asset = Asset(
        asset_code="AAL",
        asset_name="Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        data_source="TEFAS",
    )

    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)

    assert asset.id is not None
    assert asset.is_active is True
    assert asset.currency is None


def test_asset_unique_constraint_rejects_same_data_source_and_asset_code(db_session: Session) -> None:
    first_asset = Asset(
        asset_code="AAL",
        asset_name="Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        data_source="TEFAS",
    )
    second_asset = Asset(
        asset_code="AAL",
        asset_name="Another Fund",
        asset_type="FUND",
        fund_kind="YAT",
        data_source="TEFAS",
    )

    db_session.add(first_asset)
    db_session.commit()

    db_session.add(second_asset)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_asset_code_may_be_reused_across_different_data_sources(db_session: Session) -> None:
    tefas_asset = Asset(
        asset_code="AAL",
        asset_name="Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        data_source="TEFAS",
    )
    other_asset = Asset(
        asset_code="AAL",
        asset_name="Another Source Fund",
        asset_type="FUND",
        fund_kind="YAT",
        data_source="ANOTHER_SOURCE",
    )

    db_session.add_all([tefas_asset, other_asset])
    db_session.commit()

    assert tefas_asset.id is not None
    assert other_asset.id is not None


def test_tefas_fund_daily_data_can_be_inserted_for_existing_asset(db_session: Session) -> None:
    asset = Asset(
        asset_code="AAL",
        asset_name="Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        data_source="TEFAS",
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)

    daily_data = TefasFundDailyData(
        asset_id=asset.id,
        data_date=date(2026, 4, 24),
        price=Decimal("12.34567890"),
        shares_outstanding=Decimal("1000.0000"),
        investor_count=100,
        portfolio_size=Decimal("12345.6700"),
        exchange_bulletin_price=None,
    )

    db_session.add(daily_data)
    db_session.commit()
    db_session.refresh(daily_data)

    assert daily_data.id is not None
    assert daily_data.asset_id == asset.id
    assert daily_data.data_date == date(2026, 4, 24)
    assert daily_data.price == Decimal("12.34567890")
    assert daily_data.shares_outstanding == Decimal("1000.0000")
    assert daily_data.investor_count == 100
    assert daily_data.portfolio_size == Decimal("12345.6700")
    assert daily_data.exchange_bulletin_price is None


def test_tefas_fund_daily_data_unique_constraint_rejects_same_asset_and_date(db_session: Session) -> None:
    asset = Asset(
        asset_code="AAL",
        asset_name="Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        data_source="TEFAS",
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)

    first_daily_data = TefasFundDailyData(
        asset_id=asset.id,
        data_date=date(2026, 4, 24),
        price=Decimal("12.34567890"),
    )
    second_daily_data = TefasFundDailyData(
        asset_id=asset.id,
        data_date=date(2026, 4, 24),
        price=Decimal("22.34567890"),
    )

    db_session.add(first_daily_data)
    db_session.commit()

    db_session.add(second_daily_data)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_tefas_fund_daily_data_asset_id_foreign_key_targets_assets_id() -> None:
    foreign_keys = TefasFundDailyData.__table__.c.asset_id.foreign_keys

    assert len(foreign_keys) == 1
    foreign_key = next(iter(foreign_keys))
    assert foreign_key.target_fullname == "assets.id"
