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

from sqlalchemy.orm import Session

from src.model.watchlist_item import WatchlistItem
from src.repositories.watchlist_repository import WatchlistRepository


def add_watchlist_item(db_session: Session, *, user_id: int, asset_id: int) -> WatchlistItem:
    item = WatchlistItem(user_id=user_id, asset_id=asset_id)
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


def test_repository_getters_are_scoped_to_user(db_session: Session) -> None:
    first_user = add_user(db_session, email="first@example.com", username="first")
    second_user = add_user(db_session, email="second@example.com", username="second")
    asset = add_asset(db_session)
    item = add_watchlist_item(db_session, user_id=first_user.id, asset_id=asset.id)
    repository = WatchlistRepository(db_session)

    assert repository.get_by_user_and_asset(user_id=first_user.id, asset_id=asset.id).id == item.id
    assert repository.get_by_user_and_asset(user_id=second_user.id, asset_id=asset.id) is None
    assert repository.get_by_id_for_user(watchlist_item_id=item.id, user_id=first_user.id).id == item.id
    assert repository.get_by_id_for_user(watchlist_item_id=item.id, user_id=second_user.id) is None


def test_repository_list_preserves_user_isolation_total_pagination_and_order(db_session: Session) -> None:
    user = add_user(db_session)
    other_user = add_user(db_session, email="other@example.com", username="other")
    asset_b = add_asset(db_session, asset_code="BBB", asset_name="BBB Fund")
    asset_a2 = add_asset(db_session, asset_code="AAA", asset_name="Second AAA", data_source="MANUAL")
    asset_a1 = add_asset(db_session, asset_code="AAA", asset_name="First AAA")
    other_asset = add_asset(db_session, asset_code="AAC", asset_name="Other User")
    item_b = add_watchlist_item(db_session, user_id=user.id, asset_id=asset_b.id)
    item_a2 = add_watchlist_item(db_session, user_id=user.id, asset_id=asset_a2.id)
    item_a1 = add_watchlist_item(db_session, user_id=user.id, asset_id=asset_a1.id)
    add_watchlist_item(db_session, user_id=other_user.id, asset_id=other_asset.id)
    repository = WatchlistRepository(db_session)

    rows = repository.list_by_user_with_asset(user_id=user.id, skip=1, limit=2)

    assert repository.count_by_user(user_id=user.id) == 3
    assert [row.id for row in rows] == [item_a1.id, item_b.id]
    assert [(row.asset_code, row.asset_name) for row in rows] == [("AAA", "First AAA"), ("BBB", "BBB Fund")]
    assert item_a2.id < item_a1.id


def test_repository_listing_keeps_existing_item_when_asset_later_inactive(db_session: Session) -> None:
    user = add_user(db_session)
    asset = add_asset(db_session, is_active=False)
    item = add_watchlist_item(db_session, user_id=user.id, asset_id=asset.id)
    repository = WatchlistRepository(db_session)

    rows = repository.list_by_user_with_asset(user_id=user.id, skip=0, limit=50)

    assert [row.id for row in rows] == [item.id]
    assert rows[0].asset_code == asset.asset_code


def test_repository_delete_hard_deletes_item(db_session: Session) -> None:
    user = add_user(db_session)
    asset = add_asset(db_session)
    item = add_watchlist_item(db_session, user_id=user.id, asset_id=asset.id)
    repository = WatchlistRepository(db_session)

    repository.delete(item)
    db_session.commit()

    assert db_session.get(WatchlistItem, item.id) is None
