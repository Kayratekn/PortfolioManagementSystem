from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base


class AiAnalysis(Base):
    __tablename__ = "ai_analyses"
    __table_args__ = (
        CheckConstraint(
            "length(trim(analysis_type)) > 0",
            name="ck_ai_analyses_analysis_type_nonblank",
        ),
        CheckConstraint(
            "length(trim(model_version)) > 0",
            name="ck_ai_analyses_model_version_nonblank",
        ),
        CheckConstraint(
            "formula_version IS NULL OR length(trim(formula_version)) > 0",
            name="ck_ai_analyses_formula_version_null_or_nonblank",
        ),
        Index("ix_ai_analyses_user_created_id", "user_id", "created_at", "id"),
        Index("ix_ai_analyses_portfolio_created_id", "portfolio_id", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    portfolio_id: Mapped[int | None] = mapped_column(ForeignKey("portfolios.id"), nullable=True)
    analysis_type: Mapped[str] = mapped_column(String(50), nullable=False)
    result_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    explanation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    disclaimer: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    formula_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )