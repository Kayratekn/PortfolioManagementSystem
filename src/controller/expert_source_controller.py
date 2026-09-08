from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.config.dependencies import get_current_user, get_expert_source_service
from src.model.user import User
from src.response.expert_source_response import ExpertSourceListResponse
from src.services.expert_source_service import ExpertSourceService

router = APIRouter(prefix="/api/v1/expert-sources", tags=["expert-sources"])


@router.get("", response_model=ExpertSourceListResponse)
def list_expert_sources(current_user: Annotated[User, Depends(get_current_user)], service: Annotated[ExpertSourceService, Depends(get_expert_source_service)], skip: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=100)) -> ExpertSourceListResponse:
    return service.list_active(skip=skip, limit=limit)