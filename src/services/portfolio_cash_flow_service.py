from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.model.portfolio_cash_flow import PortfolioCashFlow
from src.model.user import User
from src.repositories.portfolio_cash_flow_repository import PortfolioCashFlowRepository
from src.repositories.portfolio_repository import PortfolioRepository
from src.response.portfolio_cash_flow_response import (
    PortfolioCashFlowListResponse,
    PortfolioCashFlowResponse,
)


class PortfolioCashFlowService:
    def __init__(
        self,
        db: Session,
        portfolio_repository: PortfolioRepository,
        cash_flow_repository: PortfolioCashFlowRepository,
    ) -> None:
        self.db = db
        self.portfolio_repository = portfolio_repository
        self.cash_flow_repository = cash_flow_repository

    def create_cash_flow(
        self,
        *,
        portfolio_id: int,
        flow_type: str,
        amount: Decimal,
        currency: str,
        flow_date: date,
        current_user: User,
    ) -> PortfolioCashFlow:
        portfolio = self.portfolio_repository.get_by_id_for_user(
            portfolio_id,
            current_user.id,
        )
        if portfolio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found.",
            )

        cash_flow = PortfolioCashFlow(
            portfolio_id=portfolio_id,
            flow_type=flow_type,
            amount=amount,
            currency=currency,
            flow_date=flow_date,
        )

        try:
            created_cash_flow = self.cash_flow_repository.add(cash_flow)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return created_cash_flow

    def list_cash_flows(
        self,
        *,
        portfolio_id: int,
        current_user: User,
        skip: int,
        limit: int,
    ) -> PortfolioCashFlowListResponse:
        portfolio = self.portfolio_repository.get_by_id_for_user(
            portfolio_id,
            current_user.id,
        )
        if portfolio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found.",
            )

        cash_flows = self.cash_flow_repository.list_by_portfolio(
            portfolio_id=portfolio_id,
            skip=skip,
            limit=limit,
        )
        total = self.cash_flow_repository.count_by_portfolio(portfolio_id=portfolio_id)
        return PortfolioCashFlowListResponse(
            items=[
                PortfolioCashFlowResponse.model_validate(cash_flow)
                for cash_flow in cash_flows
            ],
            total=total,
            skip=skip,
            limit=limit,
        )
