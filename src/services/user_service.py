from __future__ import annotations

from fastapi import HTTPException, status

from src.model.user import User
from src.repositories.user_repository import UserRepository
from src.request.user_request import UserCreateRequest, UserLoginRequest
from src.services.password_service import PasswordService


class UserService:
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    def register_user(self, payload: UserCreateRequest) -> User:
        email = payload.email.lower()
        username = payload.username.strip()

        if self.user_repository.get_by_email(email) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists.",
            )

        if self.user_repository.get_by_username(username) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this username already exists.",
            )

        user = User(
            email=email,
            username=username,
            hashed_password=PasswordService.hash_password(payload.password),
            full_name=payload.full_name,
            preferred_currency=payload.preferred_currency.upper(),
            risk_profile=payload.risk_profile,
            is_active=True,
        )
        return self.user_repository.create(user)

    def authenticate_user(self, payload: UserLoginRequest) -> User:
        user = self.user_repository.get_by_email(payload.email.lower())
        if user is None or not PasswordService.verify_password(payload.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user_repository.get_by_id(user_id)
