from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from src.repositories.tefas_fetch_log_repository import TefasFetchLogRepository


class TefasFetchLogService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = TefasFetchLogRepository(db)

    def start(
        self,
        *,
        fund_kind: str,
        fund_code: str | None,
        start_date: date,
        end_date: date,
        started_at: datetime,
    ) -> int:
        normalized_fund_kind = fund_kind.strip().upper()
        normalized_fund_code = self._normalize_fund_code(fund_code)

        try:
            fetch_log = self.repository.create_running(
                data_source="TEFAS",
                fund_kind=normalized_fund_kind,
                fund_code=normalized_fund_code,
                start_date=start_date,
                end_date=end_date,
                started_at=started_at,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return int(fetch_log.id)

    def mark_success(
        self,
        *,
        fetch_log_id: int,
        fetched_rows: int,
        assets_created: int,
        assets_updated: int,
        daily_rows_created: int,
        daily_rows_updated: int,
        completed_at: datetime,
    ) -> None:
        fetch_log = self.repository.get_by_id(fetch_log_id)
        if fetch_log is None:
            raise LookupError(f"TEFAS fetch log not found: {fetch_log_id}")

        try:
            self.repository.mark_success(
                fetch_log,
                fetched_rows=fetched_rows,
                assets_created=assets_created,
                assets_updated=assets_updated,
                daily_rows_created=daily_rows_created,
                daily_rows_updated=daily_rows_updated,
                completed_at=completed_at,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def mark_failed(
        self,
        *,
        fetch_log_id: int,
        error_message: str,
        completed_at: datetime,
    ) -> None:
        fetch_log = self.repository.get_by_id(fetch_log_id)
        if fetch_log is None:
            raise LookupError(f"TEFAS fetch log not found: {fetch_log_id}")

        try:
            self.repository.mark_failed(
                fetch_log,
                error_message=error_message,
                completed_at=completed_at,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _normalize_fund_code(fund_code: str | None) -> str | None:
        if fund_code is None:
            return None

        normalized_value = fund_code.strip().upper()
        return normalized_value or None
