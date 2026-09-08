from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base


class ReportDocument(Base):
    __tablename__ = "report_documents"
    __table_args__ = (
        CheckConstraint(
            "length(trim(original_filename)) > 0",
            name="ck_report_documents_original_filename_nonblank",
        ),
        CheckConstraint(
            "length(trim(storage_key)) > 0",
            name="ck_report_documents_storage_key_nonblank",
        ),
        CheckConstraint(
            "file_size_bytes > 0",
            name="ck_report_documents_file_size_positive",
        ),
        CheckConstraint(
            "page_count >= 1",
            name="ck_report_documents_page_count_positive",
        ),
        Index("ix_report_documents_user_created_id", "user_id", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
