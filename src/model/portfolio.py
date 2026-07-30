from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base, TimestampMixin


class Portfolio(TimestampMixin, Base):
    __tablename__ = "portfolios"
    __table_args__ = (
        CheckConstraint(
            "base_currency IN ('TRY', 'USD', 'EUR', 'GBP')",
            name="ck_portfolios_base_currency_allowed",
        ),
        Index("ix_portfolios_user_deleted_id", "user_id", "deleted_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
