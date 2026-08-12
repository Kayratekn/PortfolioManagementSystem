from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.tefas_fund_type_history import TefasFundTypeHistory


class TefasFundTypeHistoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_current_for_asset(
        self,
        *,
        asset_id: int,
    ) -> TefasFundTypeHistory | None:
        statement = select(TefasFundTypeHistory).where(
            TefasFundTypeHistory.asset_id == asset_id,
            TefasFundTypeHistory.closed_at.is_(None),
        )
        return self.db.scalar(statement)

    def list_by_asset(
        self,
        *,
        asset_id: int,
    ) -> list[TefasFundTypeHistory]:
        statement = (
            select(TefasFundTypeHistory)
            .where(TefasFundTypeHistory.asset_id == asset_id)
            .order_by(
                TefasFundTypeHistory.first_observed_at.asc(),
                TefasFundTypeHistory.id.asc(),
            )
        )
        return list(self.db.scalars(statement))

    def add(self, history: TefasFundTypeHistory) -> TefasFundTypeHistory:
        self.db.add(history)
        self.db.flush()
        return history