from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.watchlist_item import WatchlistItem


@dataclass(frozen=True)
class WatchlistItemWithAsset:
    id: int
    asset_id: int
    asset_code: str
    asset_name: str
    asset_type: str
    fund_kind: str | None
    isin: str | None
    currency: str | None
    data_source: str
    created_at: datetime


class WatchlistRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, watchlist_item: WatchlistItem) -> WatchlistItem:
        self.db.add(watchlist_item)
        self.db.flush()
        return watchlist_item

    def get_by_user_and_asset(self, *, user_id: int, asset_id: int) -> WatchlistItem | None:
        statement = select(WatchlistItem).where(
            WatchlistItem.user_id == user_id,
            WatchlistItem.asset_id == asset_id,
        )
        return self.db.scalar(statement)

    def get_by_id_for_user(self, *, watchlist_item_id: int, user_id: int) -> WatchlistItem | None:
        statement = select(WatchlistItem).where(
            WatchlistItem.id == watchlist_item_id,
            WatchlistItem.user_id == user_id,
        )
        return self.db.scalar(statement)

    def list_by_user_with_asset(self, *, user_id: int, skip: int, limit: int) -> list[WatchlistItemWithAsset]:
        statement = (
            select(
                WatchlistItem.id,
                WatchlistItem.asset_id,
                Asset.asset_code,
                Asset.asset_name,
                Asset.asset_type,
                Asset.fund_kind,
                Asset.isin,
                Asset.currency,
                Asset.data_source,
                WatchlistItem.created_at,
            )
            .join(Asset, Asset.id == WatchlistItem.asset_id)
            .where(WatchlistItem.user_id == user_id)
            .order_by(Asset.asset_code.asc(), WatchlistItem.id.asc())
            .offset(skip)
            .limit(limit)
        )
        return [WatchlistItemWithAsset(*row) for row in self.db.execute(statement).all()]

    def count_by_user(self, *, user_id: int) -> int:
        statement = select(func.count(WatchlistItem.id)).where(WatchlistItem.user_id == user_id)
        return int(self.db.scalar(statement) or 0)

    def delete(self, watchlist_item: WatchlistItem) -> None:
        self.db.delete(watchlist_item)
        self.db.flush()
