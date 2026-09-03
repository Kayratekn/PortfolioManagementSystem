from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260903_0016"
down_revision = "20260902_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "benchmarks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("benchmark_type", sa.String(length=20), nullable=False),
        sa.Column("native_currency", sa.String(length=3), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_symbol", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
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
            "benchmark_type IN ('MARKET_INDEX', 'TEFAS_FUND')",
            name="ck_benchmarks_benchmark_type_allowed",
        ),
        sa.CheckConstraint(
            "length(native_currency) = 3 "
            "AND native_currency = upper(native_currency) "
            "AND substr(native_currency, 1, 1) BETWEEN 'A' AND 'Z' "
            "AND substr(native_currency, 2, 1) BETWEEN 'A' AND 'Z' "
            "AND substr(native_currency, 3, 1) BETWEEN 'A' AND 'Z'",
            name="ck_benchmarks_native_currency_uppercase_3",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_benchmarks_code"),
        sa.UniqueConstraint(
            "provider",
            "provider_symbol",
            name="uq_benchmarks_provider_provider_symbol",
        ),
    )
    op.create_table(
        "benchmark_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("benchmark_id", sa.Integer(), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("close_value", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
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
            "close_value > 0",
            name="ck_benchmark_prices_close_value_positive",
        ),
        sa.ForeignKeyConstraint(["benchmark_id"], ["benchmarks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "benchmark_id",
            "price_date",
            name="uq_benchmark_prices_benchmark_date",
        ),
    )
    op.create_index(
        "ix_benchmark_prices_benchmark_date",
        "benchmark_prices",
        ["benchmark_id", "price_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_benchmark_prices_benchmark_date",
        table_name="benchmark_prices",
    )
    op.drop_table("benchmark_prices")
    op.drop_table("benchmarks")
