from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.dependencies import get_ai_client
from src.integrations.ai_client import (
    AiServiceRequestError,
    AiServiceResponseError,
    AiServiceUnavailableError,
)
from src.main import app
from src.model.ai_analysis import AiAnalysis
from src.model.report_chunk import ReportChunk
from src.model.report_document import ReportDocument
from src.repositories.report_repository import ReportRepository


AUTH_DETAIL = "Authentication credentials were not provided or are invalid."


def create_user_and_token(client, *, email: str, username: str) -> tuple[dict[str, Any], str]:
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


def question_url(report_id: int) -> str:
    return f"/api/v1/reports/{report_id}/questions"


def seed_report(
    db_session: Session,
    *,
    user_id: int,
    filename: str = "owner-report.pdf",
    chunks: list[tuple[int, int, str]] | None = None,
) -> tuple[ReportDocument, list[ReportChunk]]:
    document = ReportDocument(
        user_id=user_id,
        original_filename=filename,
        storage_key=f"{user_id:032x}.pdf",
        content_type="application/pdf",
        file_size_bytes=123,
        sha256="a" * 64,
        page_count=2,
    )
    db_session.add(document)
    db_session.flush()
    persisted_chunks = [
        ReportChunk(
            report_document_id=document.id,
            chunk_index=chunk_index,
            page_number=page_number,
            text=text,
        )
        for chunk_index, page_number, text in (chunks if chunks is not None else [(0, 1, "First")])
    ]
    db_session.add_all(persisted_chunks)
    db_session.commit()
    db_session.refresh(document)
    for chunk in persisted_chunks:
        db_session.refresh(chunk)
    return document, persisted_chunks


