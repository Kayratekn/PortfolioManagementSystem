from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from src.config.dependencies import get_current_user, get_data_sync_run_service
from src.model.user import User
from src.response.data_sync_run_response import DataSyncStatusResponse
from src.services.data_sync_run_service import DataSyncRunService


router = APIRouter(prefix="/api/v1/data-sync", tags=["data-sync"])


@router.get("/status", response_model=DataSyncStatusResponse)
def get_data_sync_status(
    current_user: Annotated[User, Depends(get_current_user)],
    data_sync_run_service: Annotated[DataSyncRunService, Depends(get_data_sync_run_service)],
) -> DataSyncStatusResponse:
    return data_sync_run_service.get_status()
