from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status

from src.model.asset import Asset
from src.model.user import User
from src.repositories.portfolio_repository import PortfolioRepository
from src.repositories.transaction_repository import TransactionRepository
from src.services.moving_weighted_average_replay import (
    MovingWeightedAverageReplayResult,
    replay_moving_weighted_average,
)


REALIZED_PL_ITEM_STATUS_COMPLETE = "COMPLETE"
REALIZED_PL_ITEM_STATUS_UNAVAILABLE = "UNAVAILABLE"
REALIZED_PL_RESULT_STATUS_COMPLETE = "COMPLETE"
REALIZED_PL_RESULT_STATUS_INCOMPLETE = "INCOMPLETE"
REALIZED_PL_UNAVAILABLE_REASON_ASSET_CURRENCY_UNAVAILABLE = (
    "ASSET_CURRENCY_UNAVAILABLE"
)


@dataclass(frozen=True)
class RealizedPlItem:
    asset_id: int
    asset_code: str
    asset_name: str
    asset_currency: str | None
    status: str
    unavailable_reason: str | None
    sold_quantity: Decimal
    realized_proceeds: Decimal | None
    realized_cost_basis: Decimal | None
    native_realized_pl: Decimal | None


@dataclass(frozen=True)
class RealizedPlResult:
    portfolio_id: int
    as_of_date: date
    status: str
    items: tuple[RealizedPlItem, ...]


class RealizedPlService:
    def __init__(
        self,
        portfolio_repository: PortfolioRepository,
        transaction_repository: TransactionRepository,
    ) -> None:
        self.portfolio_repository = portfolio_repository
        self.transaction_repository = transaction_repository

    def get_realized_pl(
        self,
        *,
        portfolio_id: int,
        current_user: User,
        as_of_date: date,
    ) -> RealizedPlResult:
        portfolio = self.portfolio_repository.get_by_id_for_user(
            portfolio_id,
            current_user.id,
        )
        if portfolio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found.",
            )

        assets = self.transaction_repository.list_assets_with_sell_on_or_before(
            portfolio_id=portfolio_id,
            transaction_date=as_of_date,
        )
        items = tuple(
            self._build_item(
                portfolio_id=portfolio_id,
                asset=asset,
                as_of_date=as_of_date,
            )
            for asset in assets
        )
        result_status = REALIZED_PL_RESULT_STATUS_COMPLETE
        if any(item.status == REALIZED_PL_ITEM_STATUS_UNAVAILABLE for item in items):
            result_status = REALIZED_PL_RESULT_STATUS_INCOMPLETE

        return RealizedPlResult(
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
        as_of_date: date,
    ) -> RealizedPlItem:
        transactions = (
            self.transaction_repository.list_by_portfolio_and_asset_on_or_before(
                portfolio_id=portfolio_id,
                asset_id=asset.id,
                transaction_date=as_of_date,
            )
        )
        replay_result = replay_moving_weighted_average(transactions)
        self._validate_replay_result(replay_result)

        if asset.currency is None or asset.currency.strip() == "":
            return RealizedPlItem(
                asset_id=asset.id,
                asset_code=asset.asset_code,
                asset_name=asset.asset_name,
                asset_currency=asset.currency,
                status=REALIZED_PL_ITEM_STATUS_UNAVAILABLE,
                unavailable_reason=(
                    REALIZED_PL_UNAVAILABLE_REASON_ASSET_CURRENCY_UNAVAILABLE
                ),
                sold_quantity=replay_result.sold_quantity,
                realized_proceeds=None,
                realized_cost_basis=None,
                native_realized_pl=None,
            )

        return RealizedPlItem(
            asset_id=asset.id,
            asset_code=asset.asset_code,
            asset_name=asset.asset_name,
            asset_currency=asset.currency,
            status=REALIZED_PL_ITEM_STATUS_COMPLETE,
            unavailable_reason=None,
            sold_quantity=replay_result.sold_quantity,
            realized_proceeds=replay_result.realized_proceeds,
            realized_cost_basis=replay_result.realized_cost_basis,
            native_realized_pl=replay_result.native_realized_pl,
        )

    @staticmethod
    def _validate_replay_result(
        replay_result: MovingWeightedAverageReplayResult,
    ) -> None:
        if replay_result.sold_quantity <= Decimal("0"):
            raise ValueError(
                "Realized P/L replay produced no sold quantity for a SELL asset."
            )
