from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status

from src.model.transaction import Transaction
from src.model.user import User
from src.repositories.portfolio_cash_flow_repository import PortfolioCashFlowRepository
from src.repositories.portfolio_repository import PortfolioRepository
from src.repositories.transaction_repository import TransactionRepository


PORTFOLIO_CASH_REPLAY_STATUS_COMPLETE = "COMPLETE"
PORTFOLIO_CASH_REPLAY_STATUS_INCOMPLETE = "INCOMPLETE"
PORTFOLIO_CASH_REPLAY_REASON_TRANSACTION_CURRENCY_UNAVAILABLE = (
    "TRANSACTION_CURRENCY_UNAVAILABLE"
)
SUPPORTED_CASH_REPLAY_CURRENCIES = ("EUR", "GBP", "TRY", "USD")


@dataclass(frozen=True)
class PortfolioCashBalance:
    currency: str
    amount: Decimal


@dataclass(frozen=True)
class PortfolioCashReplayResult:
    portfolio_id: int
    as_of_date: date
    status: str
    unavailable_reason: str | None
    balances: list[PortfolioCashBalance]


class PortfolioCashReplayService:
    def __init__(
        self,
        portfolio_repository: PortfolioRepository,
        cash_flow_repository: PortfolioCashFlowRepository,
        transaction_repository: TransactionRepository,
    ) -> None:
        self.portfolio_repository = portfolio_repository
        self.cash_flow_repository = cash_flow_repository
        self.transaction_repository = transaction_repository

    def get_cash_balances(
        self,
        *,
        portfolio_id: int,
        current_user: User,
        as_of_date: date,
    ) -> PortfolioCashReplayResult:
        portfolio = self.portfolio_repository.get_by_id_for_user(
            portfolio_id,
            current_user.id,
        )
        if portfolio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found.",
            )

        balances = {
            currency: Decimal("0")
            for currency in SUPPORTED_CASH_REPLAY_CURRENCIES
        }
        is_complete = True

        cash_flows = self.cash_flow_repository.list_by_portfolio_on_or_before(
            portfolio_id=portfolio_id,
            flow_date=as_of_date,
        )
        for cash_flow in cash_flows:
            if cash_flow.flow_type == "DEPOSIT":
                balances[cash_flow.currency] += cash_flow.amount
            elif cash_flow.flow_type == "WITHDRAWAL":
                balances[cash_flow.currency] -= cash_flow.amount

        transactions = self.transaction_repository.list_by_portfolio_on_or_before(
            portfolio_id=portfolio_id,
            transaction_date=as_of_date,
        )
        for transaction in transactions:
            if transaction.transaction_currency is None:
                is_complete = False
                continue

            transaction_value = transaction.quantity * transaction.unit_price
            self._apply_transaction_value(
                balances=balances,
                transaction=transaction,
                transaction_value=transaction_value,
            )

        return PortfolioCashReplayResult(
            portfolio_id=portfolio_id,
            as_of_date=as_of_date,
            status=(
                PORTFOLIO_CASH_REPLAY_STATUS_COMPLETE
                if is_complete
                else PORTFOLIO_CASH_REPLAY_STATUS_INCOMPLETE
            ),
            unavailable_reason=(
                None
                if is_complete
                else PORTFOLIO_CASH_REPLAY_REASON_TRANSACTION_CURRENCY_UNAVAILABLE
            ),
            balances=[
                PortfolioCashBalance(currency=currency, amount=amount)
                for currency, amount in sorted(balances.items())
                if amount != Decimal("0")
            ],
        )

    def _apply_transaction_value(
        self,
        *,
        balances: dict[str, Decimal],
        transaction: Transaction,
        transaction_value: Decimal,
    ) -> None:
        if transaction.transaction_type == "BUY":
            balances[transaction.transaction_currency] -= transaction_value
        elif transaction.transaction_type == "SELL":
            balances[transaction.transaction_currency] += transaction_value
