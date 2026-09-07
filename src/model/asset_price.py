from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base, TimestampMixin


class AssetPrice(TimestampMixin, Base):
    __tablename__ = "asset_prices"
    __table_args__ = (
        UniqueConstraint(
            "asset_id",
            "price_date",
            "source",
            name="uq_asset_prices_asset_date_source",
        ),
        CheckConstraint(
            "price > 0",
            name="ck_asset_prices_price_positive",
        ),
        CheckConstraint(
            "length(trim(source)) > 0",
            name="ck_asset_prices_source_nonblank",
        ),
        Index(
            "ix_asset_prices_asset_date_id",
            "asset_id",
            "price_date",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)