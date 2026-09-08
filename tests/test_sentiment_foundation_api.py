from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.main import app
from src.model.expert_source import ExpertSource
from src.model.sentiment_post import SentimentPost
from src.model.user_expert_source import UserExpertSource
from src.model.user import User
from src.repositories.user_expert_source_repository import UserExpertSourceRepository


AUTH_DETAIL = "Authentication credentials were not provided or are invalid."
MIGRATION = Path("alembic/versions/20260908_0025_create_sentiment_foundation.py")


def register_login(client, email: str, username: str):
    registered = client.post("/api/v1/auth/register", json={"email": email, "username": username, "password": "StrongPass123", "preferred_currency": "TRY"})
    assert registered.status_code == 201
    logged_in = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"})
    assert logged_in.status_code == 200
    return registered.json(), logged_in.json()["access_token"]


def headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def source(db: Session, handle: str, *, active: bool = True, source_key: str = "X") -> ExpertSource:
    row = ExpertSource(source_key=source_key, author_name=f"{handle} name", author_handle=handle, profile_url=f"https://x.example/{handle}", is_active=active)
    db.add(row); db.commit(); db.refresh(row)
    return row


def post(db: Session, source_row: ExpertSource, *, external_id: str | None = "post", canonical_url: str | None = None, published_at: datetime | None = None) -> SentimentPost:
    row = SentimentPost(expert_source_id=source_row.id, source_key=source_row.source_key, external_id=external_id, url="https://x.example/post", canonical_url=canonical_url, title="Title", content="Persisted source content", author_name=source_row.author_name, author_handle=source_row.author_handle, published_at=published_at or datetime(2026, 9, 8, tzinfo=timezone.utc), fetched_at=datetime(2026, 9, 8, tzinfo=timezone.utc), content_type="SOCIAL", language="en")
    db.add(row); db.commit(); db.refresh(row)
    return row


def follow(client, token: str, expert_source_id: int):
    return client.post("/api/v1/user-expert-sources", headers=headers(token), json={"expert_source_id": expert_source_id})


def test_models_migration_and_nonblank_duplicate_constraints(db_session: Session) -> None:
    assert ExpertSource.__table__.c.is_active.server_default is not None
    assert UserExpertSource.__table__.c.is_enabled.server_default is not None
    assert {"expert_sources", "user_expert_sources", "sentiment_posts"}.issubset(app.state.__class__.__mro__[0].__dict__) is False
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "20260908_0025"' in text and 'down_revision = "20260908_0024"' in text
    assert text.index('"expert_sources"') < text.index('"user_expert_sources"') < text.index('"sentiment_posts"')
    assert text.index('op.drop_table("sentiment_posts")') < text.index('op.drop_table("user_expert_sources")') < text.index('op.drop_table("expert_sources")')
    assert 'uq_expert_sources_id_source_key' in text
    assert 'fk_sentiment_posts_expert_source_source_key' in text
    first = source(db_session, "first")
    db_session.add(ExpertSource(source_key="X", author_handle="first"))
    with pytest.raises(IntegrityError): db_session.commit()
    db_session.rollback()
    db_session.add(ExpertSource(source_key="X", author_handle="   "))
    with pytest.raises(IntegrityError): db_session.commit()
    db_session.rollback()
    assert first.id is not None


def test_expert_catalog_auth_active_ordering_and_pagination(client, db_session: Session) -> None:
    _user, token = register_login(client, "catalog@example.com", "catalog")
    source(db_session, "zeta", source_key="X")
    alpha = source(db_session, "alpha", source_key="A")
    source(db_session, "hidden", active=False)
    response = client.get("/api/v1/expert-sources?skip=0&limit=1", headers=headers(token))
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["items"][0]["expert_source_id"] == alpha.id
    assert set(response.json()["items"][0]) == {"expert_source_id", "source_key", "author_name", "author_handle", "profile_url"}
    assert client.get("/api/v1/expert-sources").status_code == 401


