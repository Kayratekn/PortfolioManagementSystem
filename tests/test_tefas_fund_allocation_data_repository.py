from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.repositories.tefas_fund_allocation_data_repository import (
    TefasFundAllocationDataRepository,
    TefasFundAllocationRowCreate,
)


TEFAS_DATE = date(2026, 8, 11)
OTHER_DATE = date(2026, 8, 10)


def _create_asset(db_session: Session, *, asset_code: str) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=f"Fund {asset_code}",
        asset_type="FUND",
        fund_kind="YAT",
        data_source="TEFAS",
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def _row(*, asset_id: int, data_date: date, raw_field_name: str, allocation_percentage: str) -> TefasFundAllocationRowCreate:
    return TefasFundAllocationRowCreate(
        asset_id=asset_id,
        data_date=data_date,
        raw_field_name=raw_field_name,
        allocation_percentage=Decimal(allocation_percentage),
    )


def test_list_by_asset_and_date_returns_only_requested_asset_and_date(db_session: Session) -> None:
    first_asset = _create_asset(db_session, asset_code="AAL")
    second_asset = _create_asset(db_session, asset_code="BBL")
    repository = TefasFundAllocationDataRepository(db_session)

    repository.add_allocation_rows(
        [
            _row(asset_id=first_asset.id, data_date=TEFAS_DATE, raw_field_name="hs", allocation_percentage="80.000000"),
            _row(asset_id=first_asset.id, data_date=OTHER_DATE, raw_field_name="hs", allocation_percentage="50.000000"),
            _row(asset_id=second_asset.id, data_date=TEFAS_DATE, raw_field_name="hs", allocation_percentage="20.000000"),
        ]
    )

    result = repository.list_by_asset_and_date(asset_id=first_asset.id, data_date=TEFAS_DATE)

    assert len(result) == 1
    assert result[0].asset_id == first_asset.id
    assert result[0].data_date == TEFAS_DATE
    assert result[0].raw_field_name == "hs"


def test_list_by_asset_and_date_returns_rows_in_raw_field_name_order(db_session: Session) -> None:
    asset = _create_asset(db_session, asset_code="AAL")
    repository = TefasFundAllocationDataRepository(db_session)

    repository.add_allocation_rows(
        [
            _row(asset_id=asset.id, data_date=TEFAS_DATE, raw_field_name="vmtl", allocation_percentage="20.000000"),
            _row(asset_id=asset.id, data_date=TEFAS_DATE, raw_field_name="hs", allocation_percentage="80.000000"),
            _row(asset_id=asset.id, data_date=TEFAS_DATE, raw_field_name="bb", allocation_percentage="1.000000"),
        ]
    )

    result = repository.list_by_asset_and_date(asset_id=asset.id, data_date=TEFAS_DATE)

    assert [row.raw_field_name for row in result] == ["bb", "hs", "vmtl"]


def test_different_dates_for_same_asset_remain_separate(db_session: Session) -> None:
    asset = _create_asset(db_session, asset_code="AAL")
    repository = TefasFundAllocationDataRepository(db_session)

    repository.add_allocation_rows(
        [
            _row(asset_id=asset.id, data_date=TEFAS_DATE, raw_field_name="hs", allocation_percentage="80.000000"),
            _row(asset_id=asset.id, data_date=OTHER_DATE, raw_field_name="hs", allocation_percentage="20.000000"),
        ]
    )

    today_rows = repository.list_by_asset_and_date(asset_id=asset.id, data_date=TEFAS_DATE)
    other_rows = repository.list_by_asset_and_date(asset_id=asset.id, data_date=OTHER_DATE)

    assert len(today_rows) == 1
    assert today_rows[0].allocation_percentage == Decimal("80.000000")
    assert len(other_rows) == 1
    assert other_rows[0].allocation_percentage == Decimal("20.000000")


def test_different_assets_for_same_date_remain_separate(db_session: Session) -> None:
    first_asset = _create_asset(db_session, asset_code="AAL")
    second_asset = _create_asset(db_session, asset_code="BBL")
    repository = TefasFundAllocationDataRepository(db_session)

    repository.add_allocation_rows(
        [
            _row(asset_id=first_asset.id, data_date=TEFAS_DATE, raw_field_name="hs", allocation_percentage="80.000000"),
            _row(asset_id=second_asset.id, data_date=TEFAS_DATE, raw_field_name="hs", allocation_percentage="20.000000"),
        ]
    )

    first_rows = repository.list_by_asset_and_date(asset_id=first_asset.id, data_date=TEFAS_DATE)
    second_rows = repository.list_by_asset_and_date(asset_id=second_asset.id, data_date=TEFAS_DATE)

    assert len(first_rows) == 1
    assert first_rows[0].allocation_percentage == Decimal("80.000000")
    assert len(second_rows) == 1
    assert second_rows[0].allocation_percentage == Decimal("20.000000")


