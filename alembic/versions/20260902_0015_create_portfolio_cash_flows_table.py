from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260902_0015"
down_revision = "20260902_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio_cash_flows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("flow_type", sa.String(length=10), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("flow_date", sa.Date(), nullable=False),
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
            "flow_type IN ('DEPOSIT', 'WITHDRAWAL')",
            name="ck_portfolio_cash_flows_flow_type_allowed",
        ),
        sa.CheckConstraint(
            "amount > 0",
            name="ck_portfolio_cash_flows_amount_positive",
        ),
        sa.CheckConstraint(
            "currency IN ('TRY', 'USD', 'EUR', 'GBP')",
            name="ck_portfolio_cash_flows_currency_allowed",
        ),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_cash_flows_portfolio_date_id",
        "portfolio_cash_flows",
        ["portfolio_id", "flow_date", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portfolio_cash_flows_portfolio_date_id",
        table_name="portfolio_cash_flows",
    )
    op.drop_table("portfolio_cash_flows")
