from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import inspect

from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_management_fee_history import TefasManagementFeeHistory
from src.repositories.tefas_management_fee_history_repository import (
    TefasManagementFeeHistoryRepository,
)


def _create_asset(
    db_session: Session,
    *,
    asset_code: str = "AAL",
) -> Asset:
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


def _history(
    *,
    asset_id: int,
    management_fee_percentage: Decimal = Decimal("1"),
    first_observed_at: datetime = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
    last_observed_at: datetime = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
    closed_at: datetime | None = None,
    source_endpoint: str = "fonYonetimBazliBilgiGetir",
    source_field_name: str = "uygulananYu1Y",
) -> TefasManagementFeeHistory:
    return TefasManagementFeeHistory(
        asset_id=asset_id,
        management_fee_percentage=management_fee_percentage,
        source_endpoint=source_endpoint,
        source_field_name=source_field_name,
        first_observed_at=first_observed_at,
        last_observed_at=last_observed_at,
        closed_at=closed_at,
    )


def test_add_and_retrieve_current_row(db_session: Session) -> None:
    asset = _create_asset(db_session)
    repository = TefasManagementFeeHistoryRepository(db_session)
    history = _history(asset_id=asset.id)

    result = repository.add(history)
    current = repository.get_current_for_asset(asset_id=asset.id)

    assert result is history
    assert history.id is not None
    assert current is not None
    assert current.id == history.id
    assert current.management_fee_percentage == Decimal("1")


def test_get_current_for_asset_returns_none_when_absent(db_session: Session) -> None:
    asset = _create_asset(db_session)
    repository = TefasManagementFeeHistoryRepository(db_session)

    result = repository.get_current_for_asset(asset_id=asset.id)

    assert result is None


def test_closed_row_is_not_returned_as_current(db_session: Session) -> None:
    asset = _create_asset(db_session)
    repository = TefasManagementFeeHistoryRepository(db_session)
    repository.add(
        _history(
            asset_id=asset.id,
            closed_at=datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc),
        )
    )

    result = repository.get_current_for_asset(asset_id=asset.id)

    assert result is None


def test_list_by_asset_returns_only_requested_asset(db_session: Session) -> None:
    first_asset = _create_asset(db_session, asset_code="AAL")
    second_asset = _create_asset(db_session, asset_code="AB1")
    repository = TefasManagementFeeHistoryRepository(db_session)
    first_history = repository.add(_history(asset_id=first_asset.id))
    repository.add(_history(asset_id=second_asset.id, management_fee_percentage=Decimal("2")))

    result = repository.list_by_asset(asset_id=first_asset.id)

    assert [row.id for row in result] == [first_history.id]


def test_list_by_asset_uses_deterministic_chronological_order(db_session: Session) -> None:
    asset = _create_asset(db_session)
    repository = TefasManagementFeeHistoryRepository(db_session)
    second = repository.add(
        _history(
            asset_id=asset.id,
            management_fee_percentage=Decimal("2"),
            first_observed_at=datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc),
            last_observed_at=datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc),
        )
    )
    first = repository.add(
        _history(
            asset_id=asset.id,
            management_fee_percentage=Decimal("1"),
            first_observed_at=datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
            last_observed_at=datetime(2026, 8, 8, 9, 0, tzinfo=timezone.utc),
            closed_at=datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc),
        )
    )

    result = repository.list_by_asset(asset_id=asset.id)

    assert [row.id for row in result] == [first.id, second.id]


def test_add_does_not_commit(db_session: Session, monkeypatch) -> None:
    asset = _create_asset(db_session)
    repository = TefasManagementFeeHistoryRepository(db_session)
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)

    repository.add(_history(asset_id=asset.id))

    assert commit_calls == 0


def test_repository_does_not_contain_transition_business_logic() -> None:
    source = inspect.getsource(TefasManagementFeeHistoryRepository)

    assert "management_fee_percentage ==" not in source
    assert "last_observed_at =" not in source
    assert "closed_at =" not in source


def test_source_fields_round_trip(db_session: Session) -> None:
    asset = _create_asset(db_session)
    repository = TefasManagementFeeHistoryRepository(db_session)
    history = repository.add(
        _history(
            asset_id=asset.id,
            source_endpoint="fonYonetimBazliBilgiGetir",
            source_field_name="uygulananYu1Y",
        )
    )

    db_session.expire_all()
    result = repository.get_current_for_asset(asset_id=asset.id)

    assert result is not None
    assert result.id == history.id
    assert result.source_endpoint == "fonYonetimBazliBilgiGetir"
    assert result.source_field_name == "uygulananYu1Y"


def test_observation_timestamps_round_trip(db_session: Session) -> None:
    asset = _create_asset(db_session)
    repository = TefasManagementFeeHistoryRepository(db_session)
    first_seen = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    last_seen = datetime(2026, 8, 8, 9, 0, tzinfo=timezone.utc)
    closed_at = datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc)
    repository.add(
        _history(
            asset_id=asset.id,
            first_observed_at=first_seen,
            last_observed_at=last_seen,
            closed_at=closed_at,
        )
    )

    db_session.expire_all()
    result = repository.list_by_asset(asset_id=asset.id)[0]

    assert result.first_observed_at.replace(tzinfo=timezone.utc) == first_seen
    assert result.last_observed_at.replace(tzinfo=timezone.utc) == last_seen
    assert result.closed_at is not None
    assert result.closed_at.replace(tzinfo=timezone.utc) == closed_at
