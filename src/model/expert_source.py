from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base, TimestampMixin


class ExpertSource(TimestampMixin, Base):
    __tablename__ = "expert_sources"
    __table_args__ = (
        CheckConstraint("length(trim(source_key)) > 0", name="ck_expert_sources_source_key_nonblank"),
        CheckConstraint("source_key = upper(source_key)", name="ck_expert_sources_source_key_uppercase"),
        CheckConstraint("length(trim(author_handle)) > 0", name="ck_expert_sources_author_handle_nonblank"),
        CheckConstraint("author_name IS NULL OR length(trim(author_name)) > 0", name="ck_expert_sources_author_name_null_or_nonblank"),
        CheckConstraint("profile_url IS NULL OR length(trim(profile_url)) > 0", name="ck_expert_sources_profile_url_null_or_nonblank"),
        UniqueConstraint("source_key", "author_handle", name="uq_expert_sources_source_handle"),
        UniqueConstraint("id", "source_key", name="uq_expert_sources_id_source_key"),
        Index("ix_expert_sources_active_source_handle_id", "is_active", "source_key", "author_handle", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_key: Mapped[str] = mapped_column(String(50), nullable=False)
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author_handle: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))