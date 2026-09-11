from __future__ import annotations

from fastapi import HTTPException, status

from src.model.report_document import ReportDocument
from src.model.user import User
from src.repositories.report_repository import ReportRepository
from src.response.report_response import ReportListResponse, ReportResponse


class ReportReadService:
    def __init__(self, *, report_repository: ReportRepository) -> None:
        self.report_repository = report_repository

    def list_reports(self, *, current_user: User, skip: int, limit: int) -> ReportListResponse:
        reports = self.report_repository.list_documents_by_user(
            user_id=current_user.id,
            skip=skip,
            limit=limit,
        )
        return ReportListResponse(
            total=self.report_repository.count_documents_by_user(user_id=current_user.id),
            skip=skip,
            limit=limit,
            items=[self._to_response(report) for report in reports],
        )

    def get_report(self, *, report_id: int, current_user: User) -> ReportResponse:
        report = self.report_repository.get_document_by_id_for_user(
            report_id=report_id,
            user_id=current_user.id,
        )
        if report is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
        return self._to_response(report)

    @staticmethod
    def _to_response(report: ReportDocument) -> ReportResponse:
        return ReportResponse(
            report_id=report.id,
            original_filename=report.original_filename,
            content_type=report.content_type,
            file_size_bytes=report.file_size_bytes,
            page_count=report.page_count,
            created_at=report.created_at,
        )
