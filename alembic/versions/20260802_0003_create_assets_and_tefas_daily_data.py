from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260802_0003"
down_revision = "20260730_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("asset_code", sa.String(length=20), nullable=False),
        sa.Column("asset_name", sa.String(length=255), nullable=False),
        sa.Column("asset_type", sa.String(length=30), nullable=False),
        sa.Column("fund_kind", sa.String(length=10), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("data_source", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "data_source",
            "asset_code",
            name="uq_assets_data_source_asset_code",
        ),
    )
    op.create_table(
        "tefas_fund_daily_data",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("data_date", sa.Date(), nullable=False),
        sa.Column("price", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("shares_outstanding", sa.Numeric(precision=25, scale=4), nullable=True),
        sa.Column("investor_count", sa.Integer(), nullable=True),
        sa.Column("portfolio_size", sa.Numeric(precision=25, scale=4), nullable=True),
        sa.Column("exchange_bulletin_price", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.UniqueConstraint(
            "asset_id",
            "data_date",
            name="uq_tefas_fund_daily_data_asset_date",
        ),
    )


def downgrade() -> None:
    op.drop_table("tefas_fund_daily_data")
    op.drop_table("assets")
