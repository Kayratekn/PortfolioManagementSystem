from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260811_0005"
down_revision = "20260802_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tefas_fund_allocation_data",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("data_date", sa.Date(), nullable=False),
        sa.Column("raw_field_name", sa.String(length=20), nullable=False),
        sa.Column("allocation_percentage", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.UniqueConstraint(
            "asset_id",
            "data_date",
            "raw_field_name",
            name="uq_tefas_fund_allocation_data_asset_date_field",
        ),
    )


def downgrade() -> None:
    op.drop_table("tefas_fund_allocation_data")
