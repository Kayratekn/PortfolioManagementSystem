from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status

from src.model.asset import Asset
from src.model.user import User
from src.repositories.portfolio_repository import PortfolioRepository
from src.repositories.transaction_repository import TransactionRepository
from src.response.holding_response import HoldingListResponse, HoldingResponse


class HoldingService:
    def __init__(
        self,
        portfolio_repository: PortfolioRepository,
        transaction_repository: TransactionRepository,
    ) -> None:
        self.portfolio_repository = portfolio_repository
        self.transaction_repository = transaction_repository

    def list_holdings(
        self,
        *,
        portfolio_id: int,
        current_user: User,
    ) -> HoldingListResponse:
        portfolio = self.portfolio_repository.get_by_id_for_user(
            portfolio_id,
            current_user.id,
        )
        if portfolio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found.",
            )

        holdings = self.transaction_repository.list_holdings_by_portfolio(
            portfolio_id=portfolio_id,
        )
        items = [
            self._build_holding_response(asset=asset, quantity=quantity)
            for asset, quantity in holdings
        ]
        return HoldingListResponse(items=items, total=len(items))

    def _build_holding_response(
        self,
        *,
        asset: Asset,
        quantity: Decimal,
    ) -> HoldingResponse:
        return HoldingResponse(
            asset_id=asset.id,
            asset_code=asset.asset_code,
            asset_name=asset.asset_name,
            asset_type=asset.asset_type,
            fund_kind=asset.fund_kind,
            currency=asset.currency,
            data_source=asset.data_source,
            quantity=quantity,
        )