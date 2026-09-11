from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.config.database import get_db_session
from src.config.settings import get_settings
from src.integrations.ai_client import AiClient
from src.repositories.ai_analysis_repository import AiAnalysisRepository
from src.repositories.asset_repository import AssetRepository
from src.repositories.asset_price_repository import AssetPriceRepository
from src.repositories.benchmark_price_repository import BenchmarkPriceRepository
from src.repositories.benchmark_repository import BenchmarkRepository
from src.repositories.data_sync_run_repository import DataSyncRunRepository
from src.repositories.exchange_rate_repository import ExchangeRateRepository
from src.repositories.expert_source_repository import ExpertSourceRepository
from src.repositories.sentiment_post_repository import SentimentPostRepository
from src.repositories.user_expert_source_repository import UserExpertSourceRepository
from src.repositories.note_repository import NoteRepository
from src.repositories.portfolio_cash_flow_repository import PortfolioCashFlowRepository
from src.repositories.portfolio_repository import PortfolioRepository
from src.repositories.portfolio_snapshot_repository import PortfolioSnapshotRepository
from src.repositories.report_repository import ReportRepository
from src.repositories.tefas_fund_allocation_data_repository import TefasFundAllocationDataRepository
from src.repositories.tefas_fund_daily_data_repository import TefasFundDailyDataRepository
from src.repositories.tefas_fund_detail_snapshot_repository import TefasFundDetailSnapshotRepository
from src.repositories.tefas_management_fee_history_repository import TefasManagementFeeHistoryRepository
from src.repositories.transaction_repository import TransactionRepository
from src.repositories.user_repository import UserRepository
from src.repositories.watchlist_repository import WatchlistRepository
from src.services.ai_analysis_history_service import AiAnalysisHistoryService
from src.services.ai_analysis_persistence_service import AiAnalysisPersistenceService
from src.services.ai_portfolio_analysis_service import AiPortfolioAnalysisService
from src.services.ai_robustness_service import AiRobustnessService
from src.services.ai_sentiment_service import AiSentimentService
from src.services.asset_service import AssetService
from src.services.benchmark_catalog_service import BenchmarkCatalogService
from src.services.benchmark_comparison_service import BenchmarkComparisonService
from src.services.cost_basis_service import CostBasisService
from src.services.data_sync_run_service import DataSyncRunService
from src.services.fx_conversion_service import FxConversionService
from src.services.expert_source_service import ExpertSourceService
from src.services.sentiment_post_service import SentimentPostService
from src.services.user_expert_source_service import UserExpertSourceService
from src.services.holding_service import HoldingService
from src.services.note_service import NoteService
from src.services.portfolio_cash_flow_service import PortfolioCashFlowService
from src.services.portfolio_cash_replay_service import PortfolioCashReplayService
from src.services.portfolio_performance_service import PortfolioPerformanceService
from src.services.portfolio_service import PortfolioService
from src.services.portfolio_snapshot_service import PortfolioSnapshotService
from src.services.portfolio_valuation_service import PortfolioValuationService
from src.services.realized_pl_service import RealizedPlService
from src.services.report_qa_service import ReportQaService
from src.services.report_download_service import ReportDownloadService
from src.services.report_read_service import ReportReadService
from src.services.report_upload_service import ReportUploadService
from src.services.tefas_fund_allocation_read_service import TefasFundAllocationReadService
from src.services.tefas_fund_daily_read_service import TefasFundDailyReadService
from src.services.tefas_fund_metrics_service import TefasFundMetricsService
from src.services.tefas_fund_metadata_read_service import TefasFundMetadataReadService
from src.services.tefas_management_fee_read_service import TefasManagementFeeReadService
from src.services.tefas_valuation_price_service import TefasValuationPriceService
from src.services.valuation_price_service import ValuationPriceService
from src.services.token_service import TokenService
from src.services.transaction_service import TransactionService
from src.services.unrealized_pl_service import UnrealizedPlService
from src.services.user_service import UserService
from src.services.watchlist_service import WatchlistService
from src.integrations.local_report_storage import LocalReportStorage
from src.integrations.pdf_text_extractor import PdfTextExtractor


bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    yield from get_db_session()


def get_user_repository(db: Annotated[Session, Depends(get_db)]) -> UserRepository:
    return UserRepository(db)


