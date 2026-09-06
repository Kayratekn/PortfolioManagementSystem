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

def test_repository_create_get_latest_ordering_and_mark_methods(db_session: Session) -> None:
    repository = DataSyncRunRepository(db_session)
    first = repository.create_running(
        sync_type=SYNC_TYPE_TEFAS_DAILY,
        started_at=datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc),
    )
    second = repository.create_running(
        sync_type=SYNC_TYPE_TEFAS_DAILY,
        started_at=datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc),
    )
    other = repository.create_running(
        sync_type=SYNC_TYPE_BENCHMARK_DAILY,
        started_at=datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc),
    )
    db_session.commit()

    assert repository.get_by_id(first.id).id == first.id
    assert repository.get_latest_by_sync_type(sync_type=SYNC_TYPE_TEFAS_DAILY).id == second.id
    assert repository.get_latest_by_sync_type(sync_type=SYNC_TYPE_BENCHMARK_DAILY).id == other.id

    repository.mark_success(second, completed_at=COMPLETED_AT)
    repository.mark_failed(first, error_message="safe", completed_at=COMPLETED_AT)
    db_session.commit()

    assert second.status == "SUCCESS"
    assert same_moment(second.completed_at, COMPLETED_AT)
    assert second.error_message is None
    assert first.status == "FAILED"
    assert same_moment(first.completed_at, COMPLETED_AT)
    assert first.error_message == "safe"


def test_latest_ordering_uses_started_at_desc_then_id_desc(db_session: Session) -> None:
    repository = DataSyncRunRepository(db_session)
    older = repository.create_running(sync_type=SYNC_TYPE_TEFAS_DAILY, started_at=STARTED_AT)
    first_same_time = repository.create_running(sync_type=SYNC_TYPE_TEFAS_DAILY, started_at=COMPLETED_AT)
    second_same_time = repository.create_running(sync_type=SYNC_TYPE_TEFAS_DAILY, started_at=COMPLETED_AT)
    db_session.commit()

    assert repository.get_latest_by_sync_type(sync_type=SYNC_TYPE_TEFAS_DAILY).id == second_same_time.id
    assert older.id < first_same_time.id < second_same_time.id


def test_repository_methods_flush_but_do_not_commit(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)
    repository = DataSyncRunRepository(db_session)
    run = repository.create_running(sync_type=SYNC_TYPE_TEFAS_DAILY, started_at=STARTED_AT)
    repository.mark_success(run, completed_at=COMPLETED_AT)
    repository.mark_failed(run, error_message="safe", completed_at=COMPLETED_AT)

    assert run.id is not None
    assert commit_calls == 0
