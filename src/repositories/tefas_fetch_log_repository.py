from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.tefas_fetch_log import TefasFetchLog


class TefasFetchLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_running(
        self,
        *,
        data_source: str,
        fund_kind: str,
        fund_code: str | None,
        start_date: date,
        end_date: date,
        started_at: datetime,
    ) -> TefasFetchLog:
        fetch_log = TefasFetchLog(
            data_source=data_source,
            fund_kind=fund_kind,
            fund_code=fund_code,
            start_date=start_date,
            end_date=end_date,
            status="RUNNING",
            started_at=started_at,
        )
        self.db.add(fetch_log)
        self.db.flush()
        return fetch_log

    def get_by_id(self, fetch_log_id: int) -> TefasFetchLog | None:
        statement = select(TefasFetchLog).where(TefasFetchLog.id == fetch_log_id)
        return self.db.scalar(statement)

    def mark_success(
        self,
        fetch_log: TefasFetchLog,
        *,
        fetched_rows: int,
        assets_created: int,
        assets_updated: int,
        daily_rows_created: int,
        daily_rows_updated: int,
        completed_at: datetime,
    ) -> TefasFetchLog:
        fetch_log.status = "SUCCESS"
        fetch_log.fetched_rows = fetched_rows
        fetch_log.assets_created = assets_created
        fetch_log.assets_updated = assets_updated
        fetch_log.daily_rows_created = daily_rows_created
        fetch_log.daily_rows_updated = daily_rows_updated
        fetch_log.completed_at = completed_at
        fetch_log.error_message = None
        self.db.flush()
        return fetch_log

    def mark_failed(
        self,
        fetch_log: TefasFetchLog,
        *,
        error_message: str,
        completed_at: datetime,
    ) -> TefasFetchLog:
        fetch_log.status = "FAILED"
        fetch_log.error_message = error_message
        fetch_log.completed_at = completed_at
        self.db.flush()
        return fetch_log
