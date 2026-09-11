from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from src.config.dependencies import (
    get_current_user,
    get_report_qa_service,
    get_report_read_service,
    get_report_upload_service,
)
from src.model.user import User
from src.request.report_qa_request import ReportQaRequest
from src.response.report_qa_response import ReportQaResponse
from src.response.report_response import ReportListResponse, ReportResponse, ReportUploadResponse
from src.services.report_qa_service import ReportQaService
from src.services.report_read_service import ReportReadService
from src.services.report_upload_service import ReportUploadService


router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.post("", response_model=ReportUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_report(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    report_upload_service: Annotated[ReportUploadService, Depends(get_report_upload_service)],
) -> ReportUploadResponse:
    return report_upload_service.upload_report(
        source=file.file,
        original_filename=file.filename,
        content_type=file.content_type,
        current_user=current_user,
    )


@router.get("", response_model=ReportListResponse)
def list_reports(
    current_user: Annotated[User, Depends(get_current_user)],
    report_read_service: Annotated[ReportReadService, Depends(get_report_read_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> ReportListResponse:
    return report_read_service.list_reports(current_user=current_user, skip=skip, limit=limit)


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    report_read_service: Annotated[ReportReadService, Depends(get_report_read_service)],
) -> ReportResponse:
    return report_read_service.get_report(report_id=report_id, current_user=current_user)


@router.post("/{report_id}/questions", response_model=ReportQaResponse)
def answer_report_question(
    report_id: int,
    payload: ReportQaRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    report_qa_service: Annotated[ReportQaService, Depends(get_report_qa_service)],
) -> ReportQaResponse:
    return report_qa_service.answer_question(
        report_id=report_id,
        query=payload.query,
        current_user=current_user,
    )
