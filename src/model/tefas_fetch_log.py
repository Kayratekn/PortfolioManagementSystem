from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base, TimestampMixin


class TefasFetchLog(TimestampMixin, Base):
    __tablename__ = "tefas_fetch_logs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING', 'SUCCESS', 'FAILED')",
            name="ck_tefas_fetch_logs_status_allowed",
        ),
        CheckConstraint(
            "start_date <= end_date",
            name="ck_tefas_fetch_logs_date_range_valid",
        ),
        CheckConstraint(
            "fetched_rows >= 0",
            name="ck_tefas_fetch_logs_fetched_rows_nonnegative",
        ),
        CheckConstraint(
            "assets_created >= 0",
            name="ck_tefas_fetch_logs_assets_created_nonnegative",
        ),
        CheckConstraint(
            "assets_updated >= 0",
            name="ck_tefas_fetch_logs_assets_updated_nonnegative",
        ),
        CheckConstraint(
            "daily_rows_created >= 0",
            name="ck_tefas_fetch_logs_daily_rows_created_nonnegative",
        ),
        CheckConstraint(
            "daily_rows_updated >= 0",
            name="ck_tefas_fetch_logs_daily_rows_updated_nonnegative",
        ),
        Index(
            "ix_tefas_fetch_logs_source_kind_started_at",
            "data_source",
            "fund_kind",
            "started_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data_source: Mapped[str] = mapped_column(String(20), nullable=False)
    fund_kind: Mapped[str] = mapped_column(String(10), nullable=False)
    fund_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="RUNNING", server_default="RUNNING")
    fetched_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    assets_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    assets_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    daily_rows_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    daily_rows_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
