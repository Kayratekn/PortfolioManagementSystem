from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.config.database import get_db_session
from src.config.settings import get_settings
from src.repositories.portfolio_repository import PortfolioRepository
from src.repositories.user_repository import UserRepository
from src.services.portfolio_service import PortfolioService
from src.services.token_service import TokenService
from src.services.user_service import UserService


bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    yield from get_db_session()


def get_user_repository(db: Annotated[Session, Depends(get_db)]) -> UserRepository:
    return UserRepository(db)


def get_portfolio_repository(db: Annotated[Session, Depends(get_db)]) -> PortfolioRepository:
    return PortfolioRepository(db)


def get_token_service() -> TokenService:
    settings = get_settings()
    return TokenService(
        secret_key=settings.jwt_secret_key,
        issuer=settings.jwt_issuer,
        access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
    )


def get_user_service(
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserService:
    return UserService(user_repository)


def get_portfolio_service(
    portfolio_repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> PortfolioService:
    return PortfolioService(portfolio_repository)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
):
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials were not provided or are invalid.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    try:
        payload = token_service.decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise unauthorized

    user = user_service.get_user_by_id(user_id)
    if user is None or not user.is_active:
        raise unauthorized

    return user
