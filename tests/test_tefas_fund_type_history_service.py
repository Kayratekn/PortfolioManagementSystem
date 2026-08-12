from __future__ import annotations

from datetime import datetime, timezone
import inspect
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_type_history import TefasFundTypeHistory
from src.repositories.tefas_fund_type_history_repository import TefasFundTypeHistoryRepository
from src.services.tefas_fund_type_history_service import (
    TefasFundTypeHistoryObservationResult,
    TefasFundTypeHistoryService,
    TefasFundTypeHistoryServiceError,
)
from src.services.tefas_service import TefasFundTypeResult, TefasServiceError


TYPE_A = "Para Piyasasi Semsiye Fonu"
TYPE_B = "Hisse Senedi Yogun"
TYPE_C = "Gayrimenkul Yatirim Fonlari"


class FakeTefasService:
    def __init__(self, *results: TefasFundTypeResult | Exception) -> None:
        self.results = list(results)
        self.calls: list[str] = []

    def get_fund_type(self, *, fund_code: str) -> TefasFundTypeResult:
        self.calls.append(fund_code)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FailingAddHistoryRepository(TefasFundTypeHistoryRepository):
    def add(self, history: TefasFundTypeHistory) -> TefasFundTypeHistory:
        raise RuntimeError("history add failed")


class NoCurrentFailingAddHistoryRepository(TefasFundTypeHistoryRepository):
    def get_current_for_asset(self, *, asset_id: int) -> TefasFundTypeHistory | None:
        return None

    def add(self, history: TefasFundTypeHistory) -> TefasFundTypeHistory:
        raise RuntimeError("history add failed")


def _fund_type_result(
    fund_type_name: str,
    *,
    fund_code: str = "AAL",
    source_endpoint: str = "fonProfilDtyGetir",
    raw_field_name: str = "fonTuru",
) -> TefasFundTypeResult:
    return TefasFundTypeResult(
        fund_code=fund_code,
        fund_type_name=fund_type_name,
        raw_field_name=raw_field_name,
        source_endpoint=source_endpoint,
    )


def _observed_at(day: int, hour: int = 9) -> datetime:
    return datetime(2026, 8, day, hour, 0, tzinfo=timezone.utc)


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
    fund_type_name: str = TYPE_A,
    first_observed_at: datetime = _observed_at(1),
    last_observed_at: datetime = _observed_at(1),
    closed_at: datetime | None = None,
    source_endpoint: str = "fonProfilDtyGetir",
    source_field_name: str = "fonTuru",
) -> TefasFundTypeHistory:
    return TefasFundTypeHistory(
        asset_id=asset_id,
        fund_type_name=fund_type_name,
        source_endpoint=source_endpoint,
        source_field_name=source_field_name,
        first_observed_at=first_observed_at,
        last_observed_at=last_observed_at,
        closed_at=closed_at,
    )


def _service(
    db_session: Session,
    tefas_service: FakeTefasService,
    *,
    history_repository: TefasFundTypeHistoryRepository | None = None,
) -> TefasFundTypeHistoryService:
    return TefasFundTypeHistoryService(
        db_session,
        fund_type_history_repository=history_repository,
        tefas_service=tefas_service,  # type: ignore[arg-type]
    )


def _history_rows(db_session: Session, asset_id: int) -> list[TefasFundTypeHistory]:
    return list(
        db_session.scalars(
            select(TefasFundTypeHistory)
            .where(TefasFundTypeHistory.asset_id == asset_id)
            .order_by(
                TefasFundTypeHistory.first_observed_at.asc(),
                TefasFundTypeHistory.id.asc(),
            )
        )
    )


def _current_row(db_session: Session, asset_id: int) -> TefasFundTypeHistory | None:
    return db_session.scalar(
        select(TefasFundTypeHistory).where(
            TefasFundTypeHistory.asset_id == asset_id,
            TefasFundTypeHistory.closed_at.is_(None),
        )
    )


def _count_rows(db_session: Session) -> int:
    return len(list(db_session.scalars(select(TefasFundTypeHistory))))


def test_first_observation_creates_one_open_row(db_session: Session) -> None:
    asset = _create_asset(db_session)
    observed_at = _observed_at(1)
    service = _service(db_session, FakeTefasService(_fund_type_result(TYPE_A)))

    result = service.observe_fund_type(fund_code="AAL", observed_at=observed_at)

    rows = _history_rows(db_session, asset.id)
    assert isinstance(result, TefasFundTypeHistoryObservationResult)
    assert result.action == TefasFundTypeHistoryService.ACTION_CREATED
    assert len(rows) == 1
    assert rows[0].closed_at is None
    assert rows[0].fund_type_name == TYPE_A