def test_user_expert_source_create_list_patch_and_ownership(client, db_session: Session) -> None:
    user, token = register_login(client, "follow@example.com", "follow")
    other, other_token = register_login(client, "other@example.com", "other")
    active = source(db_session, "active")
    inactive = source(db_session, "inactive", active=False)
    created = follow(client, token, active.id)
    assert created.status_code == 201
    body = created.json()
    assert body["expert_source_id"] == active.id and body["is_enabled"] is True and "user_id" not in body
    assert db_session.get(UserExpertSource, body["user_expert_source_id"]).user_id == user["id"]
    assert follow(client, token, active.id).status_code == 409
    assert follow(client, other_token, active.id).status_code == 201
    assert follow(client, token, inactive.id).json()["detail"] == "Expert source not found."
    listed = client.get("/api/v1/user-expert-sources", headers=headers(token)).json()
    assert listed["total"] == 1 and len(listed["items"]) == 1
    missing = client.patch("/api/v1/user-expert-sources/999", headers=headers(token), json={"is_enabled": False})
    foreign = client.patch(f"/api/v1/user-expert-sources/{body['user_expert_source_id']}", headers=headers(other_token), json={"is_enabled": False})
    assert missing.json()["detail"] == foreign.json()["detail"] == "User expert source not found."
    assert client.patch(f"/api/v1/user-expert-sources/{body['user_expert_source_id']}", headers=headers(token), json={"is_enabled": False}).json()["is_enabled"] is False
    db_session.get(ExpertSource, active.id).is_active = False; db_session.commit()
    failed_enable = client.patch(f"/api/v1/user-expert-sources/{body['user_expert_source_id']}", headers=headers(token), json={"is_enabled": True})
    assert failed_enable.status_code == 404 and failed_enable.json()["detail"] == "Expert source not found."
    assert other["id"] != user["id"]


@pytest.mark.parametrize("payload", [{"expert_source_id": "1"}, {"expert_source_id": True}, {"expert_source_id": 1, "user_id": 1}, {"is_enabled": "true"}, {"is_enabled": 1}, {"is_enabled": True, "user_id": 1}])
def test_user_expert_source_requests_are_strict(client, payload) -> None:
    _user, token = register_login(client, f"strict{len(payload)}@example.com", f"strict{len(payload)}")
    url = "/api/v1/user-expert-sources" if "expert_source_id" in payload else "/api/v1/user-expert-sources/1"
    assert client.post(url, headers=headers(token), json=payload).status_code == 422 if "expert_source_id" in payload else client.patch(url, headers=headers(token), json=payload).status_code == 422


