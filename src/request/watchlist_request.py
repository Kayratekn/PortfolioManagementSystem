from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WatchlistCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: int = Field(gt=0)
