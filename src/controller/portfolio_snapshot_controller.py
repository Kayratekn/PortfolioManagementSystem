from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.config.dependencies import get_current_user, get_portfolio_snapshot_service
from src.model.user import User
from src.response.portfolio_snapshot_response import (
    PortfolioSnapshotListResponse,
    PortfolioSnapshotResponse,
)
from src.services.portfolio_snapshot_service import PortfolioSnapshotService


router = APIRouter(
    prefix="/api/v1/portfolios/{portfolio_id}/snapshots",
    tags=["portfolio-snapshots"],
)


@router.post("", response_model=PortfolioSnapshotResponse, status_code=status.HTTP_201_CREATED)
def generate_portfolio_snapshot(
    portfolio_id: int,
    snapshot_date: date,
    current_user: Annotated[User, Depends(get_current_user)],
    portfolio_snapshot_service: Annotated[
        PortfolioSnapshotService,
        Depends(get_portfolio_snapshot_service),
    ],
) -> PortfolioSnapshotResponse:
    snapshot = portfolio_snapshot_service.generate_snapshot(
        portfolio_id=portfolio_id,
        current_user=current_user,
        snapshot_date=snapshot_date,
    )
    return PortfolioSnapshotResponse.model_validate(snapshot)


@router.get("", response_model=PortfolioSnapshotListResponse)
def list_portfolio_snapshots(
    portfolio_id: int,
    start_date: date,
    end_date: date,
    current_user: Annotated[User, Depends(get_current_user)],
    portfolio_snapshot_service: Annotated[
        PortfolioSnapshotService,
        Depends(get_portfolio_snapshot_service),
    ],
) -> PortfolioSnapshotListResponse:
    snapshots = portfolio_snapshot_service.list_snapshots(
        portfolio_id=portfolio_id,
        current_user=current_user,
        start_date=start_date,
        end_date=end_date,
    )
    return PortfolioSnapshotListResponse(
        portfolio_id=portfolio_id,
        start_date=start_date,
        end_date=end_date,
        items=[PortfolioSnapshotResponse.model_validate(snapshot) for snapshot in snapshots],
    )
