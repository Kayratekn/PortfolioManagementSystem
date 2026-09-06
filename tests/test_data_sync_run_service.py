from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.model.data_sync_run import DataSyncRun
from src.repositories.data_sync_run_repository import DataSyncRunRepository
from src.services.data_sync_run_service import (
    SYNC_TYPE_BENCHMARK_DAILY,
    SYNC_TYPE_TEFAS_DAILY,
    DataSyncRunService,
)

STARTED_AT = datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc)
COMPLETED_AT = datetime(2026, 9, 7, 8, 5, tzinfo=timezone.utc)


def same_moment(actual: datetime | None, expected: datetime) -> bool:
    if actual is None:
        return False
    if actual.tzinfo is None:
        actual = actual.replace(tzinfo=timezone.utc)
    return actual == expected

class RollbackRecorder:
    def __init__(self) -> None:
        self.called = False

    def __call__(self) -> None:
        self.called = True


def service(db_session: Session) -> DataSyncRunService:
    return DataSyncRunService(db=db_session, repository=DataSyncRunRepository(db_session))


def test_service_start_mark_success_and_mark_failed_commit_values(db_session: Session) -> None:
    sync_service = service(db_session)

    run_id = sync_service.start(SYNC_TYPE_TEFAS_DAILY, STARTED_AT)
    sync_service.mark_failed(run_id, "safe error", COMPLETED_AT)
    sync_service.mark_success(run_id, COMPLETED_AT)

    run = db_session.get(DataSyncRun, run_id)
    assert run is not None
    assert run.sync_type == SYNC_TYPE_TEFAS_DAILY
    assert run.status == "SUCCESS"
    assert same_moment(run.completed_at, COMPLETED_AT)
    assert run.error_message is None


def test_service_mark_failed_stores_supplied_safe_error_message(db_session: Session) -> None:
    sync_service = service(db_session)
    run_id = sync_service.start(SYNC_TYPE_BENCHMARK_DAILY, STARTED_AT)

    sync_service.mark_failed(run_id, "One or more benchmark syncs failed.", COMPLETED_AT)

    run = db_session.get(DataSyncRun, run_id)
    assert run.status == "FAILED"
    assert run.error_message == "One or more benchmark syncs failed."


def test_service_rejects_invalid_sync_type(db_session: Session) -> None:
    with pytest.raises(ValueError, match="Unsupported data sync type"):
        service(db_session).start("OTHER", STARTED_AT)


def test_service_missing_run_id_raises_lookup_error(db_session: Session) -> None:
    sync_service = service(db_session)

    with pytest.raises(LookupError, match="DataSyncRun not found: 999999"):
        sync_service.mark_success(999999, COMPLETED_AT)
    with pytest.raises(LookupError, match="DataSyncRun not found: 999999"):
        sync_service.mark_failed(999999, "safe", COMPLETED_AT)


def test_service_rolls_back_when_start_commit_fails(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    rollback = RollbackRecorder()

    def failing_commit() -> None:
        raise RuntimeError("commit failed")

    monkeypatch.setattr(db_session, "commit", failing_commit)
    monkeypatch.setattr(db_session, "rollback", rollback)

    with pytest.raises(RuntimeError, match="commit failed"):
        service(db_session).start(SYNC_TYPE_TEFAS_DAILY, STARTED_AT)

    assert rollback.called is True


def test_service_rolls_back_when_mark_commit_fails(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    sync_service = service(db_session)
    run_id = sync_service.start(SYNC_TYPE_TEFAS_DAILY, STARTED_AT)
    rollback = RollbackRecorder()

    def failing_commit() -> None:
        raise RuntimeError("commit failed")

    monkeypatch.setattr(db_session, "commit", failing_commit)
    monkeypatch.setattr(db_session, "rollback", rollback)

    with pytest.raises(RuntimeError, match="commit failed"):
        sync_service.mark_success(run_id, COMPLETED_AT)

    assert rollback.called is True


def test_status_service_returns_latest_per_type_in_supported_order(db_session: Session) -> None:
    sync_service = service(db_session)
    older_tefas = sync_service.start(SYNC_TYPE_TEFAS_DAILY, datetime(2026, 9, 7, 6, 0, tzinfo=timezone.utc))
    latest_benchmark = sync_service.start(SYNC_TYPE_BENCHMARK_DAILY, datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc))
    latest_tefas = sync_service.start(SYNC_TYPE_TEFAS_DAILY, datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc))
    sync_service.mark_success(older_tefas, COMPLETED_AT)
    sync_service.mark_failed(latest_benchmark, "safe", COMPLETED_AT)

    result = sync_service.get_status()

    assert result.total == 2
    assert [item.sync_type for item in result.items] == [SYNC_TYPE_TEFAS_DAILY, SYNC_TYPE_BENCHMARK_DAILY]
    assert [item.id for item in result.items] == [latest_tefas, latest_benchmark]


def test_status_service_no_run_and_one_type_only_cases(db_session: Session) -> None:
    sync_service = service(db_session)
    assert sync_service.get_status().items == []
    assert sync_service.get_status().total == 0

    run_id = sync_service.start(SYNC_TYPE_BENCHMARK_DAILY, STARTED_AT)
    result = sync_service.get_status()

    assert result.total == 1
    assert result.items[0].id == run_id
    assert result.items[0].sync_type == SYNC_TYPE_BENCHMARK_DAILY
