from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from src.repositories.data_sync_run_repository import DataSyncRunRepository
from src.response.data_sync_run_response import DataSyncRunStatusItemResponse, DataSyncStatusResponse


SYNC_TYPE_TEFAS_DAILY = "TEFAS_DAILY"
SYNC_TYPE_BENCHMARK_DAILY = "BENCHMARK_DAILY"
SUPPORTED_SYNC_TYPES = (SYNC_TYPE_TEFAS_DAILY, SYNC_TYPE_BENCHMARK_DAILY)


class DataSyncRunService:
    def __init__(self, db: Session, repository: DataSyncRunRepository) -> None:
        self.db = db
        self.repository = repository

    def start(self, sync_type: str, started_at: datetime) -> int:
        self._validate_sync_type(sync_type)
        try:
            run = self.repository.create_running(sync_type=sync_type, started_at=started_at)
            self.db.commit()
            return run.id
        except Exception:
            self.db.rollback()
            raise

    def mark_success(self, run_id: int, completed_at: datetime) -> None:
        run = self.repository.get_by_id(run_id)
        if run is None:
            raise LookupError(f"DataSyncRun not found: {run_id}")
        try:
            self.repository.mark_success(run, completed_at=completed_at)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def mark_failed(self, run_id: int, error_message: str, completed_at: datetime) -> None:
        run = self.repository.get_by_id(run_id)
        if run is None:
            raise LookupError(f"DataSyncRun not found: {run_id}")
        try:
            self.repository.mark_failed(
                run,
                error_message=error_message,
                completed_at=completed_at,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def get_status(self) -> DataSyncStatusResponse:
        items = []
        for sync_type in SUPPORTED_SYNC_TYPES:
            run = self.repository.get_latest_by_sync_type(sync_type=sync_type)
            if run is not None:
                items.append(DataSyncRunStatusItemResponse.model_validate(run))
        return DataSyncStatusResponse(items=items, total=len(items))

    def _validate_sync_type(self, sync_type: str) -> None:
        if sync_type not in SUPPORTED_SYNC_TYPES:
            raise ValueError(f"Unsupported data sync type: {sync_type}")
