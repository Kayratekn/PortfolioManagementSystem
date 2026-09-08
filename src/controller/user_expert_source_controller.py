from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from src.config.dependencies import get_current_user, get_user_expert_source_service
from src.model.user import User
from src.request.expert_source_request import UserExpertSourceCreateRequest, UserExpertSourceUpdateRequest
from src.response.expert_source_response import UserExpertSourceListResponse, UserExpertSourceResponse
from src.services.user_expert_source_service import UserExpertSourceService

router = APIRouter(prefix="/api/v1/user-expert-sources", tags=["user-expert-sources"])


@router.get("", response_model=UserExpertSourceListResponse)
def list_user_expert_sources(current_user: Annotated[User, Depends(get_current_user)], service: Annotated[UserExpertSourceService, Depends(get_user_expert_source_service)], skip: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=100)) -> UserExpertSourceListResponse:
    return service.list_by_user(current_user=current_user, skip=skip, limit=limit)


@router.post("", response_model=UserExpertSourceResponse, status_code=status.HTTP_201_CREATED)
def create_user_expert_source(payload: UserExpertSourceCreateRequest, current_user: Annotated[User, Depends(get_current_user)], service: Annotated[UserExpertSourceService, Depends(get_user_expert_source_service)]) -> UserExpertSourceResponse:
    return service.create(expert_source_id=payload.expert_source_id, current_user=current_user)


@router.patch("/{user_expert_source_id}", response_model=UserExpertSourceResponse)
def update_user_expert_source(user_expert_source_id: int, payload: UserExpertSourceUpdateRequest, current_user: Annotated[User, Depends(get_current_user)], service: Annotated[UserExpertSourceService, Depends(get_user_expert_source_service)]) -> UserExpertSourceResponse:
    return service.update(user_expert_source_id=user_expert_source_id, is_enabled=payload.is_enabled, current_user=current_user)