def test_first_observation_sets_first_and_last_to_observed_at(db_session: Session) -> None:
    asset = _create_asset(db_session)
    observed_at = _observed_at(1)
    service = _service(db_session, FakeTefasService(_fund_type_result(TYPE_A)))

    service.observe_fund_type(fund_code="AAL", observed_at=observed_at)

    row = _history_rows(db_session, asset.id)[0]
    assert row.first_observed_at.replace(tzinfo=timezone.utc) == observed_at
    assert row.last_observed_at.replace(tzinfo=timezone.utc) == observed_at


def test_unchanged_observation_does_not_create_second_row(db_session: Session) -> None:
    asset = _create_asset(db_session)
    db_session.add(_history(asset_id=asset.id, first_observed_at=_observed_at(1), last_observed_at=_observed_at(1)))
    db_session.commit()
    service = _service(db_session, FakeTefasService(_fund_type_result(TYPE_A)))

    result = service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(8))

    rows = _history_rows(db_session, asset.id)
    assert result.action == TefasFundTypeHistoryService.ACTION_UNCHANGED
    assert len(rows) == 1


def test_unchanged_observation_preserves_first_observed_at(db_session: Session) -> None:
    asset = _create_asset(db_session)
    first_seen = _observed_at(1)
    db_session.add(_history(asset_id=asset.id, first_observed_at=first_seen, last_observed_at=first_seen))
    db_session.commit()
    service = _service(db_session, FakeTefasService(_fund_type_result(TYPE_A)))

    service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(8))

    row = _current_row(db_session, asset.id)
    assert row is not None
    assert row.first_observed_at.replace(tzinfo=timezone.utc) == first_seen


def test_unchanged_observation_updates_last_observed_at(db_session: Session) -> None:
    asset = _create_asset(db_session)
    db_session.add(_history(asset_id=asset.id, first_observed_at=_observed_at(1), last_observed_at=_observed_at(1)))
    db_session.commit()
    service = _service(db_session, FakeTefasService(_fund_type_result(TYPE_A)))

    service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(8))

    row = _current_row(db_session, asset.id)
    assert row is not None
    assert row.last_observed_at.replace(tzinfo=timezone.utc) == _observed_at(8)


def test_changed_observation_closes_old_row(db_session: Session) -> None:
    asset = _create_asset(db_session)
    db_session.add(_history(asset_id=asset.id, first_observed_at=_observed_at(1), last_observed_at=_observed_at(8)))
    db_session.commit()
    service = _service(db_session, FakeTefasService(_fund_type_result(TYPE_B)))

    result = service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(15))

    rows = _history_rows(db_session, asset.id)
    old_row = rows[0]
    assert result.action == TefasFundTypeHistoryService.ACTION_CHANGED
    assert old_row.fund_type_name == TYPE_A
    assert old_row.closed_at is not None
    assert old_row.closed_at.replace(tzinfo=timezone.utc) == _observed_at(15)


def test_changed_observation_preserves_old_last_observed_at(db_session: Session) -> None:
    asset = _create_asset(db_session)
    last_seen = _observed_at(8)
    db_session.add(_history(asset_id=asset.id, first_observed_at=_observed_at(1), last_observed_at=last_seen))
    db_session.commit()
    service = _service(db_session, FakeTefasService(_fund_type_result(TYPE_B)))

    service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(15))

    old_row = _history_rows(db_session, asset.id)[0]
    assert old_row.last_observed_at.replace(tzinfo=timezone.utc) == last_seen


def test_changed_observation_creates_new_open_row(db_session: Session) -> None:
    asset = _create_asset(db_session)
    db_session.add(_history(asset_id=asset.id, first_observed_at=_observed_at(1), last_observed_at=_observed_at(8)))
    db_session.commit()
    service = _service(db_session, FakeTefasService(_fund_type_result(TYPE_B)))

    service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(15))

    rows = _history_rows(db_session, asset.id)
    assert len(rows) == 2
    assert rows[1].fund_type_name == TYPE_B
    assert rows[1].closed_at is None


def test_changed_observation_sets_new_first_and_last_to_observed_at(db_session: Session) -> None:
    asset = _create_asset(db_session)
    db_session.add(_history(asset_id=asset.id, first_observed_at=_observed_at(1), last_observed_at=_observed_at(8)))
    db_session.commit()
    service = _service(db_session, FakeTefasService(_fund_type_result(TYPE_B)))

    service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(15))

    new_row = _history_rows(db_session, asset.id)[1]
    assert new_row.first_observed_at.replace(tzinfo=timezone.utc) == _observed_at(15)
    assert new_row.last_observed_at.replace(tzinfo=timezone.utc) == _observed_at(15)


