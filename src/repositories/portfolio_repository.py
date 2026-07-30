from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.model.portfolio import Portfolio


class PortfolioRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, portfolio: Portfolio) -> Portfolio:
        self.db.add(portfolio)
        self.db.commit()
        self.db.refresh(portfolio)
        return portfolio

    def list_by_user(self, user_id: int, skip: int, limit: int) -> list[Portfolio]:
        statement = (
            select(Portfolio)
            .where(Portfolio.user_id == user_id, Portfolio.deleted_at.is_(None))
            .order_by(Portfolio.id)
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.scalars(statement))

    def count_by_user(self, user_id: int) -> int:
        statement = select(func.count(Portfolio.id)).where(
            Portfolio.user_id == user_id,
            Portfolio.deleted_at.is_(None),
        )
        return int(self.db.scalar(statement) or 0)

    def get_by_id_for_user(self, portfolio_id: int, user_id: int) -> Portfolio | None:
        statement = select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.user_id == user_id,
            Portfolio.deleted_at.is_(None),
        )
        return self.db.scalar(statement)

    def update(self, portfolio: Portfolio) -> Portfolio:
        self.db.add(portfolio)
        self.db.commit()
        self.db.refresh(portfolio)
        return portfolio

    def soft_delete(self, portfolio: Portfolio) -> None:
        self.db.add(portfolio)
        self.db.commit()
