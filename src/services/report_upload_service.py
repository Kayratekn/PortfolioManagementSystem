from __future__ import annotations

import re
from typing import BinaryIO

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.integrations.local_report_storage import (
    LocalReportStorage,
    ReportFileTooLargeError,
    ReportStorageError,
    StoredReportFile,
)
from src.integrations.pdf_text_extractor import (
    EncryptedPdfError,
    ExtractedPdfPage,
    PdfExtractionError,
    PdfTextExtractor,
)
from src.model.report_chunk import ReportChunk
from src.model.report_document import ReportDocument
from src.model.user import User
from src.repositories.report_repository import ReportRepository
from src.response.report_response import ReportUploadResponse


class ReportUploadService:
    def __init__(
        self,
        *,
        db: Session,
        report_repository: ReportRepository,
        storage: LocalReportStorage,
        pdf_text_extractor: PdfTextExtractor,
    ) -> None:
        self.db = db
        self.report_repository = report_repository
        self.storage = storage
        self.pdf_text_extractor = pdf_text_extractor

    def upload_report(
        self,
        *,
        source: BinaryIO,
        original_filename: str | None,
        content_type: str | None,
        current_user: User,
    ) -> ReportUploadResponse:
        normalized_filename = self._validate_filename(original_filename)
        normalized_content_type = self._validate_content_type(content_type)
        stored_file: StoredReportFile | None = None

        try:
            stored_file = self.storage.save(source)
            self._validate_stored_file(stored_file)

            pages = self._extract_pages(stored_file)
            chunks = self._build_chunks(pages)
            if not chunks:
                raise self._unprocessable("PDF must contain extractable text.")

            document = ReportDocument(
                user_id=current_user.id,
                original_filename=normalized_filename,
                storage_key=stored_file.storage_key,
                content_type=normalized_content_type,
                file_size_bytes=stored_file.file_size_bytes,
                sha256=stored_file.sha256,
                page_count=len(pages),
            )
            report_chunks = [
                ReportChunk(
                    chunk_index=chunk_index,
                    page_number=page_number,
                    text=text,
                )
                for chunk_index, page_number, text in chunks
            ]
            created = self.report_repository.add_document_with_chunks(
                document=document,
                chunks=report_chunks,
            )
            response = ReportUploadResponse(
                report_id=created.id,
                original_filename=created.original_filename,
                content_type=created.content_type,
                file_size_bytes=created.file_size_bytes,
                page_count=created.page_count,
                chunk_count=len(report_chunks),
                created_at=created.created_at,
            )
            self.db.commit()
            return response
        except HTTPException:
            self.db.rollback()
            if not self._cleanup(stored_file):
                raise self._internal_error()
            raise
        except ReportFileTooLargeError:
            self.db.rollback()
            if not self._cleanup(stored_file):
                raise self._internal_error()
            raise self._unprocessable("Report file exceeds the maximum allowed size.")
        except Exception:
            self.db.rollback()
            if not self._cleanup(stored_file):
                raise self._internal_error()
            raise self._internal_error()

    @staticmethod
    def _validate_filename(value: str | None) -> str:
        filename = value.strip() if isinstance(value, str) else ""
        if not filename:
            raise ReportUploadService._unprocessable("A PDF filename is required.")
        if not filename.lower().endswith(".pdf"):
            raise ReportUploadService._unprocessable("Only PDF files are supported.")
        if len(filename) > 255:
            raise ReportUploadService._unprocessable("PDF filename is too long.")
        return filename

    @staticmethod
    def _validate_content_type(value: str | None) -> str:
        content_type = value.strip().lower() if isinstance(value, str) else ""
        if content_type != "application/pdf":
            raise ReportUploadService._unprocessable("Content type must be application/pdf.")
        return content_type

    @classmethod
    def _validate_stored_file(cls, stored_file: StoredReportFile) -> None:
        if stored_file.file_size_bytes == 0:
            raise cls._unprocessable("PDF file must not be empty.")
        if not stored_file.header.startswith(b"%PDF-"):
            raise cls._unprocessable("Uploaded file is not a valid PDF.")

    def _extract_pages(self, stored_file: StoredReportFile) -> list[ExtractedPdfPage]:
        try:
            pages = self.pdf_text_extractor.extract(stored_file.path)
        except EncryptedPdfError:
            raise self._unprocessable("Encrypted PDF files are not supported.")
        except PdfExtractionError:
            raise self._unprocessable("PDF file could not be read.")

        if not pages:
            raise self._unprocessable("PDF must contain at least one page.")
        return pages

    @staticmethod
    def _build_chunks(pages: list[ExtractedPdfPage]) -> list[tuple[int, int, str]]:
        chunks: list[tuple[int, int, str]] = []
        for page in pages:
            for paragraph in re.split(r"\r?\n[ \t\r]*\r?\n", page.text):
                normalized_text = paragraph.strip()
                if normalized_text:
                    chunks.append((len(chunks), page.page_number, normalized_text))
        return chunks

    @staticmethod
    def _unprocessable(detail: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)

    @staticmethod
    def _internal_error() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report upload could not be completed.",
        )

    def _cleanup(self, stored_file: StoredReportFile | None) -> bool:
        if stored_file is None:
            return True
        try:
            self.storage.cleanup(stored_file.storage_key)
        except ReportStorageError:
            return False
        return True
