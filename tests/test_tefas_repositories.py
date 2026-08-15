from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_daily_data import TefasFundDailyData
from src.model.tefas_fund_detail_snapshot import TefasFundDetailSnapshot
from src.repositories.asset_repository import AssetRepository
from src.repositories.tefas_fund_daily_data_repository import TefasFundDailyDataRepository
from src.repositories.tefas_fund_detail_snapshot_repository import TefasFundDetailSnapshotRepository


TEFAS_DATA_DATE = date(2026, 4, 24)
OBSERVED_AT = datetime(2026, 8, 14, 9, 0, tzinfo=timezone.utc)


def _build_asset(**overrides: object) -> Asset:
    values = {
        "asset_code": "AAL",
        "asset_name": "Example Fund",
        "asset_type": "FUND",
        "fund_kind": "YAT",
        "data_source": "TEFAS",
        "is_active": True,
    }
    values.update(overrides)
    return Asset(**values)


def _build_daily_data(*, asset_id: int) -> TefasFundDailyData:
    return TefasFundDailyData(
        asset_id=asset_id,
        data_date=TEFAS_DATA_DATE,
        price=Decimal("12.34567890"),
        shares_outstanding=Decimal("1000.0000"),
        investor_count=100,
        portfolio_size=Decimal("12345.6700"),
        exchange_bulletin_price=None,
    )


def _build_detail_snapshot(
    *,
    asset_id: int,
    observed_at: datetime = OBSERVED_AT,
) -> TefasFundDetailSnapshot:
    return TefasFundDetailSnapshot(
        asset_id=asset_id,
        fund_category="Serbest Fon",
        category_rank=0,
        category_fund_count=42,
        market_share_raw=Decimal("0.0100000000"),
        observed_at=observed_at,
    )

def test_asset_repository_add_assigns_id_after_flush(db_session: Session) -> None:
    repository = AssetRepository(db_session)
    asset = _build_asset()

    result = repository.add(asset)

    assert result is asset
    assert asset.id is not None



def test_asset_repository_get_by_source_and_code_returns_matching_asset(db_session: Session) -> None:
    repository = AssetRepository(db_session)
    asset = _build_asset()
    repository.add(asset)

    result = repository.get_by_source_and_code(
        data_source="TEFAS",
        asset_code="AAL",
    )

    assert result is not None
    assert result.id == asset.id



def test_asset_repository_get_by_source_and_code_returns_none_when_missing(db_session: Session) -> None:
    repository = AssetRepository(db_session)

    result = repository.get_by_source_and_code(
        data_source="TEFAS",
        asset_code="AAL",
    )

    assert result is None



def test_asset_repository_list_active_by_data_source_returns_active_tefas_asset(db_session: Session) -> None:
    repository = AssetRepository(db_session)
    asset = _build_asset(asset_code="AAL", data_source="TEFAS", is_active=True)
    repository.add(asset)

    result = repository.list_active_by_data_source("TEFAS")

    assert [item.asset_code for item in result] == ["AAL"]



def test_asset_repository_list_active_by_data_source_skips_inactive_tefas_asset(db_session: Session) -> None:
    repository = AssetRepository(db_session)
    repository.add(_build_asset(asset_code="AAL", data_source="TEFAS", is_active=False))

    result = repository.list_active_by_data_source("TEFAS")

    assert result == []



def test_asset_repository_list_active_by_data_source_skips_active_non_tefas_asset(db_session: Session) -> None:
    repository = AssetRepository(db_session)
    repository.add(_build_asset(asset_code="AAL", data_source="MANUAL", is_active=True))

    result = repository.list_active_by_data_source("TEFAS")

    assert result == []



def test_asset_repository_list_active_by_data_source_orders_by_asset_code(db_session: Session) -> None:
    repository = AssetRepository(db_session)
    repository.add(_build_asset(asset_code="BLH"))
    repository.add(_build_asset(asset_code="AAL"))
    repository.add(_build_asset(asset_code="AB1"))

    result = repository.list_active_by_data_source("TEFAS")

    assert [asset.asset_code for asset in result] == ["AAL", "AB1", "BLH"]



def test_asset_repository_list_active_by_data_source_includes_missing_fund_kind(db_session: Session) -> None:
    repository = AssetRepository(db_session)
    repository.add(_build_asset(asset_code="AAL", fund_kind=None, data_source="TEFAS", is_active=True))

    result = repository.list_active_by_data_source("TEFAS")

    assert [asset.asset_code for asset in result] == ["AAL"]
    assert result[0].fund_kind is None



def test_asset_repository_list_active_by_data_source_does_not_commit(
    db_session: Session,
    monkeypatch,
) -> None:
    repository = AssetRepository(db_session)
    repository.add(_build_asset(asset_code="AAL"))
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)

    repository.list_active_by_data_source("TEFAS")

    assert commit_calls == 0



def test_tefas_fund_daily_data_repository_add_assigns_id_for_existing_asset(db_session: Session) -> None:
    asset = _build_asset()
    db_session.add(asset)
    db_session.flush()

    repository = TefasFundDailyDataRepository(db_session)
    daily_data = _build_daily_data(asset_id=asset.id)

    result = repository.add(daily_data)

    assert result is daily_data
    assert daily_data.id is not None
    assert daily_data.asset_id == asset.id



def test_tefas_fund_daily_data_repository_get_by_asset_and_date_returns_matching_row(db_session: Session) -> None:
    asset = _build_asset()
    db_session.add(asset)
    db_session.flush()

    repository = TefasFundDailyDataRepository(db_session)
    daily_data = _build_daily_data(asset_id=asset.id)
    repository.add(daily_data)

    result = repository.get_by_asset_and_date(
        asset_id=asset.id,
        data_date=TEFAS_DATA_DATE,
    )

    assert result is not None
    assert result.id == daily_data.id



