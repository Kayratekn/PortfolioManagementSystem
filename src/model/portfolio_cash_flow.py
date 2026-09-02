from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base, TimestampMixin


class PortfolioCashFlow(TimestampMixin, Base):
    __tablename__ = "portfolio_cash_flows"
    __table_args__ = (
        CheckConstraint(
            "flow_type IN ('DEPOSIT', 'WITHDRAWAL')",
            name="ck_portfolio_cash_flows_flow_type_allowed",
        ),
        CheckConstraint(
            "amount > 0",
            name="ck_portfolio_cash_flows_amount_positive",
        ),
        CheckConstraint(
            "currency IN ('TRY', 'USD', 'EUR', 'GBP')",
            name="ck_portfolio_cash_flows_currency_allowed",
        ),
        Index("ix_portfolio_cash_flows_portfolio_date_id", "portfolio_id", "flow_date", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    flow_type: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    flow_date: Mapped[date] = mapped_column(Date, nullable=False)
