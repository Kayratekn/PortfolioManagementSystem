from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260817_0008"
down_revision = "20260814_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tefas_fund_detail_snapshots") as batch_op:
        batch_op.add_column(sa.Column("risk_value", sa.Integer(), nullable=True))
        batch_op.create_check_constraint(
            "ck_tefas_fund_detail_snapshots_risk_value_range",
            "risk_value IS NULL OR (risk_value >= 1 AND risk_value <= 7)",
        )


def downgrade() -> None:
    with op.batch_alter_table("tefas_fund_detail_snapshots") as batch_op:
        batch_op.drop_constraint(
            "ck_tefas_fund_detail_snapshots_risk_value_range",
            type_="check",
        )
        batch_op.drop_column("risk_value")
