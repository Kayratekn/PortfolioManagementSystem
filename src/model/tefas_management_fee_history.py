from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base, TimestampMixin


class TefasManagementFeeHistory(TimestampMixin, Base):
    __tablename__ = "tefas_management_fee_history"
    __table_args__ = (
        Index(
            "ix_tefas_management_fee_history_asset_first_observed_at",
            "asset_id",
            "first_observed_at",
        ),
        Index(
            "ix_tefas_management_fee_history_fee_closed_at",
            "management_fee_percentage",
            "closed_at",
        ),
        Index(
            "uq_tefas_management_fee_history_one_open_per_asset",
            "asset_id",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
            sqlite_where=text("closed_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    management_fee_percentage: Mapped[Decimal] = mapped_column(
        Numeric(18, 6),
        nullable=False,
    )
    source_endpoint: Mapped[str] = mapped_column(String(100), nullable=False)
    source_field_name: Mapped[str] = mapped_column(String(50), nullable=False)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
