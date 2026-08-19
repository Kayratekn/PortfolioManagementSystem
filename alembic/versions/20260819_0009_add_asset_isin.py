from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260819_0009"
down_revision = "20260817_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("assets") as batch_op:
        batch_op.add_column(sa.Column("isin", sa.String(length=32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("assets") as batch_op:
        batch_op.drop_column("isin")