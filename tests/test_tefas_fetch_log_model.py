from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.model.tefas_fetch_log import TefasFetchLog


TEFAS_DATE = date(2026, 4, 24)


def _build_minimal_log(**overrides: object) -> TefasFetchLog:
    values: dict[str, object] = {
        "data_source": "TEFAS",
        "fund_kind": "YAT",
        "fund_code": None,
        "start_date": TEFAS_DATE,
        "end_date": TEFAS_DATE,
    }
    values.update(overrides)
    return TefasFetchLog(**values)



def test_minimal_tefas_fetch_log_can_be_inserted_with_defaults(db_session: Session) -> None:
    fetch_log = _build_minimal_log()

    db_session.add(fetch_log)
    db_session.commit()
    db_session.refresh(fetch_log)

    assert fetch_log.id is not None
    assert fetch_log.status == "RUNNING"
    assert fetch_log.fetched_rows == 0
    assert fetch_log.assets_created == 0
    assert fetch_log.assets_updated == 0
    assert fetch_log.daily_rows_created == 0
    assert fetch_log.daily_rows_updated == 0
    assert fetch_log.error_message is None
    assert fetch_log.completed_at is None
    assert fetch_log.started_at is not None



def test_success_tefas_fetch_log_can_be_inserted_with_nonzero_counters(db_session: Session) -> None:
    completed_at = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)
    fetch_log = _build_minimal_log(
        status="SUCCESS",
        fund_code="AAL",
        fetched_rows=1,
        assets_created=1,
        assets_updated=2,
        daily_rows_created=3,
        daily_rows_updated=4,
        completed_at=completed_at,
    )

    db_session.add(fetch_log)
    db_session.commit()
    db_session.refresh(fetch_log)

    assert fetch_log.status == "SUCCESS"
    assert fetch_log.fund_code == "AAL"
    assert fetch_log.fetched_rows == 1
    assert fetch_log.assets_created == 1
    assert fetch_log.assets_updated == 2
    assert fetch_log.daily_rows_created == 3
    assert fetch_log.daily_rows_updated == 4
    assert fetch_log.completed_at is not None

    stored_completed_at = fetch_log.completed_at
    if stored_completed_at.tzinfo is None:
        stored_completed_at = stored_completed_at.replace(tzinfo=timezone.utc)

    assert stored_completed_at == completed_at
    



def test_unsupported_status_raises_integrity_error(db_session: Session) -> None:
    fetch_log = _build_minimal_log(status="UNKNOWN")

    db_session.add(fetch_log)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()



def test_invalid_date_range_raises_integrity_error(db_session: Session) -> None:
    fetch_log = _build_minimal_log(
        start_date=date(2026, 4, 25),
        end_date=date(2026, 4, 24),
    )

    db_session.add(fetch_log)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize(
    "field_name",
    [
        "fetched_rows",
        "assets_created",
        "assets_updated",
        "daily_rows_created",
        "daily_rows_updated",
    ],
)
def test_negative_counter_raises_integrity_error(db_session: Session, field_name: str) -> None:
    fetch_log = _build_minimal_log(**{field_name: -1})

    db_session.add(fetch_log)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()



def test_duplicate_request_scope_logs_are_allowed(db_session: Session) -> None:
    first_log = _build_minimal_log(fund_code="AAL")
    second_log = _build_minimal_log(fund_code="AAL")

    db_session.add_all([first_log, second_log])
    db_session.commit()

    assert first_log.id is not None
    assert second_log.id is not None
    assert first_log.id != second_log.id



def test_fetch_log_index_exists_in_model_metadata() -> None:
    indexes = {index.name: index for index in TefasFetchLog.__table__.indexes}

    assert "ix_tefas_fetch_logs_source_kind_started_at" in indexes
    index = indexes["ix_tefas_fetch_logs_source_kind_started_at"]
    assert [column.name for column in index.columns] == [
        "data_source",
        "fund_kind",
        "started_at",
    ]
