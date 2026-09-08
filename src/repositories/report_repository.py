from __future__ import annotations

from sqlalchemy import select
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

    def get_document_by_id_for_user(
        self,
        *,
        report_id: int,
        user_id: int,
    ) -> ReportDocument | None:
        statement = select(ReportDocument).where(
            ReportDocument.id == report_id,
            ReportDocument.user_id == user_id,
        )
        return self.db.scalar(statement)

    def list_chunks_by_document_id(self, *, report_document_id: int) -> list[ReportChunk]:
        statement = (
            select(ReportChunk)
            .where(ReportChunk.report_document_id == report_document_id)
            .order_by(ReportChunk.chunk_index.asc(), ReportChunk.id.asc())
        )
        return list(self.db.scalars(statement))
