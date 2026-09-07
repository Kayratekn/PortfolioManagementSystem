from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from pydantic import ValidationError

from src.integrations.ai_client import (
    AiClient,
    AiServiceRequestError,
    AiServiceResponseError,
    AiServiceUnavailableError,
)
from src.model.asset import Asset
from src.model.user import User
from src.repositories.portfolio_repository import PortfolioRepository
from src.repositories.tefas_fund_allocation_data_repository import TefasFundAllocationDataRepository
from src.repositories.tefas_fund_daily_data_repository import TefasFundDailyDataRepository
from src.repositories.transaction_repository import TransactionRepository
from src.response.ai_portfolio_analysis_response import (
    AiPortfolioAnalysisResponse,
    AiPortfolioAnalysisResult,
)
from src.services.ai_analysis_persistence_service import AiAnalysisPersistenceService
from src.services.tefas_portfolio_allocation_mapping import get_allocation_label, get_mapping_status


AI_PORTFOLIO_ANALYSIS_ENDPOINT = "/api/ai/portfolio-analysis"
HISTORY_LIMIT = 252
MIN_HISTORY_OBSERVATIONS = 60
TEFAS_SOURCE = "TEFAS"
SUPPORTED_ASSET_TYPE = "FUND"
SUPPORTED_TEFAS_FUND_KINDS = {"YAT", "EMK", "BYF", "GYF", "GSYF"}

RISK_PROFILE_ALIASES = {
    "conservative": "muhafazakar",
    "low": "muhafazakar",
    "dusuk": "muhafazakar",
    "düşük": "muhafazakar",
    "defansif": "muhafazakar",
    "muhafazakar": "muhafazakar",
    "moderate": "dengeli",
    "balanced": "dengeli",
    "medium": "dengeli",
    "orta": "dengeli",
    "dengeli": "dengeli",
    "aggressive": "agresif",
    "high": "agresif",
    "yuksek": "agresif",
    "yüksek": "agresif",
    "dinamik": "agresif",
    "agresif": "agresif",
}


