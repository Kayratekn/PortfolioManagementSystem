from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.model.ai_analysis import AiAnalysis
from src.repositories.ai_analysis_repository import AiAnalysisRepository


class AiAnalysisPersistenceService:
    def __init__(self, *, db: Session, repository: AiAnalysisRepository) -> None:
        self.db = db
        self.repository = repository

    def persist_analysis(
        self,
        *,
        user_id: int,
        portfolio_id: int | None,
        analysis_type: str,
        result_payload: dict[str, Any],
        model_version: str,
        formula_version: str | None = None,
        explanation_text: str | None = None,
        disclaimer: str | None = None,
    ) -> AiAnalysis:
        try:
            analysis = AiAnalysis(
                user_id=user_id,
                portfolio_id=portfolio_id,
                analysis_type=self._normalize_required_text(
                    analysis_type,
                    field_name="analysis_type",
                ),
                result_payload=self._validate_result_payload(result_payload),
                explanation_text=explanation_text,
                disclaimer=disclaimer,
                model_version=self._normalize_required_text(
                    model_version,
                    field_name="model_version",
                ),
                formula_version=self._normalize_optional_text(
                    formula_version,
                    field_name="formula_version",
                ),
            )
            created = self.repository.add(analysis)
            self.db.commit()
            return created
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _normalize_required_text(value: str, *, field_name: str) -> str:
        normalized_value = value.strip() if isinstance(value, str) else ""
        if not normalized_value:
            raise ValueError(f"{field_name} must not be blank.")
        return normalized_value

    @staticmethod
    def _normalize_optional_text(value: str | None, *, field_name: str) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip() if isinstance(value, str) else ""
        if not normalized_value:
            raise ValueError(f"{field_name} must not be blank when provided.")
        return normalized_value

    @staticmethod
    def _validate_result_payload(value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("result_payload must be a JSON object.")
        return value