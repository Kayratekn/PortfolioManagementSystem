from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SentimentLabel = Literal["positive", "neutral", "negative"]


class AiSentimentDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = Field(strict=True)
    label: SentimentLabel
    confidence: Decimal

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank.")
        return value

    @field_validator("confidence")
    @classmethod
    def validate_finite_confidence(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("confidence must be finite.")
        return value


class AiSentimentAiResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    overall_score: Decimal
    overall_label: SentimentLabel
    details: list[AiSentimentDetail]
    model_version: str = Field(strict=True)
    formula_version: None

    @field_validator("overall_score")
    @classmethod
    def validate_overall_score(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or not Decimal("-1") <= value <= Decimal("1"):
            raise ValueError("overall_score must be finite and between -1 and 1.")
        return value

    @field_validator("model_version")
    @classmethod
    def normalize_model_version(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("model_version must not be blank.")
        return normalized_value


class AiSentimentResponse(BaseModel):
    analysis_id: int
    overall_score: Decimal
    overall_label: SentimentLabel
    model_version: str
    formula_version: None