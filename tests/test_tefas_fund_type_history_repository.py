from __future__ import annotations

from datetime import datetime, timezone
import inspect

from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_type_history import TefasFundTypeHistory
from src.repositories.tefas_fund_type_history_repository import TefasFundTypeHistoryRepository


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
    fund_type_name: str = "Para Piyasasi Semsiye Fonu",
    first_observed_at: datetime = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
    last_observed_at: datetime = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
    closed_at: datetime | None = None,
    source_endpoint: str | None = None,
    source_field_name: str | None = None,
) -> TefasFundTypeHistory:
    kwargs: dict[str, object] = {
        "asset_id": asset_id,
        "fund_type_name": fund_type_name,
        "first_observed_at": first_observed_at,
        "last_observed_at": last_observed_at,
        "closed_at": closed_at,
    }
    if source_endpoint is not None:
        kwargs["source_endpoint"] = source_endpoint
    if source_field_name is not None:
        kwargs["source_field_name"] = source_field_name
    return TefasFundTypeHistory(**kwargs)


def test_add_and_retrieve_current_row(db_session: Session) -> None:
    asset = _create_asset(db_session)
    repository = TefasFundTypeHistoryRepository(db_session)
    history = _history(asset_id=asset.id)

    result = repository.add(history)
    current = repository.get_current_for_asset(asset_id=asset.id)

    assert result is history
    assert history.id is not None
    assert current is not None
    assert current.id == history.id
    assert current.fund_type_name == "Para Piyasasi Semsiye Fonu"


def test_get_current_for_asset_returns_none_when_absent(db_session: Session) -> None:
    asset = _create_asset(db_session)
    repository = TefasFundTypeHistoryRepository(db_session)

    result = repository.get_current_for_asset(asset_id=asset.id)

    assert result is None


def test_closed_row_is_not_returned_as_current(db_session: Session) -> None:
    asset = _create_asset(db_session)
    repository = TefasFundTypeHistoryRepository(db_session)
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
    repository = TefasFundTypeHistoryRepository(db_session)
    first_history = repository.add(_history(asset_id=first_asset.id, fund_type_name="Type A"))
    repository.add(_history(asset_id=second_asset.id, fund_type_name="Type B"))

    result = repository.list_by_asset(asset_id=first_asset.id)

    assert [row.id for row in result] == [first_history.id]


def test_list_by_asset_uses_deterministic_chronological_order(db_session: Session) -> None:
    asset = _create_asset(db_session)
    repository = TefasFundTypeHistoryRepository(db_session)
    second = repository.add(
        _history(
            asset_id=asset.id,
            fund_type_name="Type B",
            first_observed_at=datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc),
            last_observed_at=datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc),
        )
    )
    first = repository.add(
        _history(
            asset_id=asset.id,
            fund_type_name="Type A",
            first_observed_at=datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
            last_observed_at=datetime(2026, 8, 8, 9, 0, tzinfo=timezone.utc),
            closed_at=datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc),
        )
    )

    result = repository.list_by_asset(asset_id=asset.id)

    assert [row.id for row in result] == [first.id, second.id]


def test_open_and_closed_rows_both_appear_in_history(db_session: Session) -> None:
    asset = _create_asset(db_session)
    repository = TefasFundTypeHistoryRepository(db_session)
    closed = repository.add(
        _history(
            asset_id=asset.id,
            fund_type_name="Type A",
            closed_at=datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc),
        )
    )
    open_row = repository.add(
        _history(
            asset_id=asset.id,
            fund_type_name="Type B",
            first_observed_at=datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc),
            last_observed_at=datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc),
        )
    )

    result = repository.list_by_asset(asset_id=asset.id)

    assert {row.id for row in result} == {closed.id, open_row.id}


def test_add_does_not_commit(db_session: Session, monkeypatch) -> None:
    asset = _create_asset(db_session)
    repository = TefasFundTypeHistoryRepository(db_session)
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)

    repository.add(_history(asset_id=asset.id))

    assert commit_calls == 0


def test_repository_does_not_contain_transition_business_logic() -> None:
    source = inspect.getsource(TefasFundTypeHistoryRepository)

    assert "fund_type_name ==" not in source
    assert "last_observed_at =" not in source
    assert "closed_at =" not in source


def test_source_fields_round_trip(db_session: Session) -> None:
    asset = _create_asset(db_session)
    repository = TefasFundTypeHistoryRepository(db_session)
    history = repository.add(
        _history(
            asset_id=asset.id,
            source_endpoint="fonProfilDtyGetir",
            source_field_name="fonTuru",
        )
    )

    db_session.expire_all()
    result = repository.get_current_for_asset(asset_id=asset.id)

    assert result is not None
    assert result.id == history.id
    assert result.source_endpoint == "fonProfilDtyGetir"
    assert result.source_field_name == "fonTuru"


def test_source_fields_defaults_are_applied_on_add(db_session: Session) -> None:
    asset = _create_asset(db_session)
    repository = TefasFundTypeHistoryRepository(db_session)

    history = repository.add(_history(asset_id=asset.id))

    assert history.source_endpoint == "fonProfilDtyGetir"
    assert history.source_field_name == "fonTuru"


def test_observation_timestamps_round_trip(db_session: Session) -> None:
    asset = _create_asset(db_session)
    repository = TefasFundTypeHistoryRepository(db_session)
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