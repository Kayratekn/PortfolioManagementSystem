from datetime import datetime, timezone
from pathlib import Path

from src.model.data_sync_run import DataSyncRun
from src.repositories.data_sync_run_repository import DataSyncRunRepository
from src.services.data_sync_run_service import (
    SYNC_TYPE_BENCHMARK_DAILY,
    SYNC_TYPE_BIST_REFERENCE_PRICES_DAILY,
    SYNC_TYPE_TEFAS_DAILY,
    DataSyncRunService,
)


MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20260909_0026_add_bist_reference_prices_daily_sync_type.py"
NOW = datetime(2026, 9, 9, 8, 0, tzinfo=timezone.utc)


def test_bist_sync_type_is_accepted_and_status_lists_all_three_types(db_session):
    service = DataSyncRunService(db_session, DataSyncRunRepository(db_session))
    for sync_type in (SYNC_TYPE_TEFAS_DAILY, SYNC_TYPE_BENCHMARK_DAILY, SYNC_TYPE_BIST_REFERENCE_PRICES_DAILY):
        service.start(sync_type, NOW)

    result = service.get_status()
    assert [item.sync_type for item in result.items] == [
        SYNC_TYPE_TEFAS_DAILY,
        SYNC_TYPE_BENCHMARK_DAILY,
        SYNC_TYPE_BIST_REFERENCE_PRICES_DAILY,
    ]
    assert result.total == 3


def test_model_accepts_bist_sync_type(db_session):
    db_session.add(DataSyncRun(sync_type=SYNC_TYPE_BIST_REFERENCE_PRICES_DAILY, status="RUNNING", started_at=NOW))
    db_session.flush()


def test_sync_type_migration_replaces_only_constraint_and_preserves_audit_rows():
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "20260909_0026"' in text
    assert 'down_revision = "20260908_0025"' in text
    assert text.count('ck_data_sync_runs_sync_type_allowed') == 4
    assert "BIST_REFERENCE_PRICES_DAILY" in text
    assert "sync_type IN ('TEFAS_DAILY', 'BENCHMARK_DAILY')" in text
    assert "DELETE" not in text.upper()
    assert "drop_table" not in text