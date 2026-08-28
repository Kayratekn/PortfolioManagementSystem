from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from src.config.dependencies import get_cost_basis_service, get_current_user
from src.model.user import User
from src.response.cost_basis_response import CostBasisResponse
from src.services.cost_basis_service import CostBasisService


router = APIRouter(
    prefix="/api/v1/portfolios/{portfolio_id}/cost-basis",
    tags=["cost-basis"],
)


@router.get("", response_model=CostBasisResponse)
def get_cost_basis(
    portfolio_id: int,
    as_of_date: date,
    current_user: Annotated[User, Depends(get_current_user)],
    cost_basis_service: Annotated[
        CostBasisService,
        Depends(get_cost_basis_service),
    ],
) -> CostBasisResponse:
    result = cost_basis_service.get_cost_basis(
        portfolio_id=portfolio_id,
        current_user=current_user,
        as_of_date=as_of_date,
    )
    return CostBasisResponse.model_validate(result)