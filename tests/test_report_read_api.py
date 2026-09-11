from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy.orm import Session

from src.config.dependencies import get_ai_client, get_report_storage
from src.main import app
from src.model.report_chunk import ReportChunk
from src.model.report_document import ReportDocument
from src.repositories.report_repository import ReportRepository


AUTH_DETAIL = "Authentication credentials were not provided or are invalid."
PUBLIC_FIELDS = {
    "report_id",
    "original_filename",
    "content_type",
    "file_size_bytes",
    "page_count",
    "created_at",
}


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


def seed_report(
    db_session: Session,
    *,
    user_id: int,
    sequence: int,
    filename: str,
    created_at: datetime,
    add_chunk: bool = False,
) -> ReportDocument:
    report = ReportDocument(
        user_id=user_id,
        original_filename=filename,
        storage_key=f"{sequence:032x}.pdf",
        content_type="application/pdf",
        file_size_bytes=100 + sequence,
        sha256=f"{sequence:064x}",
        page_count=sequence + 1,
        created_at=created_at,
    )
    db_session.add(report)
    db_session.flush()
    if add_chunk:
        db_session.add(ReportChunk(report_document_id=report.id, chunk_index=0, page_number=1, text="secret chunk"))
    db_session.commit()
    db_session.refresh(report)
    return report


def test_report_library_list_and_detail_require_authentication(client) -> None:
    list_response = client.get("/api/v1/reports")
    detail_response = client.get("/api/v1/reports/1")

    assert list_response.status_code == 401
    assert list_response.json()["detail"] == AUTH_DETAIL
    assert detail_response.status_code == 401
    assert detail_response.json()["detail"] == AUTH_DETAIL


def test_report_library_list_is_user_scoped_ordered_paginated_and_public(client, db_session: Session) -> None:
    owner, token = register_and_login(client, email="report-list-owner@example.com", username="report-list-owner")
    other, _other_token = register_and_login(client, email="report-list-other@example.com", username="report-list-other")
    old = seed_report(
        db_session,
        user_id=owner["id"],
        sequence=1,
        filename="old.pdf",
        created_at=datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc),
    )
    first_same_time = seed_report(
        db_session,
        user_id=owner["id"],
        sequence=2,
        filename="first.pdf",
        created_at=datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc),
    )
    second_same_time = seed_report(
        db_session,
        user_id=owner["id"],
        sequence=3,
        filename="second.pdf",
        created_at=datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc),
    )
    seed_report(
        db_session,
        user_id=other["id"],
        sequence=4,
        filename="foreign.pdf",
        created_at=datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc),
    )

    response = client.get("/api/v1/reports?skip=1&limit=2", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["skip"] == 1
    assert body["limit"] == 2
    assert [item["report_id"] for item in body["items"]] == [first_same_time.id, old.id]
    assert second_same_time.id > first_same_time.id
    assert all(set(item) == PUBLIC_FIELDS for item in body["items"])
    assert all(
        {"user_id", "storage_key", "sha256", "path", "text", "chunk_count"}.isdisjoint(item)
        for item in body["items"]
    )


@pytest.mark.parametrize("query", ["skip=-1", "limit=0", "limit=101"])
def test_report_library_list_validates_pagination(client, query: str) -> None:
    _user, token = register_and_login(client, email=f"report-page-{query}@example.com", username=f"report-page-{query}")

    response = client.get(f"/api/v1/reports?{query}", headers=auth_headers(token))

    assert response.status_code == 422


def test_report_library_detail_is_owned_public_and_hides_internal_fields(client, db_session: Session) -> None:
    user, token = register_and_login(client, email="report-detail@example.com", username="report-detail")
    report = seed_report(
        db_session,
        user_id=user["id"],
        sequence=5,
        filename="owned.pdf",
        created_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
        add_chunk=True,
    )

    response = client.get(f"/api/v1/reports/{report.id}", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == PUBLIC_FIELDS
    assert body["report_id"] == report.id
    assert body["original_filename"] == "owned.pdf"
    assert {"user_id", "storage_key", "sha256", "path", "text", "chunk_count"}.isdisjoint(body)


def test_report_library_missing_and_foreign_reports_return_canonical_404(client, db_session: Session) -> None:
    owner, _owner_token = register_and_login(client, email="report-foreign-owner@example.com", username="report-foreign-owner")
    _other, token = register_and_login(client, email="report-foreign-other@example.com", username="report-foreign-other")
    report = seed_report(
        db_session,
        user_id=owner["id"],
        sequence=6,
        filename="foreign.pdf",
        created_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
    )

    foreign = client.get(f"/api/v1/reports/{report.id}", headers=auth_headers(token))
    missing = client.get("/api/v1/reports/999999", headers=auth_headers(token))

    assert foreign.status_code == 404
    assert foreign.json()["detail"] == "Report not found."
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Report not found."


def test_report_library_reads_do_not_resolve_ai_storage_or_chunks(client, db_session: Session, monkeypatch) -> None:
    user, token = register_and_login(client, email="report-read-side-effects@example.com", username="report-read-side-effects")
    report = seed_report(
        db_session,
        user_id=user["id"],
        sequence=7,
        filename="metadata-only.pdf",
        created_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
        add_chunk=True,
    )

    def fail_dependency():
        raise AssertionError("Read endpoints must not resolve this dependency.")

    def fail_chunk_access(self, *, report_document_id: int):
        raise AssertionError("Read endpoints must not load report chunks.")

    app.dependency_overrides[get_ai_client] = fail_dependency
    app.dependency_overrides[get_report_storage] = fail_dependency
    monkeypatch.setattr(ReportRepository, "list_chunks_by_document_id", fail_chunk_access)
    try:
        list_response = client.get("/api/v1/reports", headers=auth_headers(token))
        detail_response = client.get(f"/api/v1/reports/{report.id}", headers=auth_headers(token))
    finally:
        app.dependency_overrides.pop(get_ai_client, None)
        app.dependency_overrides.pop(get_report_storage, None)

    assert list_response.status_code == 200
    assert detail_response.status_code == 200


def test_report_library_read_repository_methods_do_not_commit(client, db_session: Session, monkeypatch) -> None:
    user, _token = register_and_login(client, email="report-read-repository@example.com", username="report-read-repository")
    report = seed_report(
        db_session,
        user_id=user["id"],
        sequence=8,
        filename="repository.pdf",
        created_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
    )
    repository = ReportRepository(db_session)
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)

    assert repository.get_document_by_id_for_user(report_id=report.id, user_id=user["id"]) is report
    assert repository.list_documents_by_user(user_id=user["id"], skip=0, limit=50) == [report]
    assert repository.count_documents_by_user(user_id=user["id"]) == 1
    assert commit_calls == 0
