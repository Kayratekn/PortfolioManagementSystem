from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status

from src.model.asset import Asset
from src.model.transaction import Transaction
from src.model.user import User
from src.repositories.portfolio_repository import PortfolioRepository
from src.repositories.transaction_repository import TransactionRepository


COST_BASIS_ITEM_STATUS_COMPLETE = "COMPLETE"
COST_BASIS_ITEM_STATUS_UNAVAILABLE = "UNAVAILABLE"
COST_BASIS_PORTFOLIO_STATUS_COMPLETE = "COMPLETE"
COST_BASIS_PORTFOLIO_STATUS_INCOMPLETE = "INCOMPLETE"
COST_BASIS_UNAVAILABLE_REASON_ASSET_CURRENCY_UNAVAILABLE = (
    "ASSET_CURRENCY_UNAVAILABLE"
)


@dataclass(frozen=True)
class CostBasisItem:
    asset_id: int
    asset_code: str
    asset_name: str
    asset_currency: str | None
    status: str
    unavailable_reason: str | None
    quantity: Decimal
    total_cost_basis: Decimal | None
    average_cost_per_unit: Decimal | None


@dataclass(frozen=True)
class CostBasisResult:
    portfolio_id: int
    as_of_date: date
    status: str
    items: tuple[CostBasisItem, ...]


@dataclass(frozen=True)
class _ReplayState:
    quantity: Decimal
    total_cost: Decimal
    average_cost: Decimal


class CostBasisService:
    def __init__(
        self,
        portfolio_repository: PortfolioRepository,
        transaction_repository: TransactionRepository,
    ) -> None:
        self.portfolio_repository = portfolio_repository
        self.transaction_repository = transaction_repository

    def get_cost_basis(
        self,
        *,
        portfolio_id: int,
        current_user: User,
        as_of_date: date,
    ) -> CostBasisResult:
        portfolio = self.portfolio_repository.get_by_id_for_user(
            portfolio_id,
            current_user.id,
        )
        if portfolio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found.",
            )

        holdings = self.transaction_repository.list_holdings_by_portfolio_on_or_before(
            portfolio_id=portfolio_id,
            transaction_date=as_of_date,
        )
        items = tuple(
            self._build_item(
                portfolio_id=portfolio_id,
                asset=asset,
                holding_quantity=holding_quantity,
                as_of_date=as_of_date,
            )
            for asset, holding_quantity in holdings
        )
        result_status = COST_BASIS_PORTFOLIO_STATUS_COMPLETE
        if any(
            item.status == COST_BASIS_ITEM_STATUS_UNAVAILABLE
            for item in items
        ):
            result_status = COST_BASIS_PORTFOLIO_STATUS_INCOMPLETE

        return CostBasisResult(
            portfolio_id=portfolio_id,
            as_of_date=as_of_date,
            status=result_status,
            items=items,
        )

    def _build_item(
        self,
        *,
        portfolio_id: int,
        asset: Asset,
        holding_quantity: Decimal,
        as_of_date: date,
    ) -> CostBasisItem:
        if asset.currency is None or asset.currency.strip() == "":
            return CostBasisItem(
                asset_id=asset.id,
                asset_code=asset.asset_code,
                asset_name=asset.asset_name,
                asset_currency=asset.currency,
                status=COST_BASIS_ITEM_STATUS_UNAVAILABLE,
                unavailable_reason=(
                    COST_BASIS_UNAVAILABLE_REASON_ASSET_CURRENCY_UNAVAILABLE
                ),
                quantity=holding_quantity,
                total_cost_basis=None,
                average_cost_per_unit=None,
            )

        transactions = (
            self.transaction_repository.list_by_portfolio_and_asset_on_or_before(
                portfolio_id=portfolio_id,
                asset_id=asset.id,
                transaction_date=as_of_date,
            )
        )
        replay_state = self._replay_transactions(transactions)
        if replay_state.quantity != holding_quantity:
            raise ValueError(
                "Cost basis replay quantity does not match as-of holding quantity."
            )

        return CostBasisItem(
            asset_id=asset.id,
            asset_code=asset.asset_code,
            asset_name=asset.asset_name,
            asset_currency=asset.currency,
            status=COST_BASIS_ITEM_STATUS_COMPLETE,
            unavailable_reason=None,
            quantity=replay_state.quantity,
            total_cost_basis=replay_state.total_cost,
            average_cost_per_unit=replay_state.average_cost,
        )

    def _replay_transactions(
        self,
        transactions: list[Transaction],
    ) -> _ReplayState:
        quantity = Decimal("0")
        total_cost = Decimal("0")
        average_cost = Decimal("0")

        for transaction in transactions:
            if transaction.transaction_type == "BUY":
                buy_cost = transaction.quantity * transaction.unit_price
                total_cost = total_cost + buy_cost
                quantity = quantity + transaction.quantity
                average_cost = total_cost / quantity
            elif transaction.transaction_type == "SELL":
                if transaction.quantity > quantity:
                    raise ValueError(
                        "Cost basis replay encountered a SELL exceeding quantity."
                    )
                cost_removed = transaction.quantity * average_cost
                total_cost = total_cost - cost_removed
                quantity = quantity - transaction.quantity
                if quantity == Decimal("0"):
                    quantity = Decimal("0")
                    total_cost = Decimal("0")
                    average_cost = Decimal("0")
            else:
                raise ValueError("Unsupported transaction type for cost basis replay.")

        return _ReplayState(
            quantity=quantity,
            total_cost=total_cost,
            average_cost=average_cost,
        )