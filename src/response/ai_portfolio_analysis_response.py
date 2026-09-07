from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class AiPortfolioAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    optimal_weights: dict[str, Decimal]
    expected_return: Decimal
    expected_volatility: Decimal
    sharpe_ratio: Decimal
    robustness_score: Decimal
    scenario_impacts: dict[str, Any] | None
    correlation_matrix: dict[str, Any] | None
    sentiment_score: Decimal
    sentiment_label: str
    educational_advice: str
    disclaimer: str
    model_version: str
    formula_version: str

    @field_validator("educational_advice", "disclaimer", "model_version", "formula_version")
    @classmethod
    def validate_nonblank_string(cls, value: str) -> str:
        normalized_value = value.strip() if isinstance(value, str) else ""
        if not normalized_value:
            raise ValueError("String must not be blank.")
        return normalized_value


class AiPortfolioAnalysisResponse(AiPortfolioAnalysisResult):
    analysis_id: int
    portfolio_id: int
    as_of_date: date