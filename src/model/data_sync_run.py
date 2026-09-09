from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base, TimestampMixin


class DataSyncRun(TimestampMixin, Base):
    __tablename__ = "data_sync_runs"
    __table_args__ = (
        CheckConstraint(
            "sync_type IN ('TEFAS_DAILY', 'BENCHMARK_DAILY', 'BIST_REFERENCE_PRICES_DAILY')",
            name="ck_data_sync_runs_sync_type_allowed",
        ),
        CheckConstraint(
            "status IN ('RUNNING', 'SUCCESS', 'FAILED')",
            name="ck_data_sync_runs_status_allowed",
        ),
        Index("ix_data_sync_runs_type_started_id", "sync_type", "started_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sync_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
