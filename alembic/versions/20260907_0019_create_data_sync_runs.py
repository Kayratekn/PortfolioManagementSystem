from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260907_0019"
down_revision = "20260907_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_sync_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sync_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            "sync_type IN ('TEFAS_DAILY', 'BENCHMARK_DAILY')",
            name="ck_data_sync_runs_sync_type_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'SUCCESS', 'FAILED')",
            name="ck_data_sync_runs_status_allowed",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_data_sync_runs_type_started_id",
        "data_sync_runs",
        ["sync_type", "started_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_data_sync_runs_type_started_id", table_name="data_sync_runs")
    op.drop_table("data_sync_runs")
