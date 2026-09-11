from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReportUploadResponse(BaseModel):
    report_id: int
    original_filename: str
    content_type: str
    file_size_bytes: int
    page_count: int
    chunk_count: int
    created_at: datetime


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: int
    original_filename: str
    content_type: str
    file_size_bytes: int
    page_count: int
    created_at: datetime


class ReportListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[ReportResponse]
