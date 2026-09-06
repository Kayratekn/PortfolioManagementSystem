from __future__ import annotations

from src.model.asset import Asset
from src.model.user import User
from sqlalchemy.orm import Session


def add_user(db_session: Session, *, email: str = "user@example.com", username: str = "user") -> User:
    user = User(
        email=email,
        username=username,
        hashed_password="hashed",
        preferred_currency="TRY",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def add_asset(
    db_session: Session,
    *,
    asset_code: str = "AAL",
    asset_name: str = "Example Fund",
    asset_type: str = "FUND",
    fund_kind: str | None = "YAT",
    isin: str | None = "TRTESTISIN01",
    currency: str | None = "TRY",
    data_source: str = "TEFAS",
    is_active: bool = True,
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=asset_name,
        asset_type=asset_type,
        fund_kind=fund_kind,
        isin=isin,
        currency=currency,
        data_source=data_source,
        is_active=is_active,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import src.services.watchlist_service as watchlist_service_module
from src.model.watchlist_item import WatchlistItem
from src.repositories.asset_repository import AssetRepository
from src.repositories.watchlist_repository import WatchlistRepository
from src.services.watchlist_service import WatchlistService


def service(db_session: Session) -> WatchlistService:
    return WatchlistService(
        db=db_session,
        asset_repository=AssetRepository(db_session),
        watchlist_repository=WatchlistRepository(db_session),
    )


def test_service_creates_lists_and_deletes_item(db_session: Session) -> None:
    user = add_user(db_session)
    asset = add_asset(db_session)

    created = service(db_session).create_item(asset_id=asset.id, current_user=user)
    listed = service(db_session).list_items(current_user=user, skip=0, limit=50)
    service(db_session).delete_item(watchlist_item_id=created.id, current_user=user)

    assert created.asset_id == asset.id
    assert created.asset_code == asset.asset_code
    assert listed.total == 1
    assert listed.items[0].id == created.id
    assert db_session.get(WatchlistItem, created.id) is None


@pytest.mark.parametrize("is_active", [False])
def test_service_missing_or_inactive_asset_returns_404(db_session: Session, is_active: bool) -> None:
    user = add_user(db_session)
    asset = add_asset(db_session, is_active=is_active)

    with pytest.raises(HTTPException) as exc_info:
        service(db_session).create_item(asset_id=asset.id, current_user=user)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Asset not found."

    with pytest.raises(HTTPException) as missing_exc:
        service(db_session).create_item(asset_id=999999, current_user=user)

    assert missing_exc.value.status_code == 404
    assert missing_exc.value.detail == "Asset not found."


def test_service_duplicate_returns_409(db_session: Session) -> None:
    user = add_user(db_session)
    asset = add_asset(db_session)
    service(db_session).create_item(asset_id=asset.id, current_user=user)

    with pytest.raises(HTTPException) as exc_info:
        service(db_session).create_item(asset_id=asset.id, current_user=user)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Asset is already in watchlist."


def test_service_integrity_error_duplicate_race_rolls_back_and_returns_409(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = add_user(db_session)
    asset = add_asset(db_session)
    rollback_calls = 0

    def failing_add(self: WatchlistRepository, watchlist_item: WatchlistItem) -> WatchlistItem:
        raise IntegrityError("duplicate", {}, None)

    def counting_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1

    monkeypatch.setattr(WatchlistRepository, "add", failing_add)
    monkeypatch.setattr(db_session, "rollback", counting_rollback)

    with pytest.raises(HTTPException) as exc_info:
        service(db_session).create_item(asset_id=asset.id, current_user=user)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Asset is already in watchlist."
    assert rollback_calls == 1


def test_service_allows_same_asset_for_different_users(db_session: Session) -> None:
    first_user = add_user(db_session, email="first@example.com", username="first")
    second_user = add_user(db_session, email="second@example.com", username="second")
    asset = add_asset(db_session)

    first = service(db_session).create_item(asset_id=asset.id, current_user=first_user)
    second = service(db_session).create_item(asset_id=asset.id, current_user=second_user)

    assert first.asset_id == second.asset_id == asset.id
    assert first.id != second.id


def test_service_delete_ownership_isolation_returns_404(db_session: Session) -> None:
    owner = add_user(db_session, email="owner@example.com", username="owner")
    other = add_user(db_session, email="other@example.com", username="other")
    asset = add_asset(db_session)
    created = service(db_session).create_item(asset_id=asset.id, current_user=owner)

    with pytest.raises(HTTPException) as exc_info:
        service(db_session).delete_item(watchlist_item_id=created.id, current_user=other)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Watchlist item not found."
    assert db_session.get(WatchlistItem, created.id) is not None


def test_service_list_does_not_hide_existing_item_when_asset_later_inactive(db_session: Session) -> None:
    user = add_user(db_session)
    asset = add_asset(db_session)
    service(db_session).create_item(asset_id=asset.id, current_user=user)
    asset.is_active = False
    db_session.commit()

    listed = service(db_session).list_items(current_user=user, skip=0, limit=50)

    assert listed.total == 1
    assert listed.items[0].asset_id == asset.id
