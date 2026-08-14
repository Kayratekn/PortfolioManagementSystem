from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base, TimestampMixin


class TefasFundDetailSnapshot(TimestampMixin, Base):
    __tablename__ = "tefas_fund_detail_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "asset_id",
            "observed_at",
            name="uq_tefas_fund_detail_snapshots_asset_observed_at",
        ),
        CheckConstraint(
            "category_rank IS NULL OR category_rank >= 0",
            name="ck_tefas_fund_detail_snapshots_category_rank_nonnegative",
        ),
        CheckConstraint(
            "category_fund_count IS NULL OR category_fund_count >= 0",
            name="ck_tefas_fund_detail_snapshots_category_fund_count_nonnegative",
        ),
        Index(
            "ix_tefas_fund_detail_snapshots_category_observed_at",
            "fund_category",
            "observed_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    fund_category: Mapped[str] = mapped_column(String(255), nullable=False)
    category_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category_fund_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    market_share_raw: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    source_page: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="fon-detayli-analiz",
        server_default="fon-detayli-analiz",
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
