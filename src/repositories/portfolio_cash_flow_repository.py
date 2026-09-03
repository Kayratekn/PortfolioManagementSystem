from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.model.portfolio_cash_flow import PortfolioCashFlow


class PortfolioCashFlowRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, cash_flow: PortfolioCashFlow) -> PortfolioCashFlow:
        self.db.add(cash_flow)
        self.db.flush()
        return cash_flow

    def list_by_portfolio(
        self,
        *,
        portfolio_id: int,
        skip: int,
        limit: int,
    ) -> list[PortfolioCashFlow]:
        statement = (
            select(PortfolioCashFlow)
            .where(PortfolioCashFlow.portfolio_id == portfolio_id)
            .order_by(PortfolioCashFlow.flow_date.asc(), PortfolioCashFlow.id.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.scalars(statement))

    def count_by_portfolio(self, *, portfolio_id: int) -> int:
        statement = select(func.count(PortfolioCashFlow.id)).where(
            PortfolioCashFlow.portfolio_id == portfolio_id,
        )
        return int(self.db.scalar(statement) or 0)

    def list_by_portfolio_on_or_before(
        self,
        *,
        portfolio_id: int,
        flow_date: date,
    ) -> list[PortfolioCashFlow]:
        statement = (
            select(PortfolioCashFlow)
            .where(
                PortfolioCashFlow.portfolio_id == portfolio_id,
                PortfolioCashFlow.flow_date <= flow_date,
            )
            .order_by(PortfolioCashFlow.flow_date.asc(), PortfolioCashFlow.id.asc())
        )
        return list(self.db.scalars(statement))

    def list_by_portfolio_between(
        self,
        *,
        portfolio_id: int,
        start_date: date,
        end_date: date,
    ) -> list[PortfolioCashFlow]:
        statement = (
            select(PortfolioCashFlow)
            .where(
                PortfolioCashFlow.portfolio_id == portfolio_id,
                PortfolioCashFlow.flow_date >= start_date,
                PortfolioCashFlow.flow_date <= end_date,
            )
            .order_by(PortfolioCashFlow.flow_date.asc(), PortfolioCashFlow.id.asc())
        )
        return list(self.db.scalars(statement))
