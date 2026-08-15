from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.tefas_fund_detail_snapshot import TefasFundDetailSnapshot


class TefasFundDetailSnapshotRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_asset_and_observed_at(
        self,
        *,
        asset_id: int,
        observed_at: datetime,
    ) -> TefasFundDetailSnapshot | None:
        statement = select(TefasFundDetailSnapshot).where(
            TefasFundDetailSnapshot.asset_id == asset_id,
            TefasFundDetailSnapshot.observed_at == observed_at,
        )
        return self.db.scalar(statement)

    def get_latest_for_asset(
        self,
        asset_id: int,
    ) -> TefasFundDetailSnapshot | None:
        statement = (
            select(TefasFundDetailSnapshot)
            .where(TefasFundDetailSnapshot.asset_id == asset_id)
            .order_by(TefasFundDetailSnapshot.observed_at.desc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def add(self, snapshot: TefasFundDetailSnapshot) -> TefasFundDetailSnapshot:
        self.db.add(snapshot)
        self.db.flush()
        return snapshot
