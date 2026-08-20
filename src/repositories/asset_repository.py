from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_type_history import TefasFundTypeHistory


class AssetRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_source_and_code(
        self,
        *,
        data_source: str,
        asset_code: str,
    ) -> Asset | None:
        statement = select(Asset).where(
            Asset.data_source == data_source,
            Asset.asset_code == asset_code,
        )
        return self.db.scalar(statement)

    def list_active_by_data_source(self, data_source: str) -> list[Asset]:
        statement = (
            select(Asset)
            .where(
                Asset.data_source == data_source,
                Asset.is_active.is_(True),
            )
            .order_by(Asset.asset_code.asc())
        )
        return list(self.db.scalars(statement))

    def list_active_tefas_assets(self, *, limit: int) -> list[Asset]:
        if limit <= 0:
            return []

        statement = (
            select(Asset)
            .where(
                Asset.data_source == "TEFAS",
                Asset.is_active.is_(True),
            )
            .order_by(Asset.asset_code.asc())
            .limit(limit)
        )
        return list(self.db.scalars(statement))

    def list_active_tefas_by_fund_kind(self, *, fund_kind: str) -> list[Asset]:
        statement = (
            select(Asset)
            .where(
                Asset.data_source == "TEFAS",
                Asset.is_active.is_(True),
                Asset.fund_kind == fund_kind,
            )
            .order_by(Asset.asset_code.asc())
        )
        return list(self.db.scalars(statement))

    def list_active_tefas_without_current_fund_type(
        self,
        *,
        fund_kind: str,
        limit: int,
    ) -> list[Asset]:
        if limit <= 0:
            return []

        current_fund_type_exists = (
            select(TefasFundTypeHistory.id)
            .where(
                TefasFundTypeHistory.asset_id == Asset.id,
                TefasFundTypeHistory.closed_at.is_(None),
            )
            .exists()
        )
        statement = (
            select(Asset)
            .where(
                Asset.data_source == "TEFAS",
                Asset.fund_kind == fund_kind,
                Asset.is_active.is_(True),
                ~current_fund_type_exists,
            )
            .order_by(Asset.asset_code.asc())
            .limit(limit)
        )
        return list(self.db.scalars(statement))

    def add(self, asset: Asset) -> Asset:
        self.db.add(asset)
        self.db.flush()
        return asset
