from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.config.dependencies import get_current_user, get_tefas_fund_allocation_read_service
from src.model.user import User
from src.response.tefas_fund_response import TefasFundAllocationResponse
from src.services.tefas_fund_allocation_read_service import TefasFundAllocationReadService


router = APIRouter(prefix="/api/v1/tefas/funds", tags=["tefas"])


@router.get("/{fund_code}/allocations", response_model=TefasFundAllocationResponse)
def get_fund_allocations(
    fund_code: str,
    current_user: Annotated[User, Depends(get_current_user)],
    allocation_service: Annotated[
        TefasFundAllocationReadService,
        Depends(get_tefas_fund_allocation_read_service),
    ],
    data_date: Annotated[date, Query(alias="date")],
) -> TefasFundAllocationResponse:
    return allocation_service.get_fund_allocation(
        fund_code=fund_code,
        data_date=data_date,
    )
