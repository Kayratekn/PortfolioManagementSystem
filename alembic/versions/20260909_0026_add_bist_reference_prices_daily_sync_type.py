from alembic import op


revision = "20260909_0026"
down_revision = "20260908_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_data_sync_runs_sync_type_allowed",
        "data_sync_runs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_data_sync_runs_sync_type_allowed",
        "data_sync_runs",
        "sync_type IN ('TEFAS_DAILY', 'BENCHMARK_DAILY', 'BIST_REFERENCE_PRICES_DAILY')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_data_sync_runs_sync_type_allowed",
        "data_sync_runs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_data_sync_runs_sync_type_allowed",
        "data_sync_runs",
        "sync_type IN ('TEFAS_DAILY', 'BENCHMARK_DAILY')",
    )