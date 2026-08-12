from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_daily_data import TefasFundDailyData
from src.repositories.tefas_fund_daily_data_repository import TefasFundDailyDataRepository


def _create_asset(db_session: Session, *, asset_code: str = "AAL") -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=f"{asset_code} Fund",
        asset_type="FUND",
        fund_kind="YAT",
        data_source="TEFAS",
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def _add_daily_data(
    db_session: Session,
    *,
    asset_id: int,
    data_date: date,
    price: Decimal = Decimal("10"),
) -> TefasFundDailyData:
    row = TefasFundDailyData(
        asset_id=asset_id,
        data_date=data_date,
        price=price,
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_get_latest_before_excludes_exact_date(db_session: Session) -> None:
    asset = _create_asset(db_session)
    exact = _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11))
    prior = _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 8))

    result = TefasFundDailyDataRepository(db_session).get_latest_before(
        asset_id=asset.id,
        data_date=exact.data_date,
    )

    assert result is not None
    assert result.id == prior.id


def test_get_latest_before_returns_closest_prior_observation(db_session: Session) -> None:
    asset = _create_asset(db_session)
    older = _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 1))
    closest = _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11))

    result = TefasFundDailyDataRepository(db_session).get_latest_before(
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
    )

    assert result is not None
    assert result.id == closest.id
    assert result.id != older.id


def test_get_latest_on_or_before_includes_exact_date(db_session: Session) -> None:
    asset = _create_asset(db_session)
    exact = _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10))

    result = TefasFundDailyDataRepository(db_session).get_latest_on_or_before(
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
    )

    assert result is not None
    assert result.id == exact.id


def test_get_latest_on_or_before_returns_closest_older_observation_if_exact_missing(db_session: Session) -> None:
    asset = _create_asset(db_session)
    closest = _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 8))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 1))

    result = TefasFundDailyDataRepository(db_session).get_latest_on_or_before(
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
    )

    assert result is not None
    assert result.id == closest.id


def test_list_latest_before_is_ordered_date_desc(db_session: Session) -> None:
    asset = _create_asset(db_session)
    for day in [1, 8, 5, 10]:
        _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, day))

    result = TefasFundDailyDataRepository(db_session).list_latest_before(
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        limit=10,
    )

    assert [row.data_date for row in result] == [
        date(2026, 8, 10),
        date(2026, 8, 8),
        date(2026, 8, 5),
        date(2026, 8, 1),
    ]


def test_list_latest_before_respects_limit(db_session: Session) -> None:
    asset = _create_asset(db_session)
    for day in [1, 2, 3]:
        _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, day))

    result = TefasFundDailyDataRepository(db_session).list_latest_before(
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        limit=2,
    )

    assert [row.data_date for row in result] == [date(2026, 8, 3), date(2026, 8, 2)]


def test_repository_methods_never_return_rows_from_another_asset(db_session: Session) -> None:
    asset = _create_asset(db_session, asset_code="AAL")
    other_asset = _create_asset(db_session, asset_code="AB1")
    own = _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 1))
    _add_daily_data(db_session, asset_id=other_asset.id, data_date=date(2026, 8, 10))
    repository = TefasFundDailyDataRepository(db_session)

    latest_before = repository.get_latest_before(asset_id=asset.id, data_date=date(2026, 8, 11))
    latest_on_or_before = repository.get_latest_on_or_before(asset_id=asset.id, data_date=date(2026, 8, 11))
    latest_list = repository.list_latest_before(asset_id=asset.id, data_date=date(2026, 8, 11), limit=5)

    assert latest_before is not None and latest_before.id == own.id
    assert latest_on_or_before is not None and latest_on_or_before.id == own.id
    assert [row.id for row in latest_list] == [own.id]


def test_weekend_calendar_gaps_do_not_affect_ordering(db_session: Session) -> None:
    asset = _create_asset(db_session)
    for item_date in [date(2026, 8, 3), date(2026, 8, 7), date(2026, 8, 10)]:
        _add_daily_data(db_session, asset_id=asset.id, data_date=item_date)

    result = TefasFundDailyDataRepository(db_session).list_latest_before(
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        limit=5,
    )

    assert [row.data_date for row in result] == [
        date(2026, 8, 10),
        date(2026, 8, 7),
        date(2026, 8, 3),
    ]


def test_zero_and_negative_decimal_values_are_not_filtered_out(db_session: Session) -> None:
    asset = _create_asset(db_session)
    zero = _add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 10),
        price=Decimal("0"),
    )
    negative = _add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 9),
        price=Decimal("-1.25"),
    )

    result = TefasFundDailyDataRepository(db_session).list_latest_before(
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        limit=5,
    )

    assert [row.id for row in result] == [zero.id, negative.id]
    assert [row.price for row in result] == [Decimal("0E-8"), Decimal("-1.25000000")]


def test_existing_get_by_asset_and_date_still_works(db_session: Session) -> None:
    asset = _create_asset(db_session)
    daily_data = _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11))

    result = TefasFundDailyDataRepository(db_session).get_by_asset_and_date(
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
    )

    assert result is not None
    assert result.id == daily_data.id
