from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import Numeric
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_allocation_data import TefasFundAllocationData


TEFAS_DATE = date(2026, 8, 11)


def _create_asset(db_session: Session, asset_code: str = "AAL") -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name="Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        data_source="TEFAS",
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def test_table_name_is_expected() -> None:
    assert TefasFundAllocationData.__tablename__ == "tefas_fund_allocation_data"


def test_allocation_percentage_uses_numeric_18_6() -> None:
    column = TefasFundAllocationData.__table__.c.allocation_percentage

    assert isinstance(column.type, Numeric)
    assert column.type.precision == 18
    assert column.type.scale == 6


def test_unique_constraint_exists_for_asset_date_and_raw_field() -> None:
    constraints = list(TefasFundAllocationData.__table__.constraints)
    unique_constraint = next(
        constraint
        for constraint in constraints
        if getattr(constraint, "name", None) == "uq_tefas_fund_allocation_data_asset_date_field"
    )

    assert tuple(column.name for column in unique_constraint.columns) == (
        "asset_id",
        "data_date",
        "raw_field_name",
    )


def test_negative_allocation_percentage_can_be_persisted(db_session: Session) -> None:
    asset = _create_asset(db_session)
    allocation = TefasFundAllocationData(
        asset_id=asset.id,
        data_date=TEFAS_DATE,
        raw_field_name="r",
        allocation_percentage=Decimal("-12.340000"),
    )

    db_session.add(allocation)
    db_session.commit()
    db_session.refresh(allocation)

    assert allocation.allocation_percentage == Decimal("-12.340000")
    assert isinstance(allocation.allocation_percentage, Decimal)


def test_zero_allocation_percentage_can_be_persisted(db_session: Session) -> None:
    asset = _create_asset(db_session)
    allocation = TefasFundAllocationData(
        asset_id=asset.id,
        data_date=TEFAS_DATE,
        raw_field_name="hs",
        allocation_percentage=Decimal("0.000000"),
    )

    db_session.add(allocation)
    db_session.commit()
    db_session.refresh(allocation)

    assert allocation.allocation_percentage == Decimal("0.000000")
    assert isinstance(allocation.allocation_percentage, Decimal)


def test_multiple_raw_fields_can_exist_for_same_asset_and_date(db_session: Session) -> None:
    asset = _create_asset(db_session)
    first = TefasFundAllocationData(
        asset_id=asset.id,
        data_date=TEFAS_DATE,
        raw_field_name="hs",
        allocation_percentage=Decimal("10.000000"),
    )
    second = TefasFundAllocationData(
        asset_id=asset.id,
        data_date=TEFAS_DATE,
        raw_field_name="gyy",
        allocation_percentage=Decimal("20.000000"),
    )

    db_session.add_all([first, second])
    db_session.commit()

    rows = db_session.query(TefasFundAllocationData).filter_by(asset_id=asset.id, data_date=TEFAS_DATE).all()

    assert len(rows) == 2


def test_same_asset_date_and_raw_field_cannot_be_duplicated(db_session: Session) -> None:
    asset = _create_asset(db_session)
    first = TefasFundAllocationData(
        asset_id=asset.id,
        data_date=TEFAS_DATE,
        raw_field_name="hs",
        allocation_percentage=Decimal("10.000000"),
    )
    second = TefasFundAllocationData(
        asset_id=asset.id,
        data_date=TEFAS_DATE,
        raw_field_name="hs",
        allocation_percentage=Decimal("20.000000"),
    )

    db_session.add(first)
    db_session.commit()

    db_session.add(second)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_allocation_percentage_is_non_null(db_session: Session) -> None:
    asset = _create_asset(db_session)
    allocation = TefasFundAllocationData(
        asset_id=asset.id,
        data_date=TEFAS_DATE,
        raw_field_name="hs",
        allocation_percentage=None,
    )

    db_session.add(allocation)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
