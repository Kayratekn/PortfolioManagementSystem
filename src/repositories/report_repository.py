from __future__ import annotations

from sqlalchemy.orm import Session

from src.model.report_chunk import ReportChunk
from src.model.report_document import ReportDocument


class ReportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_document_with_chunks(
        self,
        *,
        document: ReportDocument,
        chunks: list[ReportChunk],
    ) -> ReportDocument:
        self.db.add(document)
        self.db.flush()

        for chunk in chunks:
            chunk.report_document_id = document.id
        self.db.add_all(chunks)
        self.db.flush()
        return document
