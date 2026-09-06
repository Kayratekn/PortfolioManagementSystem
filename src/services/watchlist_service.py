from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.model.user import User
from src.model.watchlist_item import WatchlistItem
from src.repositories.asset_repository import AssetRepository
from src.repositories.watchlist_repository import WatchlistRepository
from src.response.watchlist_response import WatchlistItemResponse, WatchlistResponse


class WatchlistService:
    def __init__(
        self,
        db: Session,
        asset_repository: AssetRepository,
        watchlist_repository: WatchlistRepository,
    ) -> None:
        self.db = db
        self.asset_repository = asset_repository
        self.watchlist_repository = watchlist_repository

    def create_item(self, *, asset_id: int, current_user: User) -> WatchlistItemResponse:
        asset = self.asset_repository.get_by_id(asset_id)
        if asset is None or asset.is_active is not True:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")

        if self.watchlist_repository.get_by_user_and_asset(
            user_id=current_user.id,
            asset_id=asset_id,
        ) is not None:
            self._raise_duplicate()

        item = WatchlistItem(user_id=current_user.id, asset_id=asset_id)
        try:
            created_item = self.watchlist_repository.add(item)
            self.db.commit()
            self.db.refresh(created_item)
        except IntegrityError:
            self.db.rollback()
            self._raise_duplicate()
        except Exception:
            self.db.rollback()
            raise

        return WatchlistItemResponse(
            id=created_item.id,
            asset_id=asset.id,
            asset_code=asset.asset_code,
            asset_name=asset.asset_name,
            asset_type=asset.asset_type,
            fund_kind=asset.fund_kind,
            isin=asset.isin,
            currency=asset.currency,
            data_source=asset.data_source,
            created_at=created_item.created_at,
        )

    def list_items(self, *, current_user: User, skip: int, limit: int) -> WatchlistResponse:
        items = self.watchlist_repository.list_by_user_with_asset(
            user_id=current_user.id,
            skip=skip,
            limit=limit,
        )
        total = self.watchlist_repository.count_by_user(user_id=current_user.id)
        return WatchlistResponse(
            items=[WatchlistItemResponse(**item.__dict__) for item in items],
            total=total,
            skip=skip,
            limit=limit,
        )

    def delete_item(self, *, watchlist_item_id: int, current_user: User) -> None:
        item = self.watchlist_repository.get_by_id_for_user(
            watchlist_item_id=watchlist_item_id,
            user_id=current_user.id,
        )
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist item not found.",
            )

        try:
            self.watchlist_repository.delete(item)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _raise_duplicate(self) -> None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Asset is already in watchlist.",
        )
