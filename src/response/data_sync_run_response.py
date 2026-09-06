from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DataSyncRunStatusItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sync_type: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None


class DataSyncStatusResponse(BaseModel):
    items: list[DataSyncRunStatusItemResponse]
    total: int
