from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.data_sync_run import DataSyncRun


class DataSyncRunRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_running(self, *, sync_type: str, started_at: datetime) -> DataSyncRun:
        run = DataSyncRun(sync_type=sync_type, status="RUNNING", started_at=started_at)
        self.db.add(run)
        self.db.flush()
        return run

    def get_by_id(self, run_id: int) -> DataSyncRun | None:
        return self.db.get(DataSyncRun, run_id)

    def get_latest_by_sync_type(self, *, sync_type: str) -> DataSyncRun | None:
        statement = (
            select(DataSyncRun)
            .where(DataSyncRun.sync_type == sync_type)
            .order_by(DataSyncRun.started_at.desc(), DataSyncRun.id.desc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def mark_success(self, run: DataSyncRun, *, completed_at: datetime) -> DataSyncRun:
        run.status = "SUCCESS"
        run.completed_at = completed_at
        run.error_message = None
        self.db.flush()
        return run

    def mark_failed(
        self,
        run: DataSyncRun,
        *,
        error_message: str,
        completed_at: datetime,
    ) -> DataSyncRun:
        run.status = "FAILED"
        run.completed_at = completed_at
        run.error_message = error_message
        self.db.flush()
        return run
