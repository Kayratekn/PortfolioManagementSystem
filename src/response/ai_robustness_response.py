from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AiRobustnessResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scenario_impacts: dict[str, Any]
    robustness_score_100: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    verdict: str
    model_version: str
    formula_version: str

    @field_validator("verdict", "model_version", "formula_version")
    @classmethod
    def validate_nonblank_string(cls, value: str) -> str:
        normalized_value = value.strip() if isinstance(value, str) else ""
        if not normalized_value:
            raise ValueError("String must not be blank.")
        return normalized_value


class AiRobustnessResponse(AiRobustnessResult):
    analysis_id: int
    portfolio_id: int
    as_of_date: date