def get_portfolio_repository(db: Annotated[Session, Depends(get_db)]) -> PortfolioRepository:
    return PortfolioRepository(db)


def get_portfolio_snapshot_repository(
    db: Annotated[Session, Depends(get_db)],
) -> PortfolioSnapshotRepository:
    return PortfolioSnapshotRepository(db)


def get_note_repository(db: Annotated[Session, Depends(get_db)]) -> NoteRepository:
    return NoteRepository(db)


def get_ai_analysis_repository(db: Annotated[Session, Depends(get_db)]) -> AiAnalysisRepository:
    return AiAnalysisRepository(db)


def get_report_repository(db: Annotated[Session, Depends(get_db)]) -> ReportRepository:
    return ReportRepository(db)


def get_expert_source_repository(db: Annotated[Session, Depends(get_db)]) -> ExpertSourceRepository:
    return ExpertSourceRepository(db)


def get_user_expert_source_repository(db: Annotated[Session, Depends(get_db)]) -> UserExpertSourceRepository:
    return UserExpertSourceRepository(db)


def get_sentiment_post_repository(db: Annotated[Session, Depends(get_db)]) -> SentimentPostRepository:
    return SentimentPostRepository(db)

def get_asset_repository(db: Annotated[Session, Depends(get_db)]) -> AssetRepository:
    return AssetRepository(db)

def get_asset_price_repository(
    db: Annotated[Session, Depends(get_db)],
) -> AssetPriceRepository:
    return AssetPriceRepository(db)


def get_transaction_repository(db: Annotated[Session, Depends(get_db)]) -> TransactionRepository:
    return TransactionRepository(db)


def get_watchlist_repository(db: Annotated[Session, Depends(get_db)]) -> WatchlistRepository:
    return WatchlistRepository(db)


def get_portfolio_cash_flow_repository(
    db: Annotated[Session, Depends(get_db)],
) -> PortfolioCashFlowRepository:
    return PortfolioCashFlowRepository(db)


def get_exchange_rate_repository(db: Annotated[Session, Depends(get_db)]) -> ExchangeRateRepository:
    return ExchangeRateRepository(db)


def get_data_sync_run_repository(
    db: Annotated[Session, Depends(get_db)],
) -> DataSyncRunRepository:
    return DataSyncRunRepository(db)

def get_benchmark_repository(db: Annotated[Session, Depends(get_db)]) -> BenchmarkRepository:
    return BenchmarkRepository(db)


def get_benchmark_price_repository(
    db: Annotated[Session, Depends(get_db)],
) -> BenchmarkPriceRepository:
    return BenchmarkPriceRepository(db)

def get_tefas_fund_allocation_data_repository(
    db: Annotated[Session, Depends(get_db)],
) -> TefasFundAllocationDataRepository:
    return TefasFundAllocationDataRepository(db)



def get_tefas_fund_detail_snapshot_repository(
    db: Annotated[Session, Depends(get_db)],
) -> TefasFundDetailSnapshotRepository:
    return TefasFundDetailSnapshotRepository(db)


def get_tefas_management_fee_history_repository(
    db: Annotated[Session, Depends(get_db)],
) -> TefasManagementFeeHistoryRepository:
    return TefasManagementFeeHistoryRepository(db)


def get_tefas_fund_daily_data_repository(
    db: Annotated[Session, Depends(get_db)],
) -> TefasFundDailyDataRepository:
    return TefasFundDailyDataRepository(db)


def get_ai_analysis_persistence_service(
    db: Annotated[Session, Depends(get_db)],
    ai_analysis_repository: Annotated[
        AiAnalysisRepository,
        Depends(get_ai_analysis_repository),
    ],
) -> AiAnalysisPersistenceService:
    return AiAnalysisPersistenceService(db=db, repository=ai_analysis_repository)


