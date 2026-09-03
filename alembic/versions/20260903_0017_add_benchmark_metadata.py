from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260903_0017"
down_revision = "20260903_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    benchmark_count = connection.scalar(sa.text("SELECT COUNT(*) FROM benchmarks"))
    if benchmark_count:
        raise RuntimeError(
            "Cannot apply benchmark metadata migration 20260903_0017 while benchmarks contains "
            "existing rows. Resolve index_owner and return_type metadata for existing benchmarks "
            "before applying this migration."
        )

    with op.batch_alter_table("benchmarks") as batch_op:
        batch_op.add_column(sa.Column("index_owner", sa.String(length=100), nullable=False))
        batch_op.add_column(sa.Column("return_type", sa.String(length=20), nullable=False))
        batch_op.create_check_constraint(
            "ck_benchmarks_index_owner_required_uppercase",
            "length(trim(index_owner)) > 0 AND index_owner = upper(index_owner)",
        )
        batch_op.create_check_constraint(
            "ck_benchmarks_return_type_allowed",
            "return_type IN ('PRICE_RETURN', 'TOTAL_RETURN')",
        )


def downgrade() -> None:
    with op.batch_alter_table("benchmarks") as batch_op:
        batch_op.drop_constraint("ck_benchmarks_return_type_allowed", type_="check")
        batch_op.drop_constraint("ck_benchmarks_index_owner_required_uppercase", type_="check")
        batch_op.drop_column("return_type")
        batch_op.drop_column("index_owner")