from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from src.config.dependencies import get_current_user, get_portfolio_service
from src.model.user import User
from src.request.portfolio_request import PortfolioCreateRequest, PortfolioUpdateRequest
from src.response.portfolio_response import PortfolioListResponse, PortfolioResponse
from src.services.portfolio_service import PortfolioService


router = APIRouter(prefix="/api/v1/portfolios", tags=["portfolios"])


@router.post("", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
def create_portfolio(
    payload: PortfolioCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service)],
) -> PortfolioResponse:
    portfolio = portfolio_service.create_portfolio(payload, current_user)
    return PortfolioResponse.model_validate(portfolio)


@router.get("", response_model=PortfolioListResponse)
def list_portfolios(
    current_user: Annotated[User, Depends(get_current_user)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> PortfolioListResponse:
    return portfolio_service.list_portfolios(current_user, skip=skip, limit=limit)


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
def get_portfolio(
    portfolio_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service)],
) -> PortfolioResponse:
    portfolio = portfolio_service.get_portfolio(portfolio_id, current_user)
    return PortfolioResponse.model_validate(portfolio)


@router.patch("/{portfolio_id}", response_model=PortfolioResponse)
def update_portfolio(
    portfolio_id: int,
    payload: PortfolioUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service)],
) -> PortfolioResponse:
    portfolio = portfolio_service.update_portfolio(portfolio_id, payload, current_user)
    return PortfolioResponse.model_validate(portfolio)


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_portfolio(
    portfolio_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service)],
) -> Response:
    portfolio_service.delete_portfolio(portfolio_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
