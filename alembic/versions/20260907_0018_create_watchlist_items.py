from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260907_0018"
down_revision = "20260903_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "asset_id", name="uq_watchlist_items_user_asset"),
    )
    op.create_index(
        "ix_watchlist_items_user_id_id",
        "watchlist_items",
        ["user_id", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_watchlist_items_user_id_id", table_name="watchlist_items")
    op.drop_table("watchlist_items")
