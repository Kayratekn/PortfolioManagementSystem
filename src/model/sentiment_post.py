from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base


class SentimentPost(Base):
    __tablename__ = "sentiment_posts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["expert_source_id", "source_key"],
            ["expert_sources.id", "expert_sources.source_key"],
            name="fk_sentiment_posts_expert_source_source_key",
        ),
        CheckConstraint("length(trim(source_key)) > 0", name="ck_sentiment_posts_source_key_nonblank"),
        CheckConstraint("source_key = upper(source_key)", name="ck_sentiment_posts_source_key_uppercase"),
        CheckConstraint("external_id IS NULL OR length(trim(external_id)) > 0", name="ck_sentiment_posts_external_id_null_or_nonblank"),
        CheckConstraint("url IS NULL OR length(trim(url)) > 0", name="ck_sentiment_posts_url_null_or_nonblank"),
        CheckConstraint("canonical_url IS NULL OR length(trim(canonical_url)) > 0", name="ck_sentiment_posts_canonical_url_null_or_nonblank"),
        CheckConstraint("title IS NULL OR length(trim(title)) > 0", name="ck_sentiment_posts_title_null_or_nonblank"),
        CheckConstraint("length(trim(content)) > 0", name="ck_sentiment_posts_content_nonblank"),
        CheckConstraint("author_name IS NULL OR length(trim(author_name)) > 0", name="ck_sentiment_posts_author_name_null_or_nonblank"),
        CheckConstraint("author_handle IS NULL OR length(trim(author_handle)) > 0", name="ck_sentiment_posts_author_handle_null_or_nonblank"),
        CheckConstraint("length(trim(language)) > 0", name="ck_sentiment_posts_language_nonblank"),
        CheckConstraint("content_type IN ('NEWS', 'RSS', 'SOCIAL')", name="ck_sentiment_posts_content_type"),
        CheckConstraint("external_id IS NOT NULL OR canonical_url IS NOT NULL", name="ck_sentiment_posts_duplicate_identity"),
        Index("ix_sentiment_posts_published_id", "published_at", "id"),
        Index("uq_sentiment_posts_source_external_id", "source_key", "external_id", unique=True, postgresql_where=text("external_id IS NOT NULL"), sqlite_where=text("external_id IS NOT NULL")),
        Index("uq_sentiment_posts_source_canonical_url", "source_key", "canonical_url", unique=True, postgresql_where=text("external_id IS NULL AND canonical_url IS NOT NULL"), sqlite_where=text("external_id IS NULL AND canonical_url IS NOT NULL")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    expert_source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_key: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author_handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)