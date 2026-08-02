from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from src.repositories.tefas_fetch_log_repository import TefasFetchLogRepository


TEFAS_DATE = date(2026, 4, 24)
STARTED_AT = datetime(2026, 4, 24, 9, 30, tzinfo=timezone.utc)
COMPLETED_AT = datetime(2026, 4, 24, 10, 0, tzinfo=timezone.utc)


def _assert_same_moment(actual: datetime | None, expected: datetime) -> None:
    assert actual is not None
    if actual.tzinfo is None:
        actual = actual.replace(tzinfo=timezone.utc)
    assert actual == expected



def test_create_running_assigns_id_and_defaults(db_session: Session) -> None:
    repository = TefasFetchLogRepository(db_session)

    fetch_log = repository.create_running(
        data_source="TEFAS",
        fund_kind="YAT",
        fund_code=None,
        start_date=TEFAS_DATE,
        end_date=TEFAS_DATE,
        started_at=STARTED_AT,
    )

    assert fetch_log.id is not None
    assert fetch_log.data_source == "TEFAS"
    assert fetch_log.fund_kind == "YAT"
    assert fetch_log.fund_code is None
    assert fetch_log.start_date == TEFAS_DATE
    assert fetch_log.end_date == TEFAS_DATE
    assert fetch_log.status == "RUNNING"
    _assert_same_moment(fetch_log.started_at, STARTED_AT)
    assert fetch_log.fetched_rows == 0
    assert fetch_log.assets_created == 0
    assert fetch_log.assets_updated == 0
    assert fetch_log.daily_rows_created == 0
    assert fetch_log.daily_rows_updated == 0
    assert fetch_log.completed_at is None
    assert fetch_log.error_message is None



def test_get_by_id_returns_matching_log(db_session: Session) -> None:
    repository = TefasFetchLogRepository(db_session)
    created_log = repository.create_running(
        data_source="TEFAS",
        fund_kind="YAT",
        fund_code="AAL",
        start_date=TEFAS_DATE,
        end_date=TEFAS_DATE,
        started_at=STARTED_AT,
    )

    result = repository.get_by_id(created_log.id)

    assert result is not None
    assert result.id == created_log.id



def test_get_by_id_returns_none_when_missing(db_session: Session) -> None:
    repository = TefasFetchLogRepository(db_session)

    result = repository.get_by_id(999999)

    assert result is None



def test_mark_success_updates_status_counters_and_completion(db_session: Session) -> None:
    repository = TefasFetchLogRepository(db_session)
    fetch_log = repository.create_running(
        data_source="TEFAS",
        fund_kind="YAT",
        fund_code="AAL",
        start_date=TEFAS_DATE,
        end_date=TEFAS_DATE,
        started_at=STARTED_AT,
    )

    result = repository.mark_success(
        fetch_log,
        fetched_rows=5,
        assets_created=1,
        assets_updated=2,
        daily_rows_created=3,
        daily_rows_updated=4,
        completed_at=COMPLETED_AT,
    )

    assert result is fetch_log
    assert fetch_log.status == "SUCCESS"
    assert fetch_log.fetched_rows == 5
    assert fetch_log.assets_created == 1
    assert fetch_log.assets_updated == 2
    assert fetch_log.daily_rows_created == 3
    assert fetch_log.daily_rows_updated == 4
    _assert_same_moment(fetch_log.completed_at, COMPLETED_AT)
    assert fetch_log.error_message is None



def test_mark_failed_preserves_existing_counters_and_sets_error(db_session: Session) -> None:
    repository = TefasFetchLogRepository(db_session)
    fetch_log = repository.create_running(
        data_source="TEFAS",
        fund_kind="YAT",
        fund_code=None,
        start_date=TEFAS_DATE,
        end_date=TEFAS_DATE,
        started_at=STARTED_AT,
    )
    fetch_log.fetched_rows = 7
    db_session.flush()

    result = repository.mark_failed(
        fetch_log,
        error_message="request timed out",
        completed_at=COMPLETED_AT,
    )

    assert result is fetch_log
    assert fetch_log.status == "FAILED"
    assert fetch_log.fetched_rows == 7
    assert fetch_log.error_message == "request timed out"
    _assert_same_moment(fetch_log.completed_at, COMPLETED_AT)



def test_repository_does_not_commit(db_session: Session) -> None:
    repository = TefasFetchLogRepository(db_session)
    fetch_log = repository.create_running(
        data_source="TEFAS",
        fund_kind="YAT",
        fund_code=None,
        start_date=TEFAS_DATE,
        end_date=TEFAS_DATE,
        started_at=STARTED_AT,
    )

    fetch_log_id = fetch_log.id
    assert fetch_log_id is not None

    db_session.rollback()

    result = repository.get_by_id(fetch_log_id)

    assert result is None
