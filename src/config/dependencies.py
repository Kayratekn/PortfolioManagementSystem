from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.config.database import get_db_session
from src.config.settings import get_settings
from src.repositories.asset_repository import AssetRepository
from src.repositories.exchange_rate_repository import ExchangeRateRepository
from src.repositories.portfolio_repository import PortfolioRepository
from src.repositories.tefas_fund_allocation_data_repository import TefasFundAllocationDataRepository
from src.repositories.tefas_fund_daily_data_repository import TefasFundDailyDataRepository
from src.repositories.transaction_repository import TransactionRepository
from src.repositories.user_repository import UserRepository
from src.services.cost_basis_service import CostBasisService
from src.services.fx_conversion_service import FxConversionService
from src.services.holding_service import HoldingService
from src.services.portfolio_service import PortfolioService
from src.services.portfolio_valuation_service import PortfolioValuationService
from src.services.realized_pl_service import RealizedPlService
from src.services.tefas_fund_allocation_read_service import TefasFundAllocationReadService
from src.services.tefas_fund_metrics_service import TefasFundMetricsService
from src.services.tefas_valuation_price_service import TefasValuationPriceService
from src.services.token_service import TokenService
from src.services.transaction_service import TransactionService
from src.services.unrealized_pl_service import UnrealizedPlService
from src.services.user_service import UserService


bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    yield from get_db_session()


def get_user_repository(db: Annotated[Session, Depends(get_db)]) -> UserRepository:
    return UserRepository(db)


def get_portfolio_repository(db: Annotated[Session, Depends(get_db)]) -> PortfolioRepository:
    return PortfolioRepository(db)


def get_asset_repository(db: Annotated[Session, Depends(get_db)]) -> AssetRepository:
    return AssetRepository(db)


def get_transaction_repository(db: Annotated[Session, Depends(get_db)]) -> TransactionRepository:
    return TransactionRepository(db)


def get_exchange_rate_repository(db: Annotated[Session, Depends(get_db)]) -> ExchangeRateRepository:
    return ExchangeRateRepository(db)


def get_tefas_fund_allocation_data_repository(
    db: Annotated[Session, Depends(get_db)],
) -> TefasFundAllocationDataRepository:
    return TefasFundAllocationDataRepository(db)


def get_tefas_fund_daily_data_repository(
    db: Annotated[Session, Depends(get_db)],
) -> TefasFundDailyDataRepository:
    return TefasFundDailyDataRepository(db)


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


def get_transaction_service(
    db: Annotated[Session, Depends(get_db)],
    portfolio_repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
    asset_repository: Annotated[AssetRepository, Depends(get_asset_repository)],
    transaction_repository: Annotated[
        TransactionRepository,
        Depends(get_transaction_repository),
    ],
) -> TransactionService:
    return TransactionService(
        db=db,
        portfolio_repository=portfolio_repository,
        asset_repository=asset_repository,
        transaction_repository=transaction_repository,
    )


def get_holding_service(
    portfolio_repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
    transaction_repository: Annotated[
        TransactionRepository,
        Depends(get_transaction_repository),
    ],
) -> HoldingService:
    return HoldingService(
        portfolio_repository=portfolio_repository,
        transaction_repository=transaction_repository,
    )


def get_cost_basis_service(
    portfolio_repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
    transaction_repository: Annotated[
        TransactionRepository,
        Depends(get_transaction_repository),
    ],
) -> CostBasisService:
    return CostBasisService(
        portfolio_repository=portfolio_repository,
        transaction_repository=transaction_repository,
    )


def get_realized_pl_service(
    portfolio_repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
    transaction_repository: Annotated[
        TransactionRepository,
        Depends(get_transaction_repository),
    ],
) -> RealizedPlService:
    return RealizedPlService(
        portfolio_repository=portfolio_repository,
        transaction_repository=transaction_repository,
    )

def get_tefas_valuation_price_service(
    daily_data_repository: Annotated[
        TefasFundDailyDataRepository,
        Depends(get_tefas_fund_daily_data_repository),
    ],
) -> TefasValuationPriceService:
    return TefasValuationPriceService(daily_data_repository)


def get_unrealized_pl_service(
    cost_basis_service: Annotated[
        CostBasisService,
        Depends(get_cost_basis_service),
    ],
    transaction_repository: Annotated[
        TransactionRepository,
        Depends(get_transaction_repository),
    ],
    tefas_valuation_price_service: Annotated[
        TefasValuationPriceService,
        Depends(get_tefas_valuation_price_service),
    ],
) -> UnrealizedPlService:
    return UnrealizedPlService(
        cost_basis_service=cost_basis_service,
        transaction_repository=transaction_repository,
        tefas_valuation_price_service=tefas_valuation_price_service,
    )

def get_fx_conversion_service(
    exchange_rate_repository: Annotated[
        ExchangeRateRepository,
        Depends(get_exchange_rate_repository),
    ],
) -> FxConversionService:
    return FxConversionService(exchange_rate_repository)


def get_portfolio_valuation_service(
    portfolio_repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
    transaction_repository: Annotated[
        TransactionRepository,
        Depends(get_transaction_repository),
    ],
    tefas_valuation_price_service: Annotated[
        TefasValuationPriceService,
        Depends(get_tefas_valuation_price_service),
    ],
    fx_conversion_service: Annotated[
        FxConversionService,
        Depends(get_fx_conversion_service),
    ],
) -> PortfolioValuationService:
    return PortfolioValuationService(
        portfolio_repository=portfolio_repository,
        transaction_repository=transaction_repository,
        tefas_valuation_price_service=tefas_valuation_price_service,
        fx_conversion_service=fx_conversion_service,
    )


def get_tefas_fund_allocation_read_service(
    asset_repository: Annotated[AssetRepository, Depends(get_asset_repository)],
    allocation_repository: Annotated[
        TefasFundAllocationDataRepository,
        Depends(get_tefas_fund_allocation_data_repository),
    ],
) -> TefasFundAllocationReadService:
    return TefasFundAllocationReadService(
        asset_repository=asset_repository,
        allocation_repository=allocation_repository,
    )


def get_tefas_fund_metrics_service(
    asset_repository: Annotated[AssetRepository, Depends(get_asset_repository)],
    daily_data_repository: Annotated[
        TefasFundDailyDataRepository,
        Depends(get_tefas_fund_daily_data_repository),
    ],
) -> TefasFundMetricsService:
    return TefasFundMetricsService(
        asset_repository=asset_repository,
        daily_data_repository=daily_data_repository,
    )


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
