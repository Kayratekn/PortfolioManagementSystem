from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base, TimestampMixin


class UserExpertSource(TimestampMixin, Base):
    __tablename__ = "user_expert_sources"
    __table_args__ = (
        UniqueConstraint("user_id", "expert_source_id", name="uq_user_expert_sources_user_source"),
        Index("ix_user_expert_sources_user_id_id", "user_id", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    expert_source_id: Mapped[int] = mapped_column(ForeignKey("expert_sources.id"), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))