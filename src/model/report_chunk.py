from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base


class ReportChunk(Base):
    __tablename__ = "report_chunks"
    __table_args__ = (
        CheckConstraint(
            "chunk_index >= 0",
            name="ck_report_chunks_chunk_index_nonnegative",
        ),
        CheckConstraint(
            "page_number >= 1",
            name="ck_report_chunks_page_number_positive",
        ),
        CheckConstraint(
            "length(trim(text)) > 0",
            name="ck_report_chunks_text_nonblank",
        ),
        UniqueConstraint(
            "report_document_id",
            "chunk_index",
            name="uq_report_chunks_document_chunk_index",
        ),
        Index("ix_report_chunks_document_chunk_index", "report_document_id", "chunk_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_document_id: Mapped[int] = mapped_column(
        ForeignKey("report_documents.id"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
