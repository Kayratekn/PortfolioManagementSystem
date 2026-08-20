from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260820_0010"
down_revision = "20260819_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tefas_management_fee_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("management_fee_percentage", sa.Numeric(18, 6), nullable=False),
        sa.Column("source_endpoint", sa.String(length=100), nullable=False),
        sa.Column("source_field_name", sa.String(length=50), nullable=False),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
    )
    op.create_index(
        "ix_tefas_management_fee_history_asset_first_observed_at",
        "tefas_management_fee_history",
        ["asset_id", "first_observed_at"],
        unique=False,
    )
    op.create_index(
        "ix_tefas_management_fee_history_fee_closed_at",
        "tefas_management_fee_history",
        ["management_fee_percentage", "closed_at"],
        unique=False,
    )
    op.create_index(
        "uq_tefas_management_fee_history_one_open_per_asset",
        "tefas_management_fee_history",
        ["asset_id"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_tefas_management_fee_history_one_open_per_asset",
        table_name="tefas_management_fee_history",
    )
    op.drop_index(
        "ix_tefas_management_fee_history_fee_closed_at",
        table_name="tefas_management_fee_history",
    )
    op.drop_index(
        "ix_tefas_management_fee_history_asset_first_observed_at",
        table_name="tefas_management_fee_history",
    )
    op.drop_table("tefas_management_fee_history")
