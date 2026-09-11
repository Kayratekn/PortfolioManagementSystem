from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from src.config.dependencies import get_ai_client, get_report_storage
from src.integrations.local_report_storage import LocalReportStorage, ReportStorageError
from src.main import app
from src.model.report_chunk import ReportChunk
from src.model.report_document import ReportDocument
from src.repositories.report_repository import ReportRepository


AUTH_DETAIL = "Authentication credentials were not provided or are invalid."


def register_and_login(client, *, email: str, username: str) -> tuple[dict[str, Any], str]:
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "StrongPass123",
            "preferred_currency": "TRY",
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    assert login.status_code == 200
    return registration.json(), login.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def download_url(report_id: int) -> str:
    return f"/api/v1/reports/{report_id}/download"


@pytest.fixture()
def report_storage(tmp_path: Path, client) -> Path:
    root = tmp_path / "reports"
    app.dependency_overrides[get_report_storage] = lambda: LocalReportStorage(
        root=root,
        max_file_size_bytes=10 * 1024 * 1024,
    )
    yield root
    app.dependency_overrides.pop(get_report_storage, None)


def seed_report(
    db_session: Session,
    *,
    user_id: int,
    storage_key: str,
    filename: str = "Quarterly Report.pdf",
    add_chunk: bool = False,
) -> ReportDocument:
    report = ReportDocument(
        user_id=user_id,
        original_filename=filename,
        storage_key=storage_key,
        content_type="application/pdf",
        file_size_bytes=12,
        sha256="a" * 64,
        page_count=1,
        created_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
    )
    db_session.add(report)
    db_session.flush()
    if add_chunk:
        db_session.add(ReportChunk(report_document_id=report.id, chunk_index=0, page_number=1, text="secret chunk"))
    db_session.commit()
    db_session.refresh(report)
    return report


def write_stored_file(root: Path, storage_key: str, content: bytes) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / storage_key).write_bytes(content)


def test_report_download_requires_authentication(client) -> None:
    response = client.get(download_url(1))

    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_DETAIL


def test_owner_downloads_exact_pdf_bytes_with_original_filename(
    client,
    db_session: Session,
    report_storage: Path,
) -> None:
    user, token = register_and_login(client, email="download-owner@example.com", username="download-owner")
    storage_key = "a" * 32 + ".pdf"
    payload = b"%PDF-owner-report"
    report = seed_report(db_session, user_id=user["id"], storage_key=storage_key)
    write_stored_file(report_storage, storage_key, payload)

    response = client.get(download_url(report.id), headers=auth_headers(token))

    assert response.status_code == 200
    assert response.content == payload
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == "attachment; filename*=UTF-8''Quarterly%20Report.pdf"
    assert {"storage_key", "sha256", "secret chunk"}.isdisjoint(response.headers.values())


def test_foreign_and_missing_reports_are_indistinguishable_without_storage_access(
    client,
    db_session: Session,
) -> None:
    owner, _owner_token = register_and_login(client, email="download-foreign-owner@example.com", username="download-foreign-owner")
    _other, token = register_and_login(client, email="download-foreign-other@example.com", username="download-foreign-other")
    report = seed_report(db_session, user_id=owner["id"], storage_key="b" * 32 + ".pdf")

    class SpyStorage:
        def __init__(self) -> None:
            self.keys: list[str] = []

        def read_bytes(self, storage_key: str) -> bytes:
            self.keys.append(storage_key)
            raise AssertionError("Storage must not be accessed before ownership succeeds.")

    storage = SpyStorage()
    app.dependency_overrides[get_report_storage] = lambda: storage
    try:
        foreign = client.get(download_url(report.id), headers=auth_headers(token))
        missing = client.get(download_url(999999), headers=auth_headers(token))
    finally:
        app.dependency_overrides.pop(get_report_storage, None)

    assert foreign.status_code == 404
    assert foreign.json()["detail"] == "Report not found."
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Report not found."
    assert storage.keys == []


def test_missing_stored_file_returns_stable_500(client, db_session: Session, report_storage: Path) -> None:
    user, token = register_and_login(client, email="download-missing-file@example.com", username="download-missing-file")
    report = seed_report(db_session, user_id=user["id"], storage_key="c" * 32 + ".pdf")

    response = client.get(download_url(report.id), headers=auth_headers(token))

    assert response.status_code == 500
    assert response.json()["detail"] == "Report file is unavailable."
    assert str(report_storage) not in response.text


def test_storage_error_returns_stable_500_without_path_leakage(client, db_session: Session) -> None:
    user, token = register_and_login(client, email="download-storage-error@example.com", username="download-storage-error")
    report = seed_report(db_session, user_id=user["id"], storage_key="d" * 32 + ".pdf")

    class FailingStorage:
        def read_bytes(self, _storage_key: str) -> bytes:
            raise ReportStorageError(r"C:\private\reports\locked.pdf")

    app.dependency_overrides[get_report_storage] = FailingStorage
    try:
        response = client.get(download_url(report.id), headers=auth_headers(token))
    finally:
        app.dependency_overrides.pop(get_report_storage, None)

    assert response.status_code == 500
    assert response.json()["detail"] == "Report file is unavailable."
    assert "C:\\private" not in response.text


def test_invalid_storage_key_cannot_escape_storage_root(client, db_session: Session, report_storage: Path) -> None:
    user, token = register_and_login(client, email="download-traversal@example.com", username="download-traversal")
    outside_file = report_storage.parent / "outside.pdf"
    outside_file.write_bytes(b"outside")
    report = seed_report(db_session, user_id=user["id"], storage_key="../outside.pdf")

    response = client.get(download_url(report.id), headers=auth_headers(token))

    assert response.status_code == 500
    assert response.json()["detail"] == "Report file is unavailable."
    assert outside_file.read_bytes() == b"outside"
    assert str(outside_file) not in response.text


def test_download_does_not_resolve_ai_or_load_chunks(client, db_session: Session, report_storage: Path, monkeypatch) -> None:
    user, token = register_and_login(client, email="download-no-side-effects@example.com", username="download-no-side-effects")
    storage_key = "e" * 32 + ".pdf"
    report = seed_report(db_session, user_id=user["id"], storage_key=storage_key, add_chunk=True)
    write_stored_file(report_storage, storage_key, b"%PDF-side-effects")

    def fail_ai_client():
        raise AssertionError("Download must not resolve the AI client.")

    def fail_chunk_access(self, *, report_document_id: int):
        raise AssertionError("Download must not load chunks.")

    app.dependency_overrides[get_ai_client] = fail_ai_client
    monkeypatch.setattr(ReportRepository, "list_chunks_by_document_id", fail_chunk_access)
    try:
        response = client.get(download_url(report.id), headers=auth_headers(token))
    finally:
        app.dependency_overrides.pop(get_ai_client, None)

    assert response.status_code == 200
    assert response.content == b"%PDF-side-effects"
