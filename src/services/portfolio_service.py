from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status

from src.model.portfolio import Portfolio
from src.model.user import User
from src.repositories.portfolio_repository import PortfolioRepository
from src.request.portfolio_request import ALLOWED_CURRENCIES, PortfolioCreateRequest, PortfolioUpdateRequest
from src.response.portfolio_response import PortfolioListResponse, PortfolioResponse


class PortfolioService:
    def __init__(self, portfolio_repository: PortfolioRepository) -> None:
        self.portfolio_repository = portfolio_repository

    def create_portfolio(self, payload: PortfolioCreateRequest, current_user: User) -> Portfolio:
        base_currency = (payload.base_currency or current_user.preferred_currency).upper()
        if base_currency not in ALLOWED_CURRENCIES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Base currency must be one of TRY, USD, EUR or GBP.",
            )

        portfolio = Portfolio(
            user_id=current_user.id,
            name=payload.name,
            base_currency=base_currency,
        )
        return self.portfolio_repository.create(portfolio)

    def list_portfolios(self, current_user: User, skip: int, limit: int) -> PortfolioListResponse:
        items = self.portfolio_repository.list_by_user(current_user.id, skip=skip, limit=limit)
        total = self.portfolio_repository.count_by_user(current_user.id)
        return PortfolioListResponse(
            items=[PortfolioResponse.model_validate(item) for item in items],
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_portfolio(self, portfolio_id: int, current_user: User) -> Portfolio:
        portfolio = self.portfolio_repository.get_by_id_for_user(portfolio_id, current_user.id)
        if portfolio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found.",
            )
        return portfolio

    def update_portfolio(
        self,
        portfolio_id: int,
        payload: PortfolioUpdateRequest,
        current_user: User,
    ) -> Portfolio:
        portfolio = self.get_portfolio(portfolio_id, current_user)

        if payload.name is not None:
            portfolio.name = payload.name
        if payload.base_currency is not None:
            portfolio.base_currency = payload.base_currency

        return self.portfolio_repository.update(portfolio)

    def delete_portfolio(self, portfolio_id: int, current_user: User) -> None:
        portfolio = self.get_portfolio(portfolio_id, current_user)
        portfolio.deleted_at = datetime.now(UTC)
        self.portfolio_repository.soft_delete(portfolio)
