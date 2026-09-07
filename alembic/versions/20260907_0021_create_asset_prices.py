from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260907_0021"
down_revision = "20260907_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("price", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "price > 0",
            name="ck_asset_prices_price_positive",
        ),
        sa.CheckConstraint(
            "length(trim(source)) > 0",
            name="ck_asset_prices_source_nonblank",
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "asset_id",
            "price_date",
            "source",
            name="uq_asset_prices_asset_date_source",
        ),
    )
    op.create_index(
        "ix_asset_prices_asset_date_id",
        "asset_prices",
        ["asset_id", "price_date", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_asset_prices_asset_date_id", table_name="asset_prices")
    op.drop_table("asset_prices")