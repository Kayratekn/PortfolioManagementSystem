from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base, TimestampMixin


class ExchangeRate(TimestampMixin, Base):
    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint(
            "base_currency",
            "quote_currency",
            "rate_date",
            "source",
            name="uq_exchange_rates_pair_date_source",
        ),
        CheckConstraint(
            "base_currency != quote_currency",
            name="ck_exchange_rates_distinct_currencies",
        ),
        CheckConstraint(
            "forex_buying > 0",
            name="ck_exchange_rates_forex_buying_positive",
        ),
        CheckConstraint(
            "forex_selling > 0",
            name="ck_exchange_rates_forex_selling_positive",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    forex_buying: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    forex_selling: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)