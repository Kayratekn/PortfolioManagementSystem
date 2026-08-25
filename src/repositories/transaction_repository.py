from __future__ import annotations

from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.model.transaction import Transaction


class TransactionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, transaction: Transaction) -> Transaction:
        self.db.add(transaction)
        self.db.flush()
        return transaction

    def get_net_quantity(self, *, portfolio_id: int, asset_id: int) -> Decimal:
        quantity_delta = case(
            (Transaction.transaction_type == "BUY", Transaction.quantity),
            (Transaction.transaction_type == "SELL", -Transaction.quantity),
            else_=Decimal("0"),
        )
        statement = select(func.sum(quantity_delta)).where(
            Transaction.portfolio_id == portfolio_id,
            Transaction.asset_id == asset_id,
        )
        return self.db.scalar(statement) or Decimal("0")

    def list_by_portfolio_and_asset(
        self,
        *,
        portfolio_id: int,
        asset_id: int,
    ) -> list[Transaction]:
        statement = (
            select(Transaction)
            .where(
                Transaction.portfolio_id == portfolio_id,
                Transaction.asset_id == asset_id,
            )
            .order_by(Transaction.transaction_date.asc(), Transaction.id.asc())
        )
        return list(self.db.scalars(statement))