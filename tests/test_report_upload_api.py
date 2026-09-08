from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import src.integrations.local_report_storage as local_report_storage_module
from src.config.dependencies import (
    get_ai_client,
    get_pdf_text_extractor,
    get_report_repository,
    get_report_storage,
)
from src.integrations.local_report_storage import LocalReportStorage, ReportStorageError
from src.integrations.pdf_text_extractor import (
    ExtractedPdfPage,
    PdfExtractionError,
    PdfTextExtractor,
)
from src.services.report_upload_service import ReportUploadService
from src.main import app
from src.model.report_chunk import ReportChunk
from src.model.report_document import ReportDocument
from src.model.user import User
from src.repositories.report_repository import ReportRepository


AUTH_DETAIL = "Authentication credentials were not provided or are invalid."
MIGRATION = Path("alembic/versions/20260908_0024_create_report_documents_and_chunks.py")


def register_and_login(client) -> tuple[dict, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "reports@example.com",
            "username": "reports-user",
            "password": "StrongPass123",
            "preferred_currency": "TRY",
        },
    )
    assert response.status_code == 201
    user = response.json()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "reports@example.com", "password": "StrongPass123"},
    )
    assert response.status_code == 200
    return user, response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_pdf_with_text(*pages: str) -> bytes:
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)

    for page_text in pages:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {NameObject("/F1"): font_reference}
                )
            }
        )
        instructions = ["BT", "/F1 12 Tf", "72 720 Td"]
        for line_number, line in enumerate(page_text.split("\n")):
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            if line_number:
                instructions.append("T*")
            if line:
                instructions.append(f"({escaped}) Tj")
        instructions.append("ET")
        stream = DecodedStreamObject()
        stream.set_data(("\n".join(instructions)).encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def make_empty_text_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def make_encrypted_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("secret")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture()
def report_storage(tmp_path: Path, client) -> Path:
    storage_root = tmp_path / "reports"
    app.dependency_overrides[get_report_storage] = lambda: LocalReportStorage(
        root=storage_root,
        max_file_size_bytes=10 * 1024 * 1024,
    )
    yield storage_root
    app.dependency_overrides.pop(get_report_storage, None)


def upload(
    client,
    *,
    token: str | None,
    content: bytes,
    filename: str = "report.pdf",
    content_type: str = "application/pdf",
):
    headers = auth_headers(token) if token is not None else None
    return client.post(
        "/api/v1/reports",
        files={"file": (filename, content, content_type)},
        headers=headers,
    )


def test_report_upload_requires_authentication(client) -> None:
    response = upload(client, token=None, content=make_pdf_with_text("Text"))

    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_DETAIL


def test_valid_upload_persists_document_chunks_and_hides_internal_fields(
    client,
    db_session: Session,
    report_storage: Path,
) -> None:
    user, token = register_and_login(client)
    payload = make_pdf_with_text("First paragraph\n\nSecond paragraph", "Third paragraph")

    response = upload(
        client,
        token=token,
        content=payload,
        filename="Quarterly Report.PDF",
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {
        "report_id",
        "original_filename",
        "content_type",
        "file_size_bytes",
        "page_count",
        "chunk_count",
        "created_at",
    }
    assert body["original_filename"] == "Quarterly Report.PDF"
    assert body["content_type"] == "application/pdf"
    assert body["file_size_bytes"] == len(payload)
    assert body["page_count"] == 2
    assert body["chunk_count"] == 2
    assert {"user_id", "storage_key", "sha256", "text"}.isdisjoint(body)

    document = db_session.get(ReportDocument, body["report_id"])
    assert document is not None
    assert document.user_id == user["id"]
    assert document.original_filename == "Quarterly Report.PDF"
    assert document.content_type == "application/pdf"
    assert document.file_size_bytes == len(payload)
    assert document.sha256 == hashlib.sha256(payload).hexdigest()
    assert document.page_count == 2
    assert re.fullmatch(r"[0-9a-f]{32}\.pdf", document.storage_key)
    assert document.storage_key != document.original_filename
    assert (report_storage / document.storage_key).read_bytes() == payload

    chunks = list(
        db_session.scalars(
            select(ReportChunk)
            .where(ReportChunk.report_document_id == document.id)
            .order_by(ReportChunk.chunk_index)
        )
    )
    assert [(chunk.chunk_index, chunk.page_number, chunk.text) for chunk in chunks] == [
        (0, 1, "First paragraphSecond paragraph"),
        (1, 2, "Third paragraph"),
    ]


def test_chunk_builder_is_deterministic_and_ignores_blank_paragraphs() -> None:
    chunks = ReportUploadService._build_chunks(
        [
            ExtractedPdfPage(page_number=1, text=" First paragraph \n\n  \n\nSecond paragraph  "),
            ExtractedPdfPage(page_number=2, text="\n Third paragraph\n"),
        ]
    )

    assert chunks == [
        (0, 1, "First paragraph"),
        (1, 1, "Second paragraph"),
        (2, 2, "Third paragraph"),
    ]


@pytest.mark.parametrize(
    ("filename", "content_type", "content", "detail"),
    [
        ("   ", "application/pdf", make_pdf_with_text("Text"), "A PDF filename is required."),
        ("report.txt", "application/pdf", make_pdf_with_text("Text"), "Only PDF files are supported."),
        ("report.pdf", "text/plain", make_pdf_with_text("Text"), "Content type must be application/pdf."),
        ("report.pdf", "application/pdf", b"not a PDF", "Uploaded file is not a valid PDF."),
        ("report.pdf", "application/pdf", b"", "PDF file must not be empty."),
    ],
)
def test_invalid_filename_type_signature_and_empty_file_are_rejected(
    client,
    report_storage: Path,
    filename: str,
    content_type: str,
    content: bytes,
    detail: str,
) -> None:
    _user, token = register_and_login(client)

    response = upload(
        client,
        token=token,
        content=content,
        filename=filename,
        content_type=content_type,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == detail
    assert list(report_storage.glob("*.pdf")) == []


def test_oversized_file_is_rejected_while_streaming(client, report_storage: Path) -> None:
    _user, token = register_and_login(client)
    payload = b"%PDF-" + (b"x" * (10 * 1024 * 1024))

    response = upload(client, token=token, content=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == "Report file exceeds the maximum allowed size."
    assert list(report_storage.glob("*.pdf")) == []


@pytest.mark.parametrize(
    ("payload", "detail"),
    [
        (b"%PDF-not-a-real-document", "PDF file could not be read."),
        (make_encrypted_pdf(), "Encrypted PDF files are not supported."),
        (make_empty_text_pdf(), "PDF must contain extractable text."),
    ],
)
def test_unreadable_encrypted_and_unusable_pdfs_are_cleaned_up(
    client,
    report_storage: Path,
    payload: bytes,
    detail: str,
) -> None:
    _user, token = register_and_login(client)

    response = upload(client, token=token, content=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == detail
    assert list(report_storage.glob("*.pdf")) == []


def test_parser_failure_removes_stored_file(
    client,
    db_session: Session,
    report_storage: Path,
) -> None:
    _user, token = register_and_login(client)

    class FailingExtractor:
        def extract(self, _path: Path):
            raise PdfExtractionError("internal parser error")

    app.dependency_overrides[get_pdf_text_extractor] = FailingExtractor
    try:
        response = upload(client, token=token, content=make_pdf_with_text("Text"))
    finally:
        app.dependency_overrides.pop(get_pdf_text_extractor, None)

    assert response.status_code == 422
    assert response.json()["detail"] == "PDF file could not be read."
    assert list(report_storage.glob("*.pdf")) == []
    assert db_session.query(ReportDocument).count() == 0
    assert db_session.query(ReportChunk).count() == 0


def test_cleanup_retries_transient_unlink_failure_without_exposing_paths(
    client,
    report_storage: Path,
    monkeypatch,
) -> None:
    _user, token = register_and_login(client)
    original_unlink = Path.unlink
    unlink_attempts = 0

    def transient_unlink(path: Path, *args, **kwargs) -> None:
        nonlocal unlink_attempts
        if path.parent == report_storage and path.suffix == ".pdf":
            unlink_attempts += 1
            if unlink_attempts == 1:
                raise PermissionError(r"C:\private\reports\locked.pdf")
        return original_unlink(path, *args, **kwargs)

    class FailingExtractor:
        def extract(self, _path: Path):
            raise PdfExtractionError("internal parser error")

    monkeypatch.setattr(Path, "unlink", transient_unlink)
    app.dependency_overrides[get_pdf_text_extractor] = FailingExtractor
    try:
        response = upload(client, token=token, content=make_pdf_with_text("Text"))
    finally:
        app.dependency_overrides.pop(get_pdf_text_extractor, None)

    assert response.status_code == 422
    assert response.json()["detail"] == "PDF file could not be read."
    assert "C:\\private" not in response.text
    assert unlink_attempts == 2
    assert list(report_storage.glob("*.pdf")) == []


def test_cleanup_failure_returns_stable_error_without_exposing_paths(
    client,
    db_session: Session,
    report_storage: Path,
    monkeypatch,
) -> None:
    _user, token = register_and_login(client)
    original_unlink = Path.unlink

    def failing_unlink(path: Path, *args, **kwargs) -> None:
        if path.parent == report_storage and path.suffix == ".pdf":
            raise PermissionError(r"C:\private\reports\locked.pdf")
        return original_unlink(path, *args, **kwargs)

    class FailingExtractor:
        def extract(self, _path: Path):
            raise PdfExtractionError("internal parser error")

    monkeypatch.setattr(Path, "unlink", failing_unlink)
    app.dependency_overrides[get_pdf_text_extractor] = FailingExtractor
    try:
        response = upload(client, token=token, content=make_pdf_with_text("Text"))
    finally:
        app.dependency_overrides.pop(get_pdf_text_extractor, None)

    assert response.status_code == 500
    assert response.json()["detail"] == "Report upload could not be completed."
    assert "C:\\private" not in response.text
    assert db_session.query(ReportDocument).count() == 0
    assert db_session.query(ReportChunk).count() == 0
    assert len(list(report_storage.glob("*.pdf"))) == 1


def test_response_validation_failure_rolls_back_before_commit_and_removes_file(
    client,
    db_session: Session,
    report_storage: Path,
    monkeypatch,
) -> None:
    user, _token = register_and_login(client)
    current_user = db_session.get(User, user["id"])
    assert current_user is not None
    commit_called = False

    class InvalidResponseRepository(ReportRepository):
        def add_document_with_chunks(self, **kwargs):
            document = super().add_document_with_chunks(**kwargs)
            document.created_at = None
            return document

    def fail_if_committed() -> None:
        nonlocal commit_called
        commit_called = True
        raise AssertionError("Response validation must happen before commit.")

    monkeypatch.setattr(db_session, "commit", fail_if_committed)
    service = ReportUploadService(
        db=db_session,
        report_repository=InvalidResponseRepository(db_session),
        storage=LocalReportStorage(root=report_storage, max_file_size_bytes=10 * 1024 * 1024),
        pdf_text_extractor=PdfTextExtractor(),
    )

    with pytest.raises(HTTPException) as exc_info:
        service.upload_report(
            source=io.BytesIO(make_pdf_with_text("Text")),
            original_filename="report.pdf",
            content_type="application/pdf",
            current_user=current_user,
        )

    assert exc_info.value.status_code == 500
    assert commit_called is False
    assert db_session.query(ReportDocument).count() == 0
    assert db_session.query(ReportChunk).count() == 0
    assert list(report_storage.glob("*.pdf")) == []


def test_persistence_failure_rolls_back_partially_flushed_rows_and_removes_file(
    client,
    db_session: Session,
    report_storage: Path,
    monkeypatch,
) -> None:
    user, _token = register_and_login(client)
    current_user = db_session.get(User, user["id"])
    assert current_user is not None
    repository = ReportRepository(db_session)
    original_flush = db_session.flush
    flush_count = 0
    commit_called = False

    def fail_second_flush(*args, **kwargs) -> None:
        nonlocal flush_count
        flush_count += 1
        if flush_count == 2:
            raise SQLAlchemyError("chunk flush failed")
        original_flush(*args, **kwargs)

    def fail_if_committed() -> None:
        nonlocal commit_called
        commit_called = True
        raise AssertionError("Commit must not run after a chunk flush failure.")

    monkeypatch.setattr(db_session, "flush", fail_second_flush)
    monkeypatch.setattr(db_session, "commit", fail_if_committed)
    service = ReportUploadService(
        db=db_session,
        report_repository=repository,
        storage=LocalReportStorage(root=report_storage, max_file_size_bytes=10 * 1024 * 1024),
        pdf_text_extractor=PdfTextExtractor(),
    )

    with pytest.raises(HTTPException) as exc_info:
        service.upload_report(
            source=io.BytesIO(make_pdf_with_text("Text")),
            original_filename="report.pdf",
            content_type="application/pdf",
            current_user=current_user,
        )

    assert exc_info.value.status_code == 500
    assert flush_count == 2
    assert commit_called is False
    assert db_session.query(ReportDocument).count() == 0
    assert db_session.query(ReportChunk).count() == 0
    assert list(report_storage.glob("*.pdf")) == []


def test_repository_does_not_commit(db_session: Session, monkeypatch) -> None:
    user = User(
        email="report-repository-owner@example.com",
        username="report-repository-owner",
        hashed_password="hashed-password",
        preferred_currency="TRY",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    repository = ReportRepository(db_session)
    commit_called = False

    def fail_if_committed() -> None:
        nonlocal commit_called
        commit_called = True
        raise AssertionError("Repository must not commit.")

    monkeypatch.setattr(db_session, "commit", fail_if_committed)
    document = ReportDocument(
        user_id=user.id,
        original_filename="report.pdf",
        storage_key="a" * 32 + ".pdf",
        content_type="application/pdf",
        file_size_bytes=1,
        sha256="b" * 64,
        page_count=1,
    )
    chunk = ReportChunk(report_document_id=0, chunk_index=0, page_number=1, text="Text")

    repository.add_document_with_chunks(document=document, chunks=[chunk])

    assert commit_called is False
    assert document.id is not None
    assert chunk.report_document_id == document.id


def test_storage_key_collision_preserves_existing_file(report_storage: Path, monkeypatch) -> None:
    existing_key = "a" * 32 + ".pdf"
    existing_path = report_storage / existing_key
    report_storage.mkdir()
    existing_payload = b"existing report"
    existing_path.write_bytes(existing_payload)
    generated_keys = iter(["a" * 32, "b" * 32])

    monkeypatch.setattr(
        local_report_storage_module.uuid,
        "uuid4",
        lambda: SimpleNamespace(hex=next(generated_keys)),
    )
    storage = LocalReportStorage(root=report_storage, max_file_size_bytes=1024)

    stored = storage.save(io.BytesIO(b"%PDF-new report"))

    assert stored.storage_key == "b" * 32 + ".pdf"
    assert existing_path.read_bytes() == existing_payload
    assert (report_storage / stored.storage_key).read_bytes() == b"%PDF-new report"


def test_storage_keys_reject_traversal_and_client_filename_is_not_a_path(
    client,
    report_storage: Path,
) -> None:
    storage = LocalReportStorage(root=report_storage, max_file_size_bytes=1024)
    with pytest.raises(ReportStorageError):
        storage.cleanup("../outside.pdf")

    _user, token = register_and_login(client)
    response = upload(
        client,
        token=token,
        content=make_pdf_with_text("Text"),
        filename="../../outside.pdf",
    )

    assert response.status_code == 201
    assert not (report_storage.parent / "outside.pdf").exists()
    assert len(list(report_storage.glob("*.pdf"))) == 1


def test_upload_does_not_resolve_ai_client(client, report_storage: Path) -> None:
    _user, token = register_and_login(client)

    def fail_ai_client():
        raise AssertionError("AI client must not be resolved for report uploads")

    app.dependency_overrides[get_ai_client] = fail_ai_client
    try:
        response = upload(client, token=token, content=make_pdf_with_text("Text"))
    finally:
        app.dependency_overrides.pop(get_ai_client, None)

    assert response.status_code == 201


def test_report_models_and_migration_constraints_and_downgrade_order() -> None:
    document_table = ReportDocument.__table__
    chunk_table = ReportChunk.__table__

    assert document_table.c.storage_key.unique is True
    assert document_table.c.sha256.type.length == 64
    assert any(index.name == "ix_report_documents_user_created_id" for index in document_table.indexes)
    assert any(index.name == "ix_report_chunks_document_chunk_index" for index in chunk_table.indexes)
    assert any(
        constraint.name == "uq_report_chunks_document_chunk_index"
        for constraint in chunk_table.constraints
    )

    migration_text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "20260908_0024"' in migration_text
    assert 'down_revision = "20260907_0023"' in migration_text
    assert migration_text.index('"report_documents"') < migration_text.index('"report_chunks"')
    assert migration_text.index('op.drop_table("report_chunks")') < migration_text.index(
        'op.drop_table("report_documents")'
    )
