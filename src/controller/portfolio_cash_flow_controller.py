from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from src.config.dependencies import get_current_user, get_portfolio_cash_flow_service
from src.model.user import User
from src.request.portfolio_cash_flow_request import PortfolioCashFlowCreateRequest
from src.response.portfolio_cash_flow_response import (
    PortfolioCashFlowListResponse,
    PortfolioCashFlowResponse,
)
from src.services.portfolio_cash_flow_service import PortfolioCashFlowService


router = APIRouter(
    prefix="/api/v1/portfolios/{portfolio_id}/cash-flows",
    tags=["portfolio-cash-flows"],
)


@router.get("", response_model=PortfolioCashFlowListResponse)
def list_cash_flows(
    portfolio_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    cash_flow_service: Annotated[
        PortfolioCashFlowService,
        Depends(get_portfolio_cash_flow_service),
    ],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> PortfolioCashFlowListResponse:
    return cash_flow_service.list_cash_flows(
        portfolio_id=portfolio_id,
        current_user=current_user,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=PortfolioCashFlowResponse, status_code=status.HTTP_201_CREATED)
def create_cash_flow(
    portfolio_id: int,
    payload: PortfolioCashFlowCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    cash_flow_service: Annotated[
        PortfolioCashFlowService,
        Depends(get_portfolio_cash_flow_service),
    ],
) -> PortfolioCashFlowResponse:
    created_cash_flow = cash_flow_service.create_cash_flow(
        portfolio_id=portfolio_id,
        flow_type=payload.flow_type,
        amount=payload.amount,
        currency=payload.currency,
        flow_date=payload.flow_date,
        current_user=current_user,
    )
    return PortfolioCashFlowResponse.model_validate(created_cash_flow)
