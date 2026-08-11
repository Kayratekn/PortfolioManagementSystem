from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base, TimestampMixin


class TefasFundAllocationData(TimestampMixin, Base):
    __tablename__ = "tefas_fund_allocation_data"
    __table_args__ = (
        UniqueConstraint(
            "asset_id",
            "data_date",
            "raw_field_name",
            name="uq_tefas_fund_allocation_data_asset_date_field",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    data_date: Mapped[date] = mapped_column(Date, nullable=False)
    raw_field_name: Mapped[str] = mapped_column(String(20), nullable=False)
    allocation_percentage: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