class AiPortfolioAnalysisService:
    def __init__(
        self,
        *,
        portfolio_repository: PortfolioRepository,
        transaction_repository: TransactionRepository,
        daily_data_repository: TefasFundDailyDataRepository,
        allocation_repository: TefasFundAllocationDataRepository,
        ai_client: AiClient,
        persistence_service: AiAnalysisPersistenceService,
    ) -> None:
        self.portfolio_repository = portfolio_repository
        self.transaction_repository = transaction_repository
        self.daily_data_repository = daily_data_repository
        self.allocation_repository = allocation_repository
        self.ai_client = ai_client
        self.persistence_service = persistence_service

    def analyze_portfolio(
        self,
        *,
        portfolio_id: int,
        current_user: User,
        as_of_date: date,
    ) -> AiPortfolioAnalysisResponse:
        portfolio = self.portfolio_repository.get_by_id_for_user(portfolio_id, current_user.id)
        if portfolio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found.",
            )

        risk_profile = self._normalize_risk_profile(current_user.risk_profile)
        holdings = self.transaction_repository.list_holdings_by_portfolio_on_or_before(
            portfolio_id=portfolio_id,
            transaction_date=as_of_date,
        )
        if not holdings:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Portfolio has no supported holdings for AI analysis.",
            )

        if any(not self._is_supported_tefas_fund(asset) for asset, _quantity in holdings):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Portfolio contains unsupported assets for AI analysis.",
            )
        self._validate_unique_normalized_fund_codes(holdings)

        ai_payload = self._build_ai_payload(
            user_id=current_user.id,
            risk_profile=risk_profile,
            holdings=holdings,
            as_of_date=as_of_date,
        )
        raw_response = self._call_ai_service(ai_payload)
        ai_result = self._validate_ai_response(raw_response)
        result_payload = self._structured_result_payload(ai_result)
        analysis = self.persistence_service.persist_analysis(
            user_id=current_user.id,
            portfolio_id=portfolio_id,
            analysis_type="portfolio-analysis",
            result_payload=result_payload,
            explanation_text=ai_result.educational_advice,
            disclaimer=ai_result.disclaimer,
            model_version=ai_result.model_version,
            formula_version=ai_result.formula_version,
        )

        return AiPortfolioAnalysisResponse(
            analysis_id=analysis.id,
            portfolio_id=portfolio_id,
            as_of_date=as_of_date,
            **ai_result.model_dump(),
        )

    def _build_ai_payload(
        self,
        *,
        user_id: int,
        risk_profile: str,
        holdings: list[tuple[Asset, Decimal]],
        as_of_date: date,
    ) -> dict[str, Any]:
        assets: dict[str, int | float] = {}
        historical_prices: dict[str, dict[str, int | float]] = {}
        asset_breakdowns: dict[str, dict[str, int | float]] = {}

        for asset, quantity in holdings:
            observations_desc = self.daily_data_repository.list_latest_on_or_before(
                asset_id=asset.id,
                data_date=as_of_date,
                limit=HISTORY_LIMIT,
            )
            if len(observations_desc) < MIN_HISTORY_OBSERVATIONS:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Insufficient TEFAS history for AI analysis.",
                )

            latest_observation = observations_desc[0]
            fund_code = asset.asset_code.strip().upper()
            assets[fund_code] = self._decimal_to_json_number(quantity * latest_observation.price)
            historical_prices[fund_code] = {
                observation.data_date.isoformat(): self._decimal_to_json_number(observation.price)
                for observation in reversed(observations_desc)
            }

            breakdown = self._build_asset_breakdown(asset_id=asset.id, as_of_date=as_of_date)
            if breakdown is not None:
                asset_breakdowns[fund_code] = breakdown

        return {
            "user_id": user_id,
            "risk_profile": risk_profile,
            "target_currency": "TRY",
            "assets": assets,
            "recent_news": [],
            "historical_prices": historical_prices,
            "asset_breakdowns": asset_breakdowns,
        }

    def _build_asset_breakdown(
        self,
        *,
        asset_id: int,
        as_of_date: date,
    ) -> dict[str, int | float] | None:
        rows = self.allocation_repository.list_latest_on_or_before(
            asset_id=asset_id,
            data_date=as_of_date,
        )
        if not rows:
            return None

        breakdown: dict[str, int | float] = {}
        for row in rows:
            if row.allocation_percentage == Decimal("0"):
                continue
            if not Decimal("0") < row.allocation_percentage <= Decimal("100"):
                return None
            try:
                mapping_status = get_mapping_status(row.raw_field_name)
                label = get_allocation_label(row.raw_field_name)
            except ValueError:
                return None
            if mapping_status != "VERIFIED" or label is None:
                return None
            breakdown[label] = self._decimal_to_json_number(
                row.allocation_percentage / Decimal("100")
            )

        return breakdown or None

    def _call_ai_service(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.ai_client.post_json(AI_PORTFOLIO_ANALYSIS_ENDPOINT, payload)
        except AiServiceUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI service temporarily unavailable.",
            ) from exc
        except AiServiceRequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI service rejected the backend request.",
            ) from exc
        except AiServiceResponseError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI service returned an invalid response.",
            ) from exc

    @staticmethod
    def _validate_ai_response(response: dict[str, Any]) -> AiPortfolioAnalysisResult:
        try:
            return AiPortfolioAnalysisResult.model_validate(response)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI service returned an invalid response.",
            ) from exc

    @staticmethod
    def _structured_result_payload(result: AiPortfolioAnalysisResult) -> dict[str, Any]:
        allowed_fields = (
            "optimal_weights",
            "expected_return",
            "expected_volatility",
            "sharpe_ratio",
            "robustness_score",
            "scenario_impacts",
            "correlation_matrix",
            "sentiment_score",
            "sentiment_label",
        )
        serialized_result = result.model_dump(mode="json")
        return {field_name: serialized_result[field_name] for field_name in allowed_fields}

    @staticmethod
    def _normalize_risk_profile(value: str | None) -> str:
        if value is None or not value.strip():
            return "dengeli"
        normalized_value = value.strip().lower()
        canonical_value = RISK_PROFILE_ALIASES.get(normalized_value)
        if canonical_value is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unsupported risk profile.",
            )
        return canonical_value

    @staticmethod
    def _is_supported_tefas_fund(asset: Asset) -> bool:
        return (
            asset.data_source == TEFAS_SOURCE
            and asset.asset_type == SUPPORTED_ASSET_TYPE
            and asset.fund_kind in SUPPORTED_TEFAS_FUND_KINDS
        )

    @staticmethod
    def _validate_unique_normalized_fund_codes(holdings: list[tuple[Asset, Decimal]]) -> None:
        fund_codes: set[str] = set()
        for asset, _quantity in holdings:
            fund_code = asset.asset_code.strip().upper()
            if fund_code in fund_codes:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Portfolio contains ambiguous TEFAS fund codes for AI analysis.",
                )
            fund_codes.add(fund_code)

    @staticmethod
    def _decimal_to_json_number(value: Decimal) -> int | float:
        if value == value.to_integral_value():
            return int(value)
        return float(value)