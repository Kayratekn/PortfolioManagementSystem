from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    portfolio_id: int
    note_text: str
    created_at: datetime


class NoteListResponse(BaseModel):
    items: list[NoteResponse]
    total: int
    skip: int
    limit: int
