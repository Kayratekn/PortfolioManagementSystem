from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AiAnalysisHistoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    analysis_id: int
    portfolio_id: int | None
    analysis_type: str
    result_payload: dict[str, Any]
    explanation_text: str | None
    disclaimer: str | None
    model_version: str
    formula_version: str | None
    created_at: datetime


class AiAnalysisHistoryListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[AiAnalysisHistoryItemResponse]