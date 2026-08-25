from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260825_0012"
down_revision = "20260823_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "transaction_type IN ('BUY', 'SELL')",
            name="ck_transactions_transaction_type_allowed",
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_transactions_quantity_positive",
        ),
        sa.CheckConstraint(
            "unit_price > 0",
            name="ck_transactions_unit_price_positive",
        ),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
    )


def downgrade() -> None:
    op.drop_table("transactions")