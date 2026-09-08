from __future__ import annotations

from fastapi import HTTPException, status

from src.model.ai_analysis import AiAnalysis
from src.model.user import User
from src.repositories.ai_analysis_repository import AiAnalysisRepository
from src.repositories.portfolio_repository import PortfolioRepository
from src.response.ai_analysis_history_response import (
    AiAnalysisHistoryItemResponse,
    AiAnalysisHistoryListResponse,
)


class AiAnalysisHistoryService:
    def __init__(
        self,
        *,
        ai_analysis_repository: AiAnalysisRepository,
        portfolio_repository: PortfolioRepository,
    ) -> None:
        self.ai_analysis_repository = ai_analysis_repository
        self.portfolio_repository = portfolio_repository

    def list_current_user_analyses(
        self,
        *,
        current_user: User,
        skip: int,
        limit: int,
    ) -> AiAnalysisHistoryListResponse:
        analyses = self.ai_analysis_repository.list_by_user(
            user_id=current_user.id,
            skip=skip,
            limit=limit,
        )
        total = self.ai_analysis_repository.count_by_user(user_id=current_user.id)
        return AiAnalysisHistoryListResponse(
            total=total,
            skip=skip,
            limit=limit,
            items=[self._to_response(analysis) for analysis in analyses],
        )

    def get_current_user_analysis_detail(
        self,
        *,
        analysis_id: int,
        current_user: User,
    ) -> AiAnalysisHistoryItemResponse:
        analysis = self.ai_analysis_repository.get_by_id_for_user(
            analysis_id=analysis_id,
            user_id=current_user.id,
        )
        if analysis is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="AI analysis not found.",
            )
        return self._to_response(analysis)

    def list_owned_portfolio_analyses(
        self,
        *,
        portfolio_id: int,
        current_user: User,
        skip: int,
        limit: int,
    ) -> AiAnalysisHistoryListResponse:
        portfolio = self.portfolio_repository.get_by_id_for_user(portfolio_id, current_user.id)
        if portfolio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found.",
            )

        analyses = self.ai_analysis_repository.list_by_portfolio_for_user(
            portfolio_id=portfolio_id,
            user_id=current_user.id,
            skip=skip,
            limit=limit,
        )
        total = self.ai_analysis_repository.count_by_portfolio_for_user(
            portfolio_id=portfolio_id,
            user_id=current_user.id,
        )
        return AiAnalysisHistoryListResponse(
            total=total,
            skip=skip,
            limit=limit,
            items=[self._to_response(analysis) for analysis in analyses],
        )

    @staticmethod
    def _to_response(analysis: AiAnalysis) -> AiAnalysisHistoryItemResponse:
        return AiAnalysisHistoryItemResponse(
            analysis_id=analysis.id,
            portfolio_id=analysis.portfolio_id,
            analysis_type=analysis.analysis_type,
            result_payload=analysis.result_payload,
            explanation_text=analysis.explanation_text,
            disclaimer=analysis.disclaimer,
            model_version=analysis.model_version,
            formula_version=analysis.formula_version,
            created_at=analysis.created_at,
        )