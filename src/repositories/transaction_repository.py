from __future__ import annotations

from datetime import date
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

    def list_by_portfolio(
        self,
        *,
        portfolio_id: int,
        skip: int,
        limit: int,
    ) -> list[Transaction]:
        statement = (
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.transaction_date.asc(), Transaction.id.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.scalars(statement))

    def count_by_portfolio(self, *, portfolio_id: int) -> int:
        statement = select(func.count(Transaction.id)).where(
            Transaction.portfolio_id == portfolio_id,
        )
        return int(self.db.scalar(statement) or 0)

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
        return self._list_by_portfolio_and_asset(
            portfolio_id=portfolio_id,
            asset_id=asset_id,
        )

    def list_by_portfolio_and_asset_on_or_before(
        self,
        *,
        portfolio_id: int,
        asset_id: int,
        transaction_date: date,
    ) -> list[Transaction]:
        return self._list_by_portfolio_and_asset(
            portfolio_id=portfolio_id,
            asset_id=asset_id,
            transaction_date=transaction_date,
        )

    def list_assets_with_sell_on_or_before(
        self,
        *,
        portfolio_id: int,
        transaction_date: date,
    ) -> list[Asset]:
        statement = (
            select(Asset)
            .join(Transaction, Asset.id == Transaction.asset_id)
            .where(
                Transaction.portfolio_id == portfolio_id,
                Transaction.transaction_type == "SELL",
                Transaction.transaction_date <= transaction_date,
            )
            .distinct()
            .order_by(Asset.id.asc())
        )
        return list(self.db.scalars(statement))

    def _list_by_portfolio_and_asset(
        self,
        *,
        portfolio_id: int,
        asset_id: int,
        transaction_date: date | None = None,
    ) -> list[Transaction]:
        filters = [
            Transaction.portfolio_id == portfolio_id,
            Transaction.asset_id == asset_id,
        ]
        if transaction_date is not None:
            filters.append(Transaction.transaction_date <= transaction_date)

        statement = (
            select(Transaction)
            .where(*filters)
            .order_by(Transaction.transaction_date.asc(), Transaction.id.asc())
        )
        return list(self.db.scalars(statement))

    def list_holdings_by_portfolio(
        self,
        *,
        portfolio_id: int,
    ) -> list[tuple[Asset, Decimal]]:
        return self._list_holdings_by_portfolio(
            portfolio_id=portfolio_id,
        )

    def list_holdings_by_portfolio_on_or_before(
        self,
        *,
        portfolio_id: int,
        transaction_date: date,
    ) -> list[tuple[Asset, Decimal]]:
        return self._list_holdings_by_portfolio(
            portfolio_id=portfolio_id,
            transaction_date=transaction_date,
        )

    def _list_holdings_by_portfolio(
        self,
        *,
        portfolio_id: int,
        transaction_date: date | None = None,
    ) -> list[tuple[Asset, Decimal]]:
        quantity_delta = case(
            (Transaction.transaction_type == "BUY", Transaction.quantity),
            (Transaction.transaction_type == "SELL", -Transaction.quantity),
            else_=Decimal("0"),
        )
        filters = [Transaction.portfolio_id == portfolio_id]
        if transaction_date is not None:
            filters.append(Transaction.transaction_date <= transaction_date)

        holdings_subquery = (
            select(
                Transaction.asset_id.label("asset_id"),
                func.sum(quantity_delta).label("net_quantity"),
            )
            .where(*filters)
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
