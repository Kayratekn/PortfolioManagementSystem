from __future__ import annotations

from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.model.asset import Asset
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

    def list_holdings_by_portfolio(
        self,
        *,
        portfolio_id: int,
    ) -> list[tuple[Asset, Decimal]]:
        quantity_delta = case(
            (Transaction.transaction_type == "BUY", Transaction.quantity),
            (Transaction.transaction_type == "SELL", -Transaction.quantity),
            else_=Decimal("0"),
        )
        holdings_subquery = (
            select(
                Transaction.asset_id.label("asset_id"),
                func.sum(quantity_delta).label("net_quantity"),
            )
            .where(Transaction.portfolio_id == portfolio_id)
            .group_by(Transaction.asset_id)
            .subquery()
        )
        statement = (
            select(Asset, holdings_subquery.c.net_quantity)
            .join(holdings_subquery, Asset.id == holdings_subquery.c.asset_id)
            .where(holdings_subquery.c.net_quantity > Decimal("0"))
            .order_by(Asset.id.asc())
        )
        return [(asset, quantity) for asset, quantity in self.db.execute(statement).all()]