def test_changed_observation_uses_new_source_fields(db_session: Session) -> None:
    asset = _create_asset(db_session)
    db_session.add(_history(asset_id=asset.id, first_observed_at=_observed_at(1), last_observed_at=_observed_at(8)))
    db_session.commit()
    result = _fund_type_result(
        TYPE_B,
        source_endpoint="fonProfilDtyGetirV2",
        raw_field_name="fonTuruV2",
    )
    service = _service(db_session, FakeTefasService(result))

    service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(15))

    new_row = _history_rows(db_session, asset.id)[1]
    assert new_row.source_endpoint == "fonProfilDtyGetirV2"
    assert new_row.source_field_name == "fonTuruV2"


def test_a_to_b_to_a_creates_three_periods_without_reopening_old_a(db_session: Session) -> None:
    asset = _create_asset(db_session)
    service = _service(
        db_session,
        FakeTefasService(
            _fund_type_result(TYPE_A),
            _fund_type_result(TYPE_B),
            _fund_type_result(TYPE_A),
        ),
    )

    service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(1))
    service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(8))
    service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(15))

    rows = _history_rows(db_session, asset.id)
    assert [row.fund_type_name for row in rows] == [TYPE_A, TYPE_B, TYPE_A]
    assert rows[0].closed_at is not None
    assert rows[1].closed_at is not None
    assert rows[2].closed_at is None
    assert rows[0].id != rows[2].id


def test_source_failure_leaves_existing_open_history_unchanged(db_session: Session, monkeypatch) -> None:
    asset = _create_asset(db_session)
    first_seen = _observed_at(1)
    last_seen = _observed_at(8)
    db_session.add(_history(asset_id=asset.id, first_observed_at=first_seen, last_observed_at=last_seen))
    db_session.commit()
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)
    service = _service(db_session, FakeTefasService(TefasServiceError("source failed")))

    with pytest.raises(TefasServiceError):
        service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(15))

    row = _current_row(db_session, asset.id)
    assert row is not None
    assert row.fund_type_name == TYPE_A
    assert row.first_observed_at.replace(tzinfo=timezone.utc) == first_seen
    assert row.last_observed_at.replace(tzinfo=timezone.utc) == last_seen
    assert row.closed_at is None
    assert commit_calls == 0


def test_asset_missing_does_not_fetch_or_write_history(db_session: Session, monkeypatch) -> None:
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    tefas_service = FakeTefasService(_fund_type_result(TYPE_A))
    monkeypatch.setattr(db_session, "commit", counting_commit)
    service = _service(db_session, tefas_service)

    with pytest.raises(TefasFundTypeHistoryServiceError):
        service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(1))

    assert tefas_service.calls == []
    assert _count_rows(db_session) == 0
    assert commit_calls == 0


def test_changed_transition_flushes_closed_row_before_adding_new_open_row(db_session: Session, monkeypatch) -> None:
    asset = _create_asset(db_session)
    current = _history(asset_id=asset.id, first_observed_at=_observed_at(1), last_observed_at=_observed_at(8))
    db_session.add(current)
    db_session.commit()
    original_flush = db_session.flush
    flush_closed_values: list[datetime | None] = []

    def tracking_flush(*args: Any, **kwargs: Any) -> None:
        flush_closed_values.append(current.closed_at)
        original_flush(*args, **kwargs)

    monkeypatch.setattr(db_session, "flush", tracking_flush)
    service = _service(db_session, FakeTefasService(_fund_type_result(TYPE_B)))

    service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(15))

    assert flush_closed_values[0] is not None
    assert flush_closed_values[0].replace(tzinfo=timezone.utc) == _observed_at(15)
    assert len(flush_closed_values) >= 2


def test_changed_transition_add_failure_rolls_back(db_session: Session, monkeypatch) -> None:
    asset = _create_asset(db_session)
    current = _history(asset_id=asset.id, first_observed_at=_observed_at(1), last_observed_at=_observed_at(8))
    db_session.add(current)
    db_session.commit()
    rollback_calls = 0
    original_rollback = db_session.rollback

    def counting_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    monkeypatch.setattr(db_session, "rollback", counting_rollback)
    service = _service(
        db_session,
        FakeTefasService(_fund_type_result(TYPE_B)),
        history_repository=FailingAddHistoryRepository(db_session),
    )

    with pytest.raises(RuntimeError, match="history add failed"):
        service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(15))

    assert rollback_calls == 1


def test_changed_transition_rollback_leaves_previous_current_state_intact(db_session: Session) -> None:
    asset = _create_asset(db_session)
    current = _history(asset_id=asset.id, first_observed_at=_observed_at(1), last_observed_at=_observed_at(8))
    db_session.add(current)
    db_session.commit()
    service = _service(
        db_session,
        FakeTefasService(_fund_type_result(TYPE_B)),
        history_repository=FailingAddHistoryRepository(db_session),
    )

    with pytest.raises(RuntimeError, match="history add failed"):
        service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(15))

    row = _current_row(db_session, asset.id)
    assert row is not None
    assert row.id == current.id
    assert row.fund_type_name == TYPE_A
    assert row.closed_at is None
    assert len(_history_rows(db_session, asset.id)) == 1


