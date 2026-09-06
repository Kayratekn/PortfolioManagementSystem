from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.model.data_sync_run import DataSyncRun
from src.services.data_sync_run_service import SYNC_TYPE_BENCHMARK_DAILY, SYNC_TYPE_TEFAS_DAILY


def register_user(client, *, email: str = "sync-status@example.com", username: str = "sync-status") -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "StrongPass123",
            "preferred_currency": "TRY",
        },
    )
    assert response.status_code == 201


def login_user(client, *, email: str = "sync-status@example.com") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def add_run(
    db_session: Session,
    *,
    sync_type: str,
    status: str,
    started_at: datetime,
    completed_at: datetime | None = None,
    error_message: str | None = None,
) -> DataSyncRun:
    run = DataSyncRun(
        sync_type=sync_type,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        error_message=error_message,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


def test_data_sync_status_requires_authentication(client) -> None:
    response = client.get("/api/v1/data-sync/status")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication credentials were not provided or are invalid."


def test_data_sync_status_returns_authenticated_latest_runs_in_order_and_public_fields(
    client,
    db_session: Session,
) -> None:
    register_user(client)
    token = login_user(client)
    completed_at = datetime(2026, 9, 7, 8, 5, tzinfo=timezone.utc)
    add_run(
        db_session,
        sync_type=SYNC_TYPE_TEFAS_DAILY,
        status="SUCCESS",
        started_at=datetime(2026, 9, 7, 7, 0, tzinfo=timezone.utc),
        completed_at=completed_at,
    )
    latest_tefas = add_run(
        db_session,
        sync_type=SYNC_TYPE_TEFAS_DAILY,
        status="RUNNING",
        started_at=datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc),
    )
    latest_benchmark = add_run(
        db_session,
        sync_type=SYNC_TYPE_BENCHMARK_DAILY,
        status="FAILED",
        started_at=datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc),
        completed_at=completed_at,
        error_message="One or more benchmark syncs failed.",
    )

    response = client.get("/api/v1/data-sync/status", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [latest_tefas.id, latest_benchmark.id]
    assert [item["sync_type"] for item in body["items"]] == [SYNC_TYPE_TEFAS_DAILY, SYNC_TYPE_BENCHMARK_DAILY]
    assert set(body["items"][0]) == {
        "id",
        "sync_type",
        "status",
        "started_at",
        "completed_at",
        "error_message",
    }
    assert "created_at" not in body["items"][0]
    assert "updated_at" not in body["items"][0]


def test_data_sync_status_no_run_returns_empty_items(client) -> None:
    register_user(client, email="sync-empty@example.com", username="sync-empty")
    token = login_user(client, email="sync-empty@example.com")

    response = client.get("/api/v1/data-sync/status", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}
