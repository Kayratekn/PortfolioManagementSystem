from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260907_0023"
down_revision = "20260907_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_analyses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=True),
        sa.Column("analysis_type", sa.String(length=50), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("explanation_text", sa.Text(), nullable=True),
        sa.Column("disclaimer", sa.Text(), nullable=True),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("formula_version", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(analysis_type)) > 0",
            name="ck_ai_analyses_analysis_type_nonblank",
        ),
        sa.CheckConstraint(
            "length(trim(model_version)) > 0",
            name="ck_ai_analyses_model_version_nonblank",
        ),
        sa.CheckConstraint(
            "formula_version IS NULL OR length(trim(formula_version)) > 0",
            name="ck_ai_analyses_formula_version_null_or_nonblank",
        ),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_analyses_user_created_id",
        "ai_analyses",
        ["user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_ai_analyses_portfolio_created_id",
        "ai_analyses",
        ["portfolio_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_analyses_portfolio_created_id", table_name="ai_analyses")
    op.drop_index("ix_ai_analyses_user_created_id", table_name="ai_analyses")
    op.drop_table("ai_analyses")