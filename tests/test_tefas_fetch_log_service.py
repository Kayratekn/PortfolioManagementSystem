from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.tefas_fetch_log import TefasFetchLog
from src.services.tefas_fetch_log_service import TefasFetchLogService


TEFAS_DATE = date(2026, 4, 24)
STARTED_AT = datetime(2026, 4, 24, 9, 30, tzinfo=timezone.utc)
COMPLETED_AT = datetime(2026, 4, 24, 10, 0, tzinfo=timezone.utc)


class RollbackRecorder:
    def __init__(self) -> None:
        self.called = False

    def __call__(self) -> None:
        self.called = True


def _assert_same_moment(
    actual: datetime | None,
    expected: datetime,
) -> None:
    assert actual is not None

    if actual.tzinfo is None:
        actual = actual.replace(tzinfo=timezone.utc)

    assert actual == expected


def test_start_creates_and_commits_running_log(
    db_session: Session,
) -> None:
    service = TefasFetchLogService(db_session)

    fetch_log_id = service.start(
        fund_kind=" yat ",
        fund_code=" aal ",
        start_date=TEFAS_DATE,
        end_date=TEFAS_DATE,
        started_at=STARTED_AT,
    )

    assert isinstance(fetch_log_id, int)

    db_session.expire_all()
    fetch_log = db_session.scalar(
        select(TefasFetchLog).where(
            TefasFetchLog.id == fetch_log_id,
        )
    )

    assert fetch_log is not None
    assert fetch_log.data_source == "TEFAS"
    assert fetch_log.fund_kind == "YAT"
    assert fetch_log.fund_code == "AAL"
    assert fetch_log.status == "RUNNING"
    assert fetch_log.start_date == TEFAS_DATE
    assert fetch_log.end_date == TEFAS_DATE
    _assert_same_moment(fetch_log.started_at, STARTED_AT)

    assert fetch_log.fetched_rows == 0
    assert fetch_log.assets_created == 0
    assert fetch_log.assets_updated == 0
    assert fetch_log.daily_rows_created == 0
    assert fetch_log.daily_rows_updated == 0

    assert fetch_log.completed_at is None
    assert fetch_log.error_message is None


def test_start_converts_empty_fund_code_to_none(
    db_session: Session,
) -> None:
    service = TefasFetchLogService(db_session)

    fetch_log_id = service.start(
        fund_kind="YAT",
        fund_code="   ",
        start_date=TEFAS_DATE,
        end_date=TEFAS_DATE,
        started_at=STARTED_AT,
    )

    db_session.expire_all()
    fetch_log = db_session.scalar(
        select(TefasFetchLog).where(
            TefasFetchLog.id == fetch_log_id,
        )
    )

    assert fetch_log is not None
    assert fetch_log.fund_code is None


def test_mark_success_commits_all_result_values(
    db_session: Session,
) -> None:
    service = TefasFetchLogService(db_session)

    fetch_log_id = service.start(
        fund_kind="YAT",
        fund_code="AAL",
        start_date=TEFAS_DATE,
        end_date=TEFAS_DATE,
        started_at=STARTED_AT,
    )

    service.mark_success(
        fetch_log_id=fetch_log_id,
        fetched_rows=5,
        assets_created=1,
        assets_updated=2,
        daily_rows_created=3,
        daily_rows_updated=4,
        completed_at=COMPLETED_AT,
    )

    db_session.expire_all()
    fetch_log = db_session.scalar(
        select(TefasFetchLog).where(
            TefasFetchLog.id == fetch_log_id,
        )
    )

    assert fetch_log is not None
    assert fetch_log.status == "SUCCESS"
    assert fetch_log.fetched_rows == 5
    assert fetch_log.assets_created == 1
    assert fetch_log.assets_updated == 2
    assert fetch_log.daily_rows_created == 3
    assert fetch_log.daily_rows_updated == 4
    _assert_same_moment(fetch_log.completed_at, COMPLETED_AT)
    assert fetch_log.error_message is None


