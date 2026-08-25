from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.model.transaction import Transaction
from src.model.user import User
from src.repositories.asset_repository import AssetRepository
from src.repositories.portfolio_repository import PortfolioRepository
from src.repositories.transaction_repository import TransactionRepository


class TransactionService:
    def __init__(
        self,
        db: Session,
        portfolio_repository: PortfolioRepository,
        asset_repository: AssetRepository,
        transaction_repository: TransactionRepository,
    ) -> None:
        self.db = db
        self.portfolio_repository = portfolio_repository
        self.asset_repository = asset_repository
        self.transaction_repository = transaction_repository

    def create_transaction(
        self,
        *,
        portfolio_id: int,
        asset_id: int,
        transaction_type: str,
        quantity: Decimal,
        unit_price: Decimal,
        transaction_date: date,
        current_user: User,
    ) -> Transaction:
        if transaction_type == "SELL":
            portfolio = self.portfolio_repository.get_by_id_for_user_for_update(
                portfolio_id,
                current_user.id,
            )
        else:
            portfolio = self.portfolio_repository.get_by_id_for_user(
                portfolio_id,
                current_user.id,
            )
        if portfolio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found.",
            )

        asset = self.asset_repository.get_by_id(asset_id)
        if asset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asset not found.",
            )

        transaction = Transaction(
            portfolio_id=portfolio_id,
            asset_id=asset_id,
            transaction_type=transaction_type,
            quantity=quantity,
            unit_price=unit_price,
            transaction_date=transaction_date,
        )

        if transaction_type == "SELL":
            self._validate_sell_quantity(transaction)

        try:
            created_transaction = self.transaction_repository.add(transaction)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return created_transaction

    def _validate_sell_quantity(self, new_transaction: Transaction) -> None:
        history = self.transaction_repository.list_by_portfolio_and_asset(
            portfolio_id=new_transaction.portfolio_id,
            asset_id=new_transaction.asset_id,
        )
        cumulative_quantity = Decimal("0")
        inserted_new_transaction = False

        for transaction in history:
            if (
                not inserted_new_transaction
                and transaction.transaction_date > new_transaction.transaction_date
            ):
                cumulative_quantity -= new_transaction.quantity
                inserted_new_transaction = True
                if cumulative_quantity < Decimal("0"):
                    self._raise_insufficient_quantity()

            cumulative_quantity = self._apply_quantity_delta(
                cumulative_quantity,
                transaction,
            )
            if cumulative_quantity < Decimal("0"):
                self._raise_insufficient_quantity()

        if not inserted_new_transaction:
            cumulative_quantity -= new_transaction.quantity
            if cumulative_quantity < Decimal("0"):
                self._raise_insufficient_quantity()

    def _apply_quantity_delta(
        self,
        cumulative_quantity: Decimal,
        transaction: Transaction,
    ) -> Decimal:
        if transaction.transaction_type == "BUY":
            return cumulative_quantity + transaction.quantity
        if transaction.transaction_type == "SELL":
            return cumulative_quantity - transaction.quantity
        return cumulative_quantity

    def _raise_insufficient_quantity(self) -> None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Insufficient quantity for SELL.",
        )