from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260902_0014"
down_revision = "20260826_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("transaction_currency", sa.String(length=3), nullable=True),
    )
    op.create_check_constraint(
        "ck_transactions_transaction_currency_allowed",
        "transactions",
        "transaction_currency IS NULL OR transaction_currency IN ('TRY', 'USD', 'EUR', 'GBP')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_transactions_transaction_currency_allowed",
        "transactions",
        type_="check",
    )
    op.drop_column("transactions", "transaction_currency")
