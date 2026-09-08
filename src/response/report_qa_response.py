from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReportQaCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: int = Field(strict=True, gt=0)
    chunk_id: int = Field(strict=True, gt=0)
    page_number: int = Field(strict=True, ge=1)
    report_name: str

    @field_validator("report_name")
    @classmethod
    def normalize_report_name(cls, value: str) -> str:
        normalized_value = value.strip() if isinstance(value, str) else ""
        if not normalized_value:
            raise ValueError("report_name must not be blank.")
        return normalized_value


class ReportQaAiResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    answer: str
    citations: list[ReportQaCitation]
    confidence_score: Decimal
    suggested_followups: list[str]
    disclaimer: str
    model_version: str
    formula_version: None

    @field_validator("answer", "disclaimer", "model_version")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized_value = value.strip() if isinstance(value, str) else ""
        if not normalized_value:
            raise ValueError("String must not be blank.")
        return normalized_value

    @field_validator("suggested_followups")
    @classmethod
    def normalize_followups(cls, value: list[str]) -> list[str]:
        normalized_values = []
        for followup in value:
            normalized_value = followup.strip() if isinstance(followup, str) else ""
            if not normalized_value:
                raise ValueError("Suggested followups must not be blank.")
            normalized_values.append(normalized_value)
        return normalized_values

    @field_validator("confidence_score")
    @classmethod
    def validate_finite_confidence_score(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("confidence_score must be finite.")
        return value


class ReportQaResponse(ReportQaAiResult):
    analysis_id: int
    report_id: int