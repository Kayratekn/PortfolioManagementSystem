from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260823_0011"
down_revision = "20260820_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tefas_fund_detail_snapshots") as batch_op:
        batch_op.add_column(sa.Column("tefas_status", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column("transaction_start_time", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(
            sa.Column("transaction_end_time", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(
            sa.Column("entry_commission_raw", sa.Numeric(20, 10), nullable=True)
        )
        batch_op.add_column(
            sa.Column("exit_commission_raw", sa.Numeric(20, 10), nullable=True)
        )
        batch_op.add_column(sa.Column("interest_content", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("fund_sale_valor", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("fund_redemption_valor", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tefas_fund_detail_snapshots") as batch_op:
        batch_op.drop_column("fund_redemption_valor")
        batch_op.drop_column("fund_sale_valor")
        batch_op.drop_column("interest_content")
        batch_op.drop_column("exit_commission_raw")
        batch_op.drop_column("entry_commission_raw")
        batch_op.drop_column("transaction_end_time")
        batch_op.drop_column("transaction_start_time")
        batch_op.drop_column("tefas_status")