def test_sentiment_post_duplicate_constraints_and_feed_visibility(client, db_session: Session) -> None:
    user, token = register_login(client, "feed@example.com", "feed")
    other, other_token = register_login(client, "feedother@example.com", "feedother")
    visible = source(db_session, "visible")
    disabled = source(db_session, "disabled")
    inactive = source(db_session, "inactivefeed", active=False)
    older = post(db_session, visible, external_id="same", published_at=datetime(2026, 9, 7, tzinfo=timezone.utc))
    newer = post(db_session, visible, external_id="new", published_at=datetime(2026, 9, 8, tzinfo=timezone.utc))
    post(db_session, disabled, external_id="disabled")
    post(db_session, inactive, external_id="inactive")
    follow(client, token, visible.id)
    disabled_follow = follow(client, token, disabled.id).json()
    client.patch(f"/api/v1/user-expert-sources/{disabled_follow['user_expert_source_id']}", headers=headers(token), json={"is_enabled": False})
    follow(client, other_token, inactive.id)
    db_session.add(SentimentPost(expert_source_id=visible.id, source_key="X", external_id="same", content="duplicate", published_at=datetime.now(timezone.utc), fetched_at=datetime.now(timezone.utc), content_type="SOCIAL", language="en"))
    with pytest.raises(IntegrityError): db_session.commit()
    db_session.rollback()
    fallback = post(db_session, disabled, external_id=None, canonical_url="https://canonical.example/a")
    db_session.add(SentimentPost(expert_source_id=disabled.id, source_key="X", external_id=None, canonical_url="https://canonical.example/a", content="duplicate", published_at=datetime.now(timezone.utc), fetched_at=datetime.now(timezone.utc), content_type="SOCIAL", language="en"))
    with pytest.raises(IntegrityError): db_session.commit()
    db_session.rollback()
    response = client.get("/api/v1/sentiment/posts?skip=0&limit=50", headers=headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2 and [item["post_id"] for item in body["items"]] == [newer.id, older.id]
    assert set(body["items"][0]) == {"post_id", "expert_source_id", "source_key", "title", "content", "author_name", "author_handle", "url", "published_at", "fetched_at", "content_type", "language"}
    assert {"external_id", "canonical_url", "user_id"}.isdisjoint(body["items"][0])
    assert client.get("/api/v1/sentiment/posts").status_code == 401
    assert fallback.id is not None and other["id"] != user["id"]


def test_repositories_flush_without_commit(db_session: Session, monkeypatch) -> None:
    user = User(email="repository@example.com", username="repository", hashed_password="hashed", preferred_currency="TRY", is_active=True)
    expert = ExpertSource(source_key="X", author_handle="repository-source", is_active=True)
    db_session.add_all([user, expert])
    db_session.flush()
    calls = 0

    def commit():
        nonlocal calls
        calls += 1
        raise AssertionError("Repository must not commit.")

    monkeypatch.setattr(db_session, "commit", commit)
    relation = UserExpertSourceRepository(db_session).add(UserExpertSource(user_id=user.id, expert_source_id=expert.id))

    assert relation.id is not None
    assert calls == 0

def test_user_expert_source_endpoints_require_authentication(client) -> None:
    responses = [
        client.get("/api/v1/user-expert-sources"),
        client.post("/api/v1/user-expert-sources", json={"expert_source_id": 1}),
        client.patch("/api/v1/user-expert-sources/1", json={"is_enabled": False}),
    ]
    assert all(response.status_code == 401 for response in responses)
    assert all(response.json()["detail"] == AUTH_DETAIL for response in responses)


def test_sentiment_post_identity_and_content_constraints(db_session: Session) -> None:
    db_session.execute(text("PRAGMA foreign_keys=ON"))
    first = source(db_session, "identity-one", source_key="X")
    second = source(db_session, "identity-two", source_key="Y")
    post(db_session, first, external_id="shared")
    post(db_session, second, external_id="shared")
    db_session.add(SentimentPost(expert_source_id=first.id, source_key="RSS", external_id="mismatched-source", content="mismatch", published_at=datetime.now(timezone.utc), fetched_at=datetime.now(timezone.utc), content_type="SOCIAL", language="en"))
    with pytest.raises(IntegrityError): db_session.commit()
    db_session.rollback()
    db_session.add(SentimentPost(expert_source_id=first.id, source_key="X", external_id=None, canonical_url=None, content="no identity", published_at=datetime.now(timezone.utc), fetched_at=datetime.now(timezone.utc), content_type="SOCIAL", language="en"))
    with pytest.raises(IntegrityError): db_session.commit()
    db_session.rollback()
    db_session.add(SentimentPost(expert_source_id=first.id, source_key="X", external_id="invalid-type", content="invalid", published_at=datetime.now(timezone.utc), fetched_at=datetime.now(timezone.utc), content_type="VIDEO", language="en"))
    with pytest.raises(IntegrityError): db_session.commit()
    db_session.rollback()
    db_session.add(SentimentPost(expert_source_id=first.id, source_key="X", external_id="blank-content", content="   ", published_at=datetime.now(timezone.utc), fetched_at=datetime.now(timezone.utc), content_type="SOCIAL", language="en"))
    with pytest.raises(IntegrityError): db_session.commit()

def test_feed_excludes_posts_followed_only_by_another_user(client, db_session: Session) -> None:
    _current_user, current_token = register_login(client, "feed-isolation@example.com", "feed-isolation")
    _other_user, other_token = register_login(client, "feed-foreign@example.com", "feed-foreign")
    foreign_source = source(db_session, "foreign-active")
    foreign_post = post(db_session, foreign_source, external_id="foreign-post")

    foreign_relation = follow(client, other_token, foreign_source.id)
    assert foreign_relation.status_code == 201

    response = client.get("/api/v1/sentiment/posts", headers=headers(current_token))

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []
    assert foreign_post.id not in [item["post_id"] for item in response.json()["items"]]


def test_feed_excludes_posts_after_followed_source_becomes_inactive(client, db_session: Session) -> None:
    _user, token = register_login(client, "feed-inactive@example.com", "feed-inactive")
    inactive_source = source(db_session, "will-be-inactive")
    inactive_post = post(db_session, inactive_source, external_id="inactive-after-follow")

    relation = follow(client, token, inactive_source.id)
    assert relation.status_code == 201
    initial = client.get("/api/v1/sentiment/posts", headers=headers(token))
    assert initial.status_code == 200
    assert initial.json()["total"] == 1
    assert initial.json()["items"][0]["post_id"] == inactive_post.id

    inactive_source.is_active = False
    db_session.commit()

    response = client.get("/api/v1/sentiment/posts", headers=headers(token))

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []