from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base, TimestampMixin


class BenchmarkPrice(TimestampMixin, Base):
    __tablename__ = "benchmark_prices"
    __table_args__ = (
        UniqueConstraint(
            "benchmark_id",
            "price_date",
            name="uq_benchmark_prices_benchmark_date",
        ),
        CheckConstraint(
            "close_value > 0",
            name="ck_benchmark_prices_close_value_positive",
        ),
        Index(
            "ix_benchmark_prices_benchmark_date",
            "benchmark_id",
            "price_date",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    benchmark_id: Mapped[int] = mapped_column(ForeignKey("benchmarks.id"), nullable=False)
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    close_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
