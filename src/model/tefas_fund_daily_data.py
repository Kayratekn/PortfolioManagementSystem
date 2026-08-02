from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base, TimestampMixin


class TefasFundDailyData(TimestampMixin, Base):
    __tablename__ = "tefas_fund_daily_data"
    __table_args__ = (
        UniqueConstraint(
            "asset_id",
            "data_date",
            name="uq_tefas_fund_daily_data_asset_date",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    data_date: Mapped[date] = mapped_column(Date, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    shares_outstanding: Mapped[Decimal | None] = mapped_column(Numeric(25, 4), nullable=True)
    investor_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    portfolio_size: Mapped[Decimal | None] = mapped_column(Numeric(25, 4), nullable=True)
    exchange_bulletin_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
