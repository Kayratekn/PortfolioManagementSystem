from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260908_0024"
down_revision = "20260907_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=40), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(original_filename)) > 0",
            name="ck_report_documents_original_filename_nonblank",
        ),
        sa.CheckConstraint(
            "length(trim(storage_key)) > 0",
            name="ck_report_documents_storage_key_nonblank",
        ),
        sa.CheckConstraint(
            "file_size_bytes > 0",
            name="ck_report_documents_file_size_positive",
        ),
        sa.CheckConstraint(
            "page_count >= 1",
            name="ck_report_documents_page_count_positive",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        "ix_report_documents_user_created_id",
        "report_documents",
        ["user_id", "created_at", "id"],
    )
    op.create_table(
        "report_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "chunk_index >= 0",
            name="ck_report_chunks_chunk_index_nonnegative",
        ),
        sa.CheckConstraint(
            "page_number >= 1",
            name="ck_report_chunks_page_number_positive",
        ),
        sa.CheckConstraint(
            "length(trim(text)) > 0",
            name="ck_report_chunks_text_nonblank",
        ),
        sa.ForeignKeyConstraint(["report_document_id"], ["report_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "report_document_id",
            "chunk_index",
            name="uq_report_chunks_document_chunk_index",
        ),
    )
    op.create_index(
        "ix_report_chunks_document_chunk_index",
        "report_chunks",
        ["report_document_id", "chunk_index"],
    )


def downgrade() -> None:
    op.drop_index("ix_report_chunks_document_chunk_index", table_name="report_chunks")
    op.drop_table("report_chunks")
    op.drop_index("ix_report_documents_user_created_id", table_name="report_documents")
    op.drop_table("report_documents")