def test_first_observation_db_failure_rolls_back(db_session: Session, monkeypatch) -> None:
    _create_asset(db_session)
    db_session.commit()
    rollback_calls = 0
    original_rollback = db_session.rollback

    def counting_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    monkeypatch.setattr(db_session, "rollback", counting_rollback)
    service = _service(
        db_session,
        FakeTefasService(_fund_type_result(TYPE_A)),
        history_repository=NoCurrentFailingAddHistoryRepository(db_session),
    )

    with pytest.raises(RuntimeError, match="history add failed"):
        service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(1))

    assert rollback_calls == 1
    assert _count_rows(db_session) == 0


def test_unchanged_update_db_failure_rolls_back(db_session: Session, monkeypatch) -> None:
    asset = _create_asset(db_session)
    first_seen = _observed_at(1)
    last_seen = _observed_at(8)
    current = _history(asset_id=asset.id, first_observed_at=first_seen, last_observed_at=last_seen)
    db_session.add(current)
    db_session.commit()
    rollback_calls = 0
    original_rollback = db_session.rollback

    def failing_flush(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("flush failed")

    def counting_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    monkeypatch.setattr(db_session, "flush", failing_flush)
    monkeypatch.setattr(db_session, "rollback", counting_rollback)
    service = _service(db_session, FakeTefasService(_fund_type_result(TYPE_A)))

    with pytest.raises(RuntimeError, match="flush failed"):
        service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(15))

    assert rollback_calls == 1
    row = _current_row(db_session, asset.id)
    assert row is not None
    assert row.last_observed_at.replace(tzinfo=timezone.utc) == last_seen


def test_successful_operation_commits_once_at_service_boundary(db_session: Session, monkeypatch) -> None:
    _create_asset(db_session)
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)
    service = _service(db_session, FakeTefasService(_fund_type_result(TYPE_A)))

    service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(1))

    assert commit_calls == 1


def test_repository_still_does_not_commit() -> None:
    source = inspect.getsource(TefasFundTypeHistoryRepository)

    assert ".commit(" not in source


def test_default_observation_timestamp_is_timezone_aware(db_session: Session) -> None:
    _create_asset(db_session)
    service = _service(db_session, FakeTefasService(_fund_type_result(TYPE_A)))

    result = service.observe_fund_type(fund_code="AAL")

    assert result.observed_at.tzinfo is not None
    assert result.observed_at.utcoffset() is not None
    assert result.observed_at.tzinfo == timezone.utc


def test_naive_observed_at_is_rejected_without_mutation(db_session: Session) -> None:
    _create_asset(db_session)
    service = _service(db_session, FakeTefasService(_fund_type_result(TYPE_A)))

    with pytest.raises(TefasFundTypeHistoryServiceError, match="timezone-aware"):
        service.observe_fund_type(fund_code="AAL", observed_at=datetime(2026, 8, 1, 9, 0))

    assert _count_rows(db_session) == 0


def test_out_of_order_observed_at_is_rejected_without_mutation(db_session: Session, monkeypatch) -> None:
    asset = _create_asset(db_session)
    first_seen = _observed_at(10)
    last_seen = _observed_at(12)
    current = _history(asset_id=asset.id, first_observed_at=first_seen, last_observed_at=last_seen)
    db_session.add(current)
    db_session.commit()
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)
    service = _service(db_session, FakeTefasService(_fund_type_result(TYPE_B)))

    with pytest.raises(TefasFundTypeHistoryServiceError, match="observed_at cannot be earlier"):
        service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(11))

    row = _current_row(db_session, asset.id)
    assert row is not None
    assert row.fund_type_name == TYPE_A
    assert row.first_observed_at.replace(tzinfo=timezone.utc) == first_seen
    assert row.last_observed_at.replace(tzinfo=timezone.utc) == last_seen
    assert row.closed_at is None
    assert commit_calls == 0


def test_fund_code_is_normalized_for_asset_lookup_and_source_call(db_session: Session) -> None:
    _create_asset(db_session, asset_code="AAL")
    tefas_service = FakeTefasService(_fund_type_result(TYPE_A))
    service = _service(db_session, tefas_service)

    result = service.observe_fund_type(fund_code=" aal ", observed_at=_observed_at(1))

    assert result.fund_code == "AAL"
    assert tefas_service.calls == ["AAL"]


def test_no_tefas_network_call_is_made_beyond_injected_service(db_session: Session) -> None:
    _create_asset(db_session)
    tefas_service = FakeTefasService(_fund_type_result(TYPE_A))
    service = _service(db_session, tefas_service)

    service.observe_fund_type(fund_code="AAL", observed_at=_observed_at(1))

    assert tefas_service.calls == ["AAL"]
