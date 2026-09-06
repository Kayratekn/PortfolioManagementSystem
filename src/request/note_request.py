from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NoteCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    portfolio_id: int = Field(gt=0)
    note_text: str = Field(min_length=1, max_length=2000)

    @field_validator("note_text", mode="before")
    @classmethod
    def trim_note_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value
