from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260814_0007"
down_revision = "20260812_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tefas_fund_detail_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("fund_category", sa.String(length=255), nullable=False),
        sa.Column("category_rank", sa.Integer(), nullable=True),
        sa.Column("category_fund_count", sa.Integer(), nullable=True),
        sa.Column("market_share_raw", sa.Numeric(precision=20, scale=10), nullable=True),
        sa.Column(
            "source_page",
            sa.String(length=100),
            nullable=False,
            server_default="fon-detayli-analiz",
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.UniqueConstraint(
            "asset_id",
            "observed_at",
            name="uq_tefas_fund_detail_snapshots_asset_observed_at",
        ),
        sa.CheckConstraint(
            "category_rank IS NULL OR category_rank >= 0",
            name="ck_tefas_fund_detail_snapshots_category_rank_nonnegative",
        ),
        sa.CheckConstraint(
            "category_fund_count IS NULL OR category_fund_count >= 0",
            name="ck_tefas_fund_detail_snapshots_category_fund_count_nonnegative",
        ),
    )
    op.create_index(
        "ix_tefas_fund_detail_snapshots_category_observed_at",
        "tefas_fund_detail_snapshots",
        ["fund_category", "observed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tefas_fund_detail_snapshots_category_observed_at",
        table_name="tefas_fund_detail_snapshots",
    )
    op.drop_table("tefas_fund_detail_snapshots")
