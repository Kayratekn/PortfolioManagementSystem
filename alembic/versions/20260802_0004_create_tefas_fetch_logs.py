from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260802_0004"
down_revision = "20260802_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tefas_fetch_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("data_source", sa.String(length=20), nullable=False),
        sa.Column("fund_kind", sa.String(length=10), nullable=False),
        sa.Column("fund_code", sa.String(length=20), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="RUNNING"),
        sa.Column("fetched_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assets_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assets_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("daily_rows_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("daily_rows_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'SUCCESS', 'FAILED')",
            name="ck_tefas_fetch_logs_status_allowed",
        ),
        sa.CheckConstraint(
            "start_date <= end_date",
            name="ck_tefas_fetch_logs_date_range_valid",
        ),
        sa.CheckConstraint(
            "fetched_rows >= 0",
            name="ck_tefas_fetch_logs_fetched_rows_nonnegative",
        ),
        sa.CheckConstraint(
            "assets_created >= 0",
            name="ck_tefas_fetch_logs_assets_created_nonnegative",
        ),
        sa.CheckConstraint(
            "assets_updated >= 0",
            name="ck_tefas_fetch_logs_assets_updated_nonnegative",
        ),
        sa.CheckConstraint(
            "daily_rows_created >= 0",
            name="ck_tefas_fetch_logs_daily_rows_created_nonnegative",
        ),
        sa.CheckConstraint(
            "daily_rows_updated >= 0",
            name="ck_tefas_fetch_logs_daily_rows_updated_nonnegative",
        ),
    )
    op.create_index(
        "ix_tefas_fetch_logs_source_kind_started_at",
        "tefas_fetch_logs",
        ["data_source", "fund_kind", "started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tefas_fetch_logs_source_kind_started_at", table_name="tefas_fetch_logs")
    op.drop_table("tefas_fetch_logs")
