from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class AiPortfolioAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of_date: date