from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base, TimestampMixin


class TefasFundTypeHistory(TimestampMixin, Base):
    __tablename__ = "tefas_fund_type_history"
    __table_args__ = (
        Index(
            "ix_tefas_fund_type_history_asset_first_observed_at",
            "asset_id",
            "first_observed_at",
        ),
        Index(
            "ix_tefas_fund_type_history_type_closed_at",
            "fund_type_name",
            "closed_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    fund_type_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_endpoint: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="fonProfilDtyGetir",
        server_default="fonProfilDtyGetir",
    )
    source_field_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="fonTuru",
        server_default="fonTuru",
    )
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)