class FakeAiClient:
    def __init__(self, response: dict[str, Any] | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((endpoint, payload))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def valid_ai_response(**overrides: Any) -> dict[str, Any]:
    response = {
        "answer": " The report supports the allocation. ",
        "citations": [{"report_id": 1, "chunk_id": 1, "page_number": 1, "report_name": "owner-report.pdf"}],
        "confidence_score": "0.85",
        "suggested_followups": [" Ask about risk. "],
        "disclaimer": " Educational information only. ",
        "model_version": " report-qa-v1 ",
        "formula_version": None,
        "internal_prompt": "must not leave the AI response boundary",
    }
    response.update(overrides)
    return response


def with_ai_client(client, fake: FakeAiClient):
    app.dependency_overrides[get_ai_client] = lambda: fake
    return fake


def clear_ai_client_override() -> None:
    app.dependency_overrides.pop(get_ai_client, None)


def test_report_qa_requires_authentication(client) -> None:
    response = client.post(question_url(1), json={"query": "What changed?"})

    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_DETAIL


def test_valid_report_question_uses_exact_persisted_context_and_persists_analysis(
    client,
    db_session: Session,
) -> None:
    user, token = create_user_and_token(client, email="qa-owner@example.com", username="qa-owner")
    report, chunks = seed_report(
        db_session,
        user_id=user["id"],
        filename="Quarterly Report.pdf",
        chunks=[(1, 2, "Second persisted chunk"), (0, 1, "First persisted chunk")],
    )
    fake = with_ai_client(
        client,
        FakeAiClient(
            valid_ai_response(
                citations=[
                    {
                        "report_id": report.id,
                        "chunk_id": chunks[1].id,
                        "page_number": chunks[1].page_number,
                        "report_name": report.original_filename,
                    }
                ]
            )
        ),
    )
    try:
        response = client.post(
            question_url(report.id),
            headers=auth_headers(token),
            json={"query": "  What does the report say?  "},
        )
    finally:
        clear_ai_client_override()

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "analysis_id", "report_id", "answer", "citations", "confidence_score",
        "suggested_followups", "disclaimer", "model_version", "formula_version",
    }
    assert body["report_id"] == report.id
    assert body["answer"] == "The report supports the allocation."
    assert body["suggested_followups"] == ["Ask about risk."]
    assert body["disclaimer"] == "Educational information only."
    assert body["model_version"] == "report-qa-v1"
    assert body["formula_version"] is None
    assert body["citations"] == [
        {
            "report_id": report.id,
            "chunk_id": chunks[1].id,
            "page_number": 1,
            "report_name": "Quarterly Report.pdf",
        }
    ]
    assert set(body["citations"][0]) == {"report_id", "chunk_id", "page_number", "report_name"}
    assert {"user_id", "text", "storage_key", "sha256", "internal_prompt"}.isdisjoint(body)

    assert len(fake.calls) == 1
    endpoint, payload = fake.calls[0]
    assert endpoint == "/api/ai/report-qa"
    assert payload == {
        "user_id": user["id"],
        "query": "What does the report say?",
        "report_ids": [report.id],
        "report_chunks": [
            {
                "report_id": report.id,
                "report_name": "Quarterly Report.pdf",
                "chunk_id": chunks[1].id,
                "page_number": 1,
                "text": "First persisted chunk",
            },
            {
                "report_id": report.id,
                "report_name": "Quarterly Report.pdf",
                "chunk_id": chunks[0].id,
                "page_number": 2,
                "text": "Second persisted chunk",
            },
        ],
    }
    analysis = db_session.get(AiAnalysis, body["analysis_id"])
    assert analysis is not None
    assert analysis.user_id == user["id"]
    assert analysis.portfolio_id is None
    assert analysis.analysis_type == "report-qa"
    assert analysis.result_payload == {
        "report_id": report.id,
        "citations": [{"report_id": report.id, "chunk_id": chunks[1].id, "page_number": 1, "report_name": "Quarterly Report.pdf"}],
        "confidence_score": "0.85",
        "suggested_followups": ["Ask about risk."],
    }
    assert set(analysis.result_payload["citations"][0]) == {
        "report_id", "chunk_id", "page_number", "report_name"
    }
    assert analysis.explanation_text == "The report supports the allocation."
    assert analysis.disclaimer == "Educational information only."
    assert analysis.model_version == "report-qa-v1"
    assert analysis.formula_version is None
    assert "What does the report say?" not in str(analysis.result_payload)
    assert "persisted chunk" not in str(analysis.result_payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "ok", "user_id": 999},
        {"query": "ok", "report_ids": [1]},
        {"query": "ok", "report_name": "x"},
        {"query": "ok", "chunks": []},
        {"query": "ok", "model_version": "x"},
        {"query": 1},
    ],
)
def test_question_request_rejects_backend_owned_or_non_string_fields(client, payload: dict[str, Any]) -> None:
    _user, token = create_user_and_token(client, email=f"qa-request-{len(payload)}@example.com", username=f"qa-request-{len(payload)}")

    response = client.post(question_url(1), headers=auth_headers(token), json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize("query", ["   ", " " * 2001])
def test_question_request_rejects_blank_or_too_long_normalized_query(client, query: str) -> None:
    _user, token = create_user_and_token(client, email=f"qa-query-{len(query)}@example.com", username=f"qa-query-{len(query)}")

    response = client.post(question_url(1), headers=auth_headers(token), json={"query": query})

    assert response.status_code == 422


def test_missing_and_foreign_reports_are_indistinguishable_and_do_not_access_chunks_or_ai(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    owner, _owner_token = create_user_and_token(client, email="qa-foreign-owner@example.com", username="qa-foreign-owner")
    _other, token = create_user_and_token(client, email="qa-foreign-other@example.com", username="qa-foreign-other")
    report, _chunks = seed_report(db_session, user_id=owner["id"])
    fake = with_ai_client(client, FakeAiClient(valid_ai_response()))

    def fail_chunk_access(self, *, report_document_id: int):
        raise AssertionError("Chunk access must follow ownership verification.")

    monkeypatch.setattr(ReportRepository, "list_chunks_by_document_id", fail_chunk_access)
    try:
        foreign = client.post(question_url(report.id), headers=auth_headers(token), json={"query": "Question"})
        missing = client.post(question_url(999999), headers=auth_headers(token), json={"query": "Question"})
    finally:
        clear_ai_client_override()

    assert foreign.status_code == 404
    assert foreign.json()["detail"] == "Report not found."
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Report not found."
    assert fake.calls == []
    assert db_session.query(AiAnalysis).count() == 0


def test_empty_owned_report_returns_422_without_calling_ai(client, db_session: Session) -> None:
    user, token = create_user_and_token(client, email="qa-empty@example.com", username="qa-empty")
    report, _chunks = seed_report(db_session, user_id=user["id"], chunks=[])
    fake = with_ai_client(client, FakeAiClient(valid_ai_response()))
    try:
        response = client.post(question_url(report.id), headers=auth_headers(token), json={"query": "Question"})
    finally:
        clear_ai_client_override()

    assert response.status_code == 422
    assert response.json()["detail"] == "Report has no content available for Q&A."
    assert fake.calls == []
    assert db_session.query(AiAnalysis).count() == 0


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (AiServiceUnavailableError("unavailable"), 503, "AI service temporarily unavailable."),
        (AiServiceRequestError("rejected", status_code=400), 502, "AI service rejected the backend request."),
        (AiServiceResponseError("bad response"), 502, "AI service returned an invalid response."),
    ],
)
def test_ai_client_errors_are_mapped_without_persistence(
    client,
    db_session: Session,
    error: Exception,
    status_code: int,
    detail: str,
) -> None:
    user, token = create_user_and_token(client, email=f"qa-error-{status_code}@example.com", username=f"qa-error-{status_code}")
    report, _chunks = seed_report(db_session, user_id=user["id"])
    fake = with_ai_client(client, FakeAiClient(error))
    try:
        response = client.post(question_url(report.id), headers=auth_headers(token), json={"query": "Question"})
    finally:
        clear_ai_client_override()

    assert response.status_code == status_code
    assert response.json()["detail"] == detail
    assert db_session.query(AiAnalysis).count() == 0


