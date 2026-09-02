from __future__ import annotations

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
