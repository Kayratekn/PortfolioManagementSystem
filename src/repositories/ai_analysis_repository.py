from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.model.ai_analysis import AiAnalysis


class AiAnalysisRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, analysis: AiAnalysis) -> AiAnalysis:
        self.db.add(analysis)
        self.db.flush()
        return analysis

    def get_by_id(self, analysis_id: int) -> AiAnalysis | None:
        statement = select(AiAnalysis).where(AiAnalysis.id == analysis_id)
        return self.db.scalar(statement)

    def list_by_user(self, *, user_id: int, skip: int = 0, limit: int = 100) -> list[AiAnalysis]:
        statement = (
            select(AiAnalysis)
            .where(AiAnalysis.user_id == user_id)
            .order_by(AiAnalysis.created_at.desc(), AiAnalysis.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.scalars(statement))

    def list_by_portfolio_for_user(
        self,
        *,
        portfolio_id: int,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AiAnalysis]:
        statement = (
            select(AiAnalysis)
            .where(
                AiAnalysis.portfolio_id == portfolio_id,
                AiAnalysis.user_id == user_id,
            )
            .order_by(AiAnalysis.created_at.desc(), AiAnalysis.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.scalars(statement))

    def count_by_user(self, *, user_id: int) -> int:
        statement = select(func.count()).select_from(AiAnalysis).where(AiAnalysis.user_id == user_id)
        return int(self.db.scalar(statement) or 0)

    def count_by_portfolio_for_user(self, *, portfolio_id: int, user_id: int) -> int:
        statement = (
            select(func.count())
            .select_from(AiAnalysis)
            .where(
                AiAnalysis.portfolio_id == portfolio_id,
                AiAnalysis.user_id == user_id,
            )
        )
        return int(self.db.scalar(statement) or 0)