@pytest.mark.parametrize(
    "invalid_response",
    [
        {},
        valid_ai_response(answer=" "),
        valid_ai_response(disclaimer=" "),
        valid_ai_response(model_version=" "),
        valid_ai_response(suggested_followups=[" "]),
        valid_ai_response(formula_version="formula-v1"),
        valid_ai_response(confidence_score="NaN"),
    ],
)
def test_invalid_ai_responses_are_rejected_without_persistence(
    client,
    db_session: Session,
    invalid_response: dict[str, Any],
) -> None:
    user, token = create_user_and_token(client, email=f"qa-invalid-{id(invalid_response)}@example.com", username=f"qa-invalid-{id(invalid_response)}")
    report, _chunks = seed_report(db_session, user_id=user["id"])
    fake = with_ai_client(client, FakeAiClient(invalid_response))
    try:
        response = client.post(question_url(report.id), headers=auth_headers(token), json={"query": "Question"})
    finally:
        clear_ai_client_override()

    assert response.status_code == 502
    assert response.json()["detail"] == "AI service returned an invalid response."
    assert db_session.query(AiAnalysis).count() == 0


def test_repeated_questions_append_immutable_analyses(client, db_session: Session) -> None:
    user, token = create_user_and_token(client, email="qa-repeat@example.com", username="qa-repeat")
    report, _chunks = seed_report(db_session, user_id=user["id"])
    fake = with_ai_client(client, FakeAiClient(valid_ai_response()))
    try:
        first = client.post(question_url(report.id), headers=auth_headers(token), json={"query": "First?"})
        second = client.post(question_url(report.id), headers=auth_headers(token), json={"query": "Second?"})
    finally:
        clear_ai_client_override()

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["analysis_id"] != second.json()["analysis_id"]
    analyses = list(db_session.scalars(select(AiAnalysis).order_by(AiAnalysis.id)))
    assert len(analyses) == 2
    assert all(analysis.analysis_type == "report-qa" for analysis in analyses)