def test_mark_failed_commits_original_error_message(
    db_session: Session,
) -> None:
    service = TefasFetchLogService(db_session)

    fetch_log_id = service.start(
        fund_kind="YAT",
        fund_code=None,
        start_date=TEFAS_DATE,
        end_date=TEFAS_DATE,
        started_at=STARTED_AT,
    )

    fetch_log = db_session.scalar(
        select(TefasFetchLog).where(
            TefasFetchLog.id == fetch_log_id,
        )
    )

    assert fetch_log is not None

    fetch_log.fetched_rows = 7
    db_session.commit()

    service.mark_failed(
        fetch_log_id=fetch_log_id,
        error_message="TEFAS Request Timed Out ",
        completed_at=COMPLETED_AT,
    )

    db_session.expire_all()
    fetch_log = db_session.scalar(
        select(TefasFetchLog).where(
            TefasFetchLog.id == fetch_log_id,
        )
    )

    assert fetch_log is not None
    assert fetch_log.status == "FAILED"
    assert fetch_log.fetched_rows == 7
    assert fetch_log.error_message == "TEFAS Request Timed Out "
    _assert_same_moment(fetch_log.completed_at, COMPLETED_AT)


def test_mark_success_raises_lookup_error_for_missing_id(
    db_session: Session,
) -> None:
    service = TefasFetchLogService(db_session)

    with pytest.raises(
        LookupError,
        match=r"^TEFAS fetch log not found: 999999$",
    ):
        service.mark_success(
            fetch_log_id=999999,
            fetched_rows=1,
            assets_created=1,
            assets_updated=0,
            daily_rows_created=1,
            daily_rows_updated=0,
            completed_at=COMPLETED_AT,
        )


def test_mark_failed_raises_lookup_error_for_missing_id(
    db_session: Session,
) -> None:
    service = TefasFetchLogService(db_session)

    with pytest.raises(
        LookupError,
        match=r"^TEFAS fetch log not found: 999999$",
    ):
        service.mark_failed(
            fetch_log_id=999999,
            error_message="boom",
            completed_at=COMPLETED_AT,
        )


def test_start_rolls_back_when_commit_fails(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TefasFetchLogService(db_session)
    rollback_recorder = RollbackRecorder()

    def failing_commit() -> None:
        raise RuntimeError("commit failed")

    monkeypatch.setattr(
        db_session,
        "commit",
        failing_commit,
    )
    monkeypatch.setattr(
        db_session,
        "rollback",
        rollback_recorder,
    )

    with pytest.raises(
        RuntimeError,
        match=r"^commit failed$",
    ):
        service.start(
            fund_kind="YAT",
            fund_code="AAL",
            start_date=TEFAS_DATE,
            end_date=TEFAS_DATE,
            started_at=STARTED_AT,
        )

    assert rollback_recorder.called is True


def test_mark_success_rolls_back_when_commit_fails(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TefasFetchLogService(db_session)

    fetch_log_id = service.start(
        fund_kind="YAT",
        fund_code="AAL",
        start_date=TEFAS_DATE,
        end_date=TEFAS_DATE,
        started_at=STARTED_AT,
    )

    rollback_recorder = RollbackRecorder()

    def failing_commit() -> None:
        raise RuntimeError("commit failed")

    monkeypatch.setattr(
        db_session,
        "commit",
        failing_commit,
    )
    monkeypatch.setattr(
        db_session,
        "rollback",
        rollback_recorder,
    )

    with pytest.raises(
        RuntimeError,
        match=r"^commit failed$",
    ):
        service.mark_success(
            fetch_log_id=fetch_log_id,
            fetched_rows=1,
            assets_created=1,
            assets_updated=0,
            daily_rows_created=1,
            daily_rows_updated=0,
            completed_at=COMPLETED_AT,
        )

    assert rollback_recorder.called is True