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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_0019 = PROJECT_ROOT / "alembic" / "versions" / "20260907_0019_create_data_sync_runs.py"


def test_data_sync_run_model_fields_constraints_and_index() -> None:
    constraints = DataSyncRun.__table__.constraints
    check_constraints = {
        constraint.name
        for constraint in constraints
        if isinstance(constraint, CheckConstraint)
    }
    indexes = {index.name for index in DataSyncRun.__table__.indexes if isinstance(index, Index)}

    assert DataSyncRun.__table__.c.id.primary_key is True
    assert DataSyncRun.__table__.c.sync_type.nullable is False
    assert DataSyncRun.__table__.c.status.nullable is False
    assert DataSyncRun.__table__.c.error_message.nullable is True
    assert DataSyncRun.__table__.c.started_at.nullable is False
    assert DataSyncRun.__table__.c.completed_at.nullable is True
    assert DataSyncRun.__table__.c.created_at.nullable is False
    assert DataSyncRun.__table__.c.updated_at.nullable is False
    assert DataSyncRun.__table__.c.started_at.type.timezone is True
    assert DataSyncRun.__table__.c.completed_at.type.timezone is True
    assert "ck_data_sync_runs_sync_type_allowed" in check_constraints
    assert "ck_data_sync_runs_status_allowed" in check_constraints
    assert "ix_data_sync_runs_type_started_id" in indexes
    assert "reference_date" not in DataSyncRun.__table__.c
    assert "user_id" not in DataSyncRun.__table__.c


@pytest.mark.parametrize("sync_type", ["", "TEFAS", "BENCHMARK", "OTHER"])
def test_data_sync_run_sync_type_db_constraint(db_session: Session, sync_type: str) -> None:
    db_session.add(DataSyncRun(sync_type=sync_type, status="RUNNING", started_at=STARTED_AT))

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("status", ["", "STARTED", "DONE", "ERROR"])
def test_data_sync_run_status_db_constraint(db_session: Session, status: str) -> None:
    db_session.add(DataSyncRun(sync_type=SYNC_TYPE_TEFAS_DAILY, status=status, started_at=STARTED_AT))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_data_sync_run_migration_uses_expected_revision_table_constraints_and_index() -> None:
    migration_text = MIGRATION_0019.read_text(encoding="utf-8")

    assert 'revision = "20260907_0019"' in migration_text
    assert 'down_revision = "20260907_0018"' in migration_text
    assert '"data_sync_runs"' in migration_text
    assert "ck_data_sync_runs_sync_type_allowed" in migration_text
    assert "ck_data_sync_runs_status_allowed" in migration_text
    assert "ix_data_sync_runs_type_started_id" in migration_text
    assert "reference_date" not in migration_text
    assert "fund_kind" not in migration_text
    assert "benchmark_code" not in migration_text
    assert "JSON" not in migration_text
    assert 'op.drop_table("data_sync_runs")' in migration_text


def test_data_sync_run_table_is_registered_in_metadata() -> None:
    assert "data_sync_runs" in DataSyncRun.metadata.tables
