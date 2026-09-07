from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base, TimestampMixin


class PortfolioSnapshot(TimestampMixin, Base):
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id",
            "snapshot_date",
            name="uq_portfolio_snapshots_portfolio_date",
        ),
        Index(
            "ix_portfolio_snapshots_portfolio_date_id",
            "portfolio_id",
            "snapshot_date",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_value_try: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    total_value_usd: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    total_value_eur: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    total_value_gbp: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