def test_zero_decimal_persists_unchanged(db_session: Session) -> None:
    asset = _create_asset(db_session, asset_code="AAL")
    repository = TefasFundAllocationDataRepository(db_session)

    repository.add_allocation_rows(
        [_row(asset_id=asset.id, data_date=TEFAS_DATE, raw_field_name="hs", allocation_percentage="0.000000")]
    )

    result = repository.list_by_asset_and_date(asset_id=asset.id, data_date=TEFAS_DATE)

    assert result[0].allocation_percentage == Decimal("0.000000")


def test_negative_decimal_persists_unchanged(db_session: Session) -> None:
    asset = _create_asset(db_session, asset_code="AAL")
    repository = TefasFundAllocationDataRepository(db_session)

    repository.add_allocation_rows(
        [_row(asset_id=asset.id, data_date=TEFAS_DATE, raw_field_name="r", allocation_percentage="-5.500000")]
    )

    result = repository.list_by_asset_and_date(asset_id=asset.id, data_date=TEFAS_DATE)

    assert result[0].allocation_percentage == Decimal("-5.500000")


def test_replace_for_asset_and_date_removes_stale_fields(db_session: Session) -> None:
    asset = _create_asset(db_session, asset_code="AAL")
    repository = TefasFundAllocationDataRepository(db_session)

    repository.add_allocation_rows(
        [
            _row(asset_id=asset.id, data_date=TEFAS_DATE, raw_field_name="hs", allocation_percentage="80.000000"),
            _row(asset_id=asset.id, data_date=TEFAS_DATE, raw_field_name="vmtl", allocation_percentage="20.000000"),
        ]
    )
    db_session.commit()

    repository.replace_for_asset_and_date(
        asset_id=asset.id,
        data_date=TEFAS_DATE,
        rows=[
            _row(asset_id=asset.id, data_date=TEFAS_DATE, raw_field_name="hs", allocation_percentage="100.000000"),
        ],
    )
    db_session.commit()

    result = repository.list_by_asset_and_date(asset_id=asset.id, data_date=TEFAS_DATE)

    assert [(row.raw_field_name, row.allocation_percentage) for row in result] == [
        ("hs", Decimal("100.000000")),
    ]


def test_replace_for_asset_and_date_accepts_unresolved_raw_fields(db_session: Session) -> None:
    asset = _create_asset(db_session, asset_code="AAL")
    repository = TefasFundAllocationDataRepository(db_session)

    repository.replace_for_asset_and_date(
        asset_id=asset.id,
        data_date=TEFAS_DATE,
        rows=[
            _row(asset_id=asset.id, data_date=TEFAS_DATE, raw_field_name="bb", allocation_percentage="1.250000"),
        ],
    )
    db_session.commit()

    result = repository.list_by_asset_and_date(asset_id=asset.id, data_date=TEFAS_DATE)

    assert len(result) == 1
    assert result[0].raw_field_name == "bb"
    assert result[0].allocation_percentage == Decimal("1.250000")


def test_duplicate_asset_date_raw_field_cannot_create_duplicate_rows(db_session: Session) -> None:
    asset = _create_asset(db_session, asset_code="AAL")
    repository = TefasFundAllocationDataRepository(db_session)

    repository.add_allocation_rows(
        [_row(asset_id=asset.id, data_date=TEFAS_DATE, raw_field_name="hs", allocation_percentage="10.000000")]
    )
    db_session.commit()

    with pytest.raises(IntegrityError):
        repository.add_allocation_rows(
            [_row(asset_id=asset.id, data_date=TEFAS_DATE, raw_field_name="hs", allocation_percentage="20.000000")]
        )
        db_session.commit()
    db_session.rollback()


def test_repository_operations_do_not_commit(db_session: Session) -> None:
    asset = _create_asset(db_session, asset_code="AAL")
    repository = TefasFundAllocationDataRepository(db_session)

    repository.add_allocation_rows(
        [_row(asset_id=asset.id, data_date=TEFAS_DATE, raw_field_name="hs", allocation_percentage="10.000000")]
    )

    db_session.rollback()

    result = repository.list_by_asset_and_date(asset_id=asset.id, data_date=TEFAS_DATE)

    assert result == []
