from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from src.config.dependencies import get_current_user, get_transaction_service
from src.model.user import User
from src.request.transaction_request import TransactionCreateRequest
from src.response.transaction_response import TransactionListResponse, TransactionResponse
from src.services.transaction_service import TransactionService


router = APIRouter(
    prefix="/api/v1/portfolios/{portfolio_id}/transactions",
    tags=["transactions"],
)


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    portfolio_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    transaction_service: Annotated[TransactionService, Depends(get_transaction_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> TransactionListResponse:
    return transaction_service.list_transactions(
        portfolio_id=portfolio_id,
        current_user=current_user,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    portfolio_id: int,
    payload: TransactionCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    transaction_service: Annotated[TransactionService, Depends(get_transaction_service)],
) -> TransactionResponse:
    created_transaction = transaction_service.create_transaction(
        portfolio_id=portfolio_id,
        asset_id=payload.asset_id,
        transaction_type=payload.transaction_type,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        transaction_currency=payload.transaction_currency,
        transaction_date=payload.transaction_date,
        current_user=current_user,
    )
    return TransactionResponse.model_validate(created_transaction)