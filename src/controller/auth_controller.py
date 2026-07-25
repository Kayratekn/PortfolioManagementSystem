from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.config.dependencies import get_current_user, get_token_service, get_user_service
from src.model.user import User
from src.request.user_request import UserCreateRequest, UserLoginRequest
from src.response.user_response import AuthTokenResponse, UserResponse
from src.services.token_service import TokenService
from src.services.user_service import UserService


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreateRequest,
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    user = user_service.register_user(payload)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=AuthTokenResponse)
def login(
    payload: UserLoginRequest,
    user_service: Annotated[UserService, Depends(get_user_service)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> AuthTokenResponse:
    user = user_service.authenticate_user(payload)
    access_token = token_service.create_access_token(str(user.id))
    return AuthTokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.model_validate(current_user)
