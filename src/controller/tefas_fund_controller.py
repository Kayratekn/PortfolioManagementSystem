from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.config.dependencies import (
    get_current_user,
    get_tefas_fund_allocation_read_service,
    get_tefas_fund_daily_read_service,
    get_tefas_fund_metrics_service,
)
from src.model.user import User
from src.response.tefas_fund_daily_data_response import (
    TefasFundDailyHistoryResponse,
    TefasFundDailyLatestResponse,
)
from src.response.tefas_fund_metrics_response import TefasFundMetricsResponse
from src.response.tefas_fund_response import TefasFundAllocationResponse
from src.services.tefas_fund_allocation_read_service import TefasFundAllocationReadService
from src.services.tefas_fund_daily_read_service import TefasFundDailyReadService
from src.services.tefas_fund_metrics_service import TefasFundMetricsService


router = APIRouter(prefix="/api/v1/tefas/funds", tags=["tefas"])

@router.get("/{fund_code}/latest", response_model=TefasFundDailyLatestResponse)
def get_fund_latest_daily_data(
    fund_code: str,
    current_user: Annotated[User, Depends(get_current_user)],
    daily_read_service: Annotated[
        TefasFundDailyReadService,
        Depends(get_tefas_fund_daily_read_service),
    ],
) -> TefasFundDailyLatestResponse:
    return daily_read_service.get_latest(fund_code=fund_code)


@router.get("/{fund_code}/history", response_model=TefasFundDailyHistoryResponse)
def get_fund_daily_history(
    fund_code: str,
    current_user: Annotated[User, Depends(get_current_user)],
    daily_read_service: Annotated[
        TefasFundDailyReadService,
        Depends(get_tefas_fund_daily_read_service),
    ],
    start_date: date,
    end_date: date,
) -> TefasFundDailyHistoryResponse:
    return daily_read_service.get_history(
        fund_code=fund_code,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/{fund_code}/metrics", response_model=TefasFundMetricsResponse)
def get_fund_metrics(
    fund_code: str,
    current_user: Annotated[User, Depends(get_current_user)],
    metrics_service: Annotated[
        TefasFundMetricsService,
        Depends(get_tefas_fund_metrics_service),
    ],
    data_date: Annotated[date, Query(alias="date")],
) -> TefasFundMetricsResponse:
    return metrics_service.get_fund_metrics(
        fund_code=fund_code,
        data_date=data_date,
    )


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