def get_ai_analysis_history_service(
    ai_analysis_repository: Annotated[
        AiAnalysisRepository,
        Depends(get_ai_analysis_repository),
    ],
    portfolio_repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> AiAnalysisHistoryService:
    return AiAnalysisHistoryService(
        ai_analysis_repository=ai_analysis_repository,
        portfolio_repository=portfolio_repository,
    )


def get_report_storage() -> LocalReportStorage:
    settings = get_settings()
    return LocalReportStorage(
        root=settings.report_storage_dir,
        max_file_size_bytes=settings.report_max_file_size_bytes,
    )


def get_pdf_text_extractor() -> PdfTextExtractor:
    return PdfTextExtractor()


def get_report_upload_service(
    db: Annotated[Session, Depends(get_db)],
    report_repository: Annotated[ReportRepository, Depends(get_report_repository)],
    storage: Annotated[LocalReportStorage, Depends(get_report_storage)],
    pdf_text_extractor: Annotated[PdfTextExtractor, Depends(get_pdf_text_extractor)],
) -> ReportUploadService:
    return ReportUploadService(
        db=db,
        report_repository=report_repository,
        storage=storage,
        pdf_text_extractor=pdf_text_extractor,
    )


def get_report_qa_service(
    report_repository: Annotated[ReportRepository, Depends(get_report_repository)],
    ai_client: Annotated[AiClient, Depends(get_ai_client)],
    persistence_service: Annotated[
        AiAnalysisPersistenceService,
        Depends(get_ai_analysis_persistence_service),
    ],
) -> ReportQaService:
    return ReportQaService(
        report_repository=report_repository,
        ai_client=ai_client,
        persistence_service=persistence_service,
    )


def get_report_read_service(
    report_repository: Annotated[ReportRepository, Depends(get_report_repository)],
) -> ReportReadService:
    return ReportReadService(report_repository=report_repository)


def get_report_download_service(
    report_repository: Annotated[ReportRepository, Depends(get_report_repository)],
    storage: Annotated[LocalReportStorage, Depends(get_report_storage)],
) -> ReportDownloadService:
    return ReportDownloadService(report_repository=report_repository, storage=storage)


def get_ai_client() -> AiClient:
    settings = get_settings()
    return AiClient(
        base_url=settings.ai_service_url,
        timeout_seconds=settings.ai_timeout_seconds,
    )


def get_ai_portfolio_analysis_service(
    portfolio_repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
    transaction_repository: Annotated[
        TransactionRepository,
        Depends(get_transaction_repository),
    ],
    daily_data_repository: Annotated[
        TefasFundDailyDataRepository,
        Depends(get_tefas_fund_daily_data_repository),
    ],
    allocation_repository: Annotated[
        TefasFundAllocationDataRepository,
        Depends(get_tefas_fund_allocation_data_repository),
    ],
    ai_client: Annotated[AiClient, Depends(get_ai_client)],
    persistence_service: Annotated[
        AiAnalysisPersistenceService,
        Depends(get_ai_analysis_persistence_service),
    ],
) -> AiPortfolioAnalysisService:
    return AiPortfolioAnalysisService(
        portfolio_repository=portfolio_repository,
        transaction_repository=transaction_repository,
        daily_data_repository=daily_data_repository,
        allocation_repository=allocation_repository,
        ai_client=ai_client,
        persistence_service=persistence_service,
    )

def get_ai_robustness_service(
    portfolio_repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
    transaction_repository: Annotated[
        TransactionRepository,
        Depends(get_transaction_repository),
    ],
    daily_data_repository: Annotated[
        TefasFundDailyDataRepository,
        Depends(get_tefas_fund_daily_data_repository),
    ],
    allocation_repository: Annotated[
        TefasFundAllocationDataRepository,
        Depends(get_tefas_fund_allocation_data_repository),
    ],
    ai_client: Annotated[AiClient, Depends(get_ai_client)],
    persistence_service: Annotated[
        AiAnalysisPersistenceService,
        Depends(get_ai_analysis_persistence_service),
    ],
) -> AiRobustnessService:
    return AiRobustnessService(
        portfolio_repository=portfolio_repository,
        transaction_repository=transaction_repository,
        daily_data_repository=daily_data_repository,
        allocation_repository=allocation_repository,
        ai_client=ai_client,
        persistence_service=persistence_service,
    )


def get_ai_sentiment_service(
    sentiment_post_repository: Annotated[
        SentimentPostRepository,
        Depends(get_sentiment_post_repository),
    ],
    ai_client: Annotated[AiClient, Depends(get_ai_client)],
    persistence_service: Annotated[
        AiAnalysisPersistenceService,
        Depends(get_ai_analysis_persistence_service),
    ],
) -> AiSentimentService:
    return AiSentimentService(
        sentiment_post_repository=sentiment_post_repository,
        ai_client=ai_client,
        persistence_service=persistence_service,
    )


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


def get_asset_service(
    asset_repository: Annotated[AssetRepository, Depends(get_asset_repository)],
) -> AssetService:
    return AssetService(asset_repository)


def get_note_service(
    db: Annotated[Session, Depends(get_db)],
    note_repository: Annotated[NoteRepository, Depends(get_note_repository)],
    portfolio_repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> NoteService:
    return NoteService(
        db=db,
        note_repository=note_repository,
        portfolio_repository=portfolio_repository,
    )


def get_expert_source_service(expert_source_repository: Annotated[ExpertSourceRepository, Depends(get_expert_source_repository)]) -> ExpertSourceService:
    return ExpertSourceService(expert_source_repository)


def get_user_expert_source_service(db: Annotated[Session, Depends(get_db)], expert_source_repository: Annotated[ExpertSourceRepository, Depends(get_expert_source_repository)], user_expert_source_repository: Annotated[UserExpertSourceRepository, Depends(get_user_expert_source_repository)]) -> UserExpertSourceService:
    return UserExpertSourceService(db=db, expert_source_repository=expert_source_repository, repository=user_expert_source_repository)


def get_sentiment_post_service(sentiment_post_repository: Annotated[SentimentPostRepository, Depends(get_sentiment_post_repository)]) -> SentimentPostService:
    return SentimentPostService(sentiment_post_repository)

def get_watchlist_service(
    db: Annotated[Session, Depends(get_db)],
    asset_repository: Annotated[AssetRepository, Depends(get_asset_repository)],
    watchlist_repository: Annotated[
        WatchlistRepository,
        Depends(get_watchlist_repository),
    ],
) -> WatchlistService:
    return WatchlistService(
        db=db,
        asset_repository=asset_repository,
        watchlist_repository=watchlist_repository,
    )


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


def get_portfolio_cash_flow_service(
    db: Annotated[Session, Depends(get_db)],
    portfolio_repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
    cash_flow_repository: Annotated[
        PortfolioCashFlowRepository,
        Depends(get_portfolio_cash_flow_repository),
    ],
) -> PortfolioCashFlowService:
    return PortfolioCashFlowService(
        db=db,
        portfolio_repository=portfolio_repository,
        cash_flow_repository=cash_flow_repository,
    )


def get_portfolio_cash_replay_service(
    portfolio_repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
    cash_flow_repository: Annotated[
        PortfolioCashFlowRepository,
        Depends(get_portfolio_cash_flow_repository),
    ],
    transaction_repository: Annotated[
        TransactionRepository,
        Depends(get_transaction_repository),
    ],
) -> PortfolioCashReplayService:
    return PortfolioCashReplayService(
        portfolio_repository=portfolio_repository,
        cash_flow_repository=cash_flow_repository,
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


def get_valuation_price_service(
    tefas_valuation_price_service: Annotated[
        TefasValuationPriceService,
        Depends(get_tefas_valuation_price_service),
    ],
    asset_price_repository: Annotated[
        AssetPriceRepository,
        Depends(get_asset_price_repository),
    ],
) -> ValuationPriceService:
    return ValuationPriceService(
        tefas_valuation_price_service=tefas_valuation_price_service,
        asset_price_repository=asset_price_repository,
    )
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
        ValuationPriceService,
        Depends(get_valuation_price_service),
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
        ValuationPriceService,
        Depends(get_valuation_price_service),
    ],
    fx_conversion_service: Annotated[
        FxConversionService,
        Depends(get_fx_conversion_service),
    ],
    portfolio_cash_replay_service: Annotated[
        PortfolioCashReplayService,
        Depends(get_portfolio_cash_replay_service),
    ],
) -> PortfolioValuationService:
    return PortfolioValuationService(
        portfolio_repository=portfolio_repository,
        transaction_repository=transaction_repository,
        tefas_valuation_price_service=tefas_valuation_price_service,
        fx_conversion_service=fx_conversion_service,
        portfolio_cash_replay_service=portfolio_cash_replay_service,
    )


def get_portfolio_snapshot_service(
    db: Annotated[Session, Depends(get_db)],
    portfolio_repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
    portfolio_snapshot_repository: Annotated[
        PortfolioSnapshotRepository,
        Depends(get_portfolio_snapshot_repository),
    ],
    portfolio_valuation_service: Annotated[
        PortfolioValuationService,
        Depends(get_portfolio_valuation_service),
    ],
) -> PortfolioSnapshotService:
    return PortfolioSnapshotService(
        db=db,
        portfolio_repository=portfolio_repository,
        portfolio_snapshot_repository=portfolio_snapshot_repository,
        portfolio_valuation_service=portfolio_valuation_service,
    )



def get_portfolio_performance_service(
    portfolio_repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
    cash_flow_repository: Annotated[
        PortfolioCashFlowRepository,
        Depends(get_portfolio_cash_flow_repository),
    ],
    fx_conversion_service: Annotated[
        FxConversionService,
        Depends(get_fx_conversion_service),
    ],
    portfolio_valuation_service: Annotated[
        PortfolioValuationService,
        Depends(get_portfolio_valuation_service),
    ],
) -> PortfolioPerformanceService:
    return PortfolioPerformanceService(
        portfolio_repository=portfolio_repository,
        cash_flow_repository=cash_flow_repository,
        fx_conversion_service=fx_conversion_service,
        portfolio_valuation_service=portfolio_valuation_service,
    )


def get_data_sync_run_service(
    db: Annotated[Session, Depends(get_db)],
    data_sync_run_repository: Annotated[
        DataSyncRunRepository,
        Depends(get_data_sync_run_repository),
    ],
) -> DataSyncRunService:
    return DataSyncRunService(db=db, repository=data_sync_run_repository)


def get_benchmark_catalog_service(
    benchmark_repository: Annotated[
        BenchmarkRepository,
        Depends(get_benchmark_repository),
    ],
) -> BenchmarkCatalogService:
    return BenchmarkCatalogService(benchmark_repository)


def get_benchmark_comparison_service(
    benchmark_repository: Annotated[
        BenchmarkRepository,
        Depends(get_benchmark_repository),
    ],
    benchmark_price_repository: Annotated[
        BenchmarkPriceRepository,
        Depends(get_benchmark_price_repository),
    ],
    fx_conversion_service: Annotated[
        FxConversionService,
        Depends(get_fx_conversion_service),
    ],
    portfolio_performance_service: Annotated[
        PortfolioPerformanceService,
        Depends(get_portfolio_performance_service),
    ],
) -> BenchmarkComparisonService:
    return BenchmarkComparisonService(
        benchmark_repository=benchmark_repository,
        benchmark_price_repository=benchmark_price_repository,
        fx_conversion_service=fx_conversion_service,
        portfolio_performance_service=portfolio_performance_service,
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




def get_tefas_management_fee_read_service(
    asset_repository: Annotated[AssetRepository, Depends(get_asset_repository)],
    management_fee_history_repository: Annotated[
        TefasManagementFeeHistoryRepository,
        Depends(get_tefas_management_fee_history_repository),
    ],
) -> TefasManagementFeeReadService:
    return TefasManagementFeeReadService(
        asset_repository=asset_repository,
        management_fee_history_repository=management_fee_history_repository,
    )

def get_tefas_fund_metadata_read_service(
    asset_repository: Annotated[AssetRepository, Depends(get_asset_repository)],
    detail_snapshot_repository: Annotated[
        TefasFundDetailSnapshotRepository,
        Depends(get_tefas_fund_detail_snapshot_repository),
    ],
) -> TefasFundMetadataReadService:
    return TefasFundMetadataReadService(
        asset_repository=asset_repository,
        detail_snapshot_repository=detail_snapshot_repository,
    )

def get_tefas_fund_daily_read_service(
    asset_repository: Annotated[AssetRepository, Depends(get_asset_repository)],
    daily_data_repository: Annotated[
        TefasFundDailyDataRepository,
        Depends(get_tefas_fund_daily_data_repository),
    ],
) -> TefasFundDailyReadService:
    return TefasFundDailyReadService(
        asset_repository=asset_repository,
        daily_data_repository=daily_data_repository,
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
