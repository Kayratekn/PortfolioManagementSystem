from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260826_0013"
down_revision = "20260825_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("quote_currency", sa.String(length=3), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("forex_buying", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("forex_selling", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "base_currency",
            "quote_currency",
            "rate_date",
            "source",
            name="uq_exchange_rates_pair_date_source",
        ),
        sa.CheckConstraint(
            "base_currency != quote_currency",
            name="ck_exchange_rates_distinct_currencies",
        ),
        sa.CheckConstraint(
            "forex_buying > 0",
            name="ck_exchange_rates_forex_buying_positive",
        ),
        sa.CheckConstraint(
            "forex_selling > 0",
            name="ck_exchange_rates_forex_selling_positive",
        ),
    )


def downgrade() -> None:
    op.drop_table("exchange_rates")