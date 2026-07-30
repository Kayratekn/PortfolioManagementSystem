from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260730_0002"
down_revision = "20260724_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "base_currency IN ('TRY', 'USD', 'EUR', 'GBP')",
            name="ck_portfolios_base_currency_allowed",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(
        "ix_portfolios_user_deleted_id",
        "portfolios",
        ["user_id", "deleted_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_portfolios_user_deleted_id", table_name="portfolios")
    op.drop_table("portfolios")