def test_tefas_fund_daily_data_repository_get_by_asset_and_date_returns_none_when_missing(db_session: Session) -> None:
    asset = _build_asset()
    db_session.add(asset)
    db_session.flush()

    repository = TefasFundDailyDataRepository(db_session)

    result = repository.get_by_asset_and_date(
        asset_id=asset.id,
        data_date=TEFAS_DATA_DATE,
    )

    assert result is None

def test_tefas_fund_detail_snapshot_repository_add_assigns_id_for_existing_asset(
    db_session: Session,
) -> None:
    asset = _build_asset()
    db_session.add(asset)
    db_session.flush()

    repository = TefasFundDetailSnapshotRepository(db_session)
    snapshot = _build_detail_snapshot(asset_id=asset.id)

    result = repository.add(snapshot)

    assert result is snapshot
    assert snapshot.id is not None
    assert snapshot.asset_id == asset.id
    assert snapshot.category_rank == 0
    assert snapshot.market_share_raw == Decimal("0.0100000000")


def test_tefas_fund_detail_snapshot_repository_get_by_asset_and_observed_at_returns_matching_row(
    db_session: Session,
) -> None:
    asset = _build_asset()
    db_session.add(asset)
    db_session.flush()

    repository = TefasFundDetailSnapshotRepository(db_session)
    snapshot = _build_detail_snapshot(asset_id=asset.id)
    repository.add(snapshot)

    result = repository.get_by_asset_and_observed_at(
        asset_id=asset.id,
        observed_at=OBSERVED_AT,
    )

    assert result is not None
    assert result.id == snapshot.id


def test_tefas_fund_detail_snapshot_repository_get_by_asset_and_observed_at_filters_asset(
    db_session: Session,
) -> None:
    matching_asset = _build_asset(asset_code="AAL")
    other_asset = _build_asset(asset_code="BBL")
    db_session.add_all([matching_asset, other_asset])
    db_session.flush()

    repository = TefasFundDetailSnapshotRepository(db_session)
    repository.add(_build_detail_snapshot(asset_id=other_asset.id))

    result = repository.get_by_asset_and_observed_at(
        asset_id=matching_asset.id,
        observed_at=OBSERVED_AT,
    )

    assert result is None


def test_tefas_fund_detail_snapshot_repository_get_by_asset_and_observed_at_filters_observed_at(
    db_session: Session,
) -> None:
    asset = _build_asset()
    db_session.add(asset)
    db_session.flush()

    repository = TefasFundDetailSnapshotRepository(db_session)
    repository.add(_build_detail_snapshot(asset_id=asset.id))

    result = repository.get_by_asset_and_observed_at(
        asset_id=asset.id,
        observed_at=datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc),
    )

    assert result is None


def test_tefas_fund_detail_snapshot_repository_get_latest_for_asset_returns_most_recent_observation(
    db_session: Session,
) -> None:
    asset = _build_asset()
    db_session.add(asset)
    db_session.flush()

    repository = TefasFundDetailSnapshotRepository(db_session)
    older_snapshot = _build_detail_snapshot(
        asset_id=asset.id,
        observed_at=datetime(2026, 8, 14, 9, 0, tzinfo=timezone.utc),
    )
    latest_snapshot = _build_detail_snapshot(
        asset_id=asset.id,
        observed_at=datetime(2026, 8, 14, 11, 0, tzinfo=timezone.utc),
    )
    repository.add(older_snapshot)
    repository.add(latest_snapshot)

    result = repository.get_latest_for_asset(asset.id)

    assert result is not None
    assert result.id == latest_snapshot.id


def test_tefas_fund_detail_snapshot_repository_get_latest_for_asset_filters_asset(
    db_session: Session,
) -> None:
    matching_asset = _build_asset(asset_code="AAL")
    other_asset = _build_asset(asset_code="BBL")
    db_session.add_all([matching_asset, other_asset])
    db_session.flush()

    repository = TefasFundDetailSnapshotRepository(db_session)
    matching_snapshot = _build_detail_snapshot(
        asset_id=matching_asset.id,
        observed_at=datetime(2026, 8, 14, 9, 0, tzinfo=timezone.utc),
    )
    repository.add(matching_snapshot)
    repository.add(
        _build_detail_snapshot(
            asset_id=other_asset.id,
            observed_at=datetime(2026, 8, 14, 11, 0, tzinfo=timezone.utc),
        )
    )

    result = repository.get_latest_for_asset(matching_asset.id)

    assert result is not None
    assert result.id == matching_snapshot.id


def test_tefas_fund_detail_snapshot_repository_get_latest_for_asset_returns_none_when_missing(
    db_session: Session,
) -> None:
    repository = TefasFundDetailSnapshotRepository(db_session)

    result = repository.get_latest_for_asset(1)

    assert result is None


def test_tefas_fund_detail_snapshot_repository_does_not_commit(
    db_session: Session,
    monkeypatch,
) -> None:
    asset = _build_asset()
    db_session.add(asset)
    db_session.flush()
    repository = TefasFundDetailSnapshotRepository(db_session)
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)

    repository.add(_build_detail_snapshot(asset_id=asset.id))
    repository.get_by_asset_and_observed_at(
        asset_id=asset.id,
        observed_at=OBSERVED_AT,
    )
    repository.get_latest_for_asset(asset.id)

    assert commit_calls == 0
