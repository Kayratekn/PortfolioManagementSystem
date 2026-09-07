from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260907_0022"
down_revision = "20260907_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("total_value_try", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("total_value_usd", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("total_value_eur", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("total_value_gbp", sa.Numeric(precision=20, scale=8), nullable=False),
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
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portfolio_id",
            "snapshot_date",
            name="uq_portfolio_snapshots_portfolio_date",
        ),
    )
    op.create_index(
        "ix_portfolio_snapshots_portfolio_date_id",
        "portfolio_snapshots",
        ["portfolio_id", "snapshot_date", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_portfolio_snapshots_portfolio_date_id", table_name="portfolio_snapshots")
    op.drop_table("portfolio_snapshots")