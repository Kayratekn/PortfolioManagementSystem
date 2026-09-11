from __future__ import annotations

from urllib.parse import quote

from fastapi import HTTPException, status
from fastapi.responses import Response

from src.integrations.local_report_storage import LocalReportStorage, ReportStorageError
from src.model.user import User
from src.repositories.report_repository import ReportRepository


class ReportDownloadService:
    def __init__(
        self,
        *,
        report_repository: ReportRepository,
        storage: LocalReportStorage,
    ) -> None:
        self.report_repository = report_repository
        self.storage = storage

    def download_report(self, *, report_id: int, current_user: User) -> Response:
        report = self.report_repository.get_document_by_id_for_user(
            report_id=report_id,
            user_id=current_user.id,
        )
        if report is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")

        try:
            content = self.storage.read_bytes(report.storage_key)
        except ReportStorageError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Report file is unavailable.",
            ) from exc

        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": self._content_disposition(report.original_filename)},
        )

    @staticmethod
    def _content_disposition(filename: str) -> str:
        return f"attachment; filename*=UTF-8''{quote(filename, safe='')}"