def test_report_repository_user_scoped_lookup_isolates_foreign_document(client, db_session: Session) -> None:
    owner, _owner_token = create_user_and_token(client, email="qa-repository-owner@example.com", username="qa-repository-owner")
    other, _other_token = create_user_and_token(client, email="qa-repository-other@example.com", username="qa-repository-other")
    report, _chunks = seed_report(db_session, user_id=owner["id"])
    repository = ReportRepository(db_session)

    assert repository.get_document_by_id_for_user(report_id=report.id, user_id=owner["id"]) == report
    assert repository.get_document_by_id_for_user(report_id=report.id, user_id=other["id"]) is None


@pytest.mark.parametrize(
    "citation_updates",
    [
        {"text": "raw chunk text"},
        {"snippet": "excerpt"},
        {"storage_path": "C:/reports/secret.pdf"},
        {"report_id": 999999},
        {"chunk_id": 999999},
        {"page_number": 2},
        {"report_name": "different-report.pdf"},
        {"report_id": 0},
        {"chunk_id": 0},
        {"page_number": 0},
        {"report_name": "   "},
    ],
)
def test_invalid_or_ungrounded_citations_are_rejected_without_persistence(
    client,
    db_session: Session,
    citation_updates: dict[str, Any],
) -> None:
    user, token = create_user_and_token(
        client,
        email=f"qa-citation-{id(citation_updates)}@example.com",
        username=f"qa-citation-{id(citation_updates)}",
    )
    report, chunks = seed_report(db_session, user_id=user["id"])
    citation = {
        "report_id": report.id,
        "chunk_id": chunks[0].id,
        "page_number": chunks[0].page_number,
        "report_name": report.original_filename,
    }
    citation.update(citation_updates)
    fake = with_ai_client(client, FakeAiClient(valid_ai_response(citations=[citation])))
    try:
        response = client.post(
            question_url(report.id),
            headers=auth_headers(token),
            json={"query": "Question"},
        )
    finally:
        clear_ai_client_override()

    assert response.status_code == 502
    assert response.json()["detail"] == "AI service returned an invalid response."
    assert db_session.query(AiAnalysis).count() == 0

@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("report_id", "1"),
        ("report_id", 1.0),
        ("report_id", True),
        ("chunk_id", "1"),
        ("chunk_id", 1.0),
        ("chunk_id", True),
        ("page_number", "1"),
        ("page_number", 1.0),
        ("page_number", True),
    ],
)
def test_citation_integer_fields_reject_coercive_values_without_persistence(
    client,
    db_session: Session,
    field_name: str,
    invalid_value: Any,
) -> None:
    user, token = create_user_and_token(
        client,
        email=f"qa-strict-citation-{field_name}-{id(invalid_value)}@example.com",
        username=f"qa-strict-citation-{field_name}-{id(invalid_value)}",
    )
    report, chunks = seed_report(db_session, user_id=user["id"])
    citation = {
        "report_id": report.id,
        "chunk_id": chunks[0].id,
        "page_number": chunks[0].page_number,
        "report_name": report.original_filename,
    }
    citation[field_name] = invalid_value
    fake = with_ai_client(client, FakeAiClient(valid_ai_response(citations=[citation])))
    try:
        response = client.post(
            question_url(report.id),
            headers=auth_headers(token),
            json={"query": "Question"},
        )
    finally:
        clear_ai_client_override()

    assert response.status_code == 502
    assert response.json()["detail"] == "AI service returned an invalid response."
    assert db_session.query(AiAnalysis).count() == 0