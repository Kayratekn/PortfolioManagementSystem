from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.portfolio_snapshot import PortfolioSnapshot


class PortfolioSnapshotRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, snapshot: PortfolioSnapshot) -> PortfolioSnapshot:
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    def get_by_portfolio_and_date(
        self,
        *,
        portfolio_id: int,
        snapshot_date: date,
    ) -> PortfolioSnapshot | None:
        statement = select(PortfolioSnapshot).where(
            PortfolioSnapshot.portfolio_id == portfolio_id,
            PortfolioSnapshot.snapshot_date == snapshot_date,
        )
        return self.db.scalar(statement)

    def get_latest_on_or_before(
        self,
        *,
        portfolio_id: int,
        snapshot_date: date,
    ) -> PortfolioSnapshot | None:
        statement = (
            select(PortfolioSnapshot)
            .where(
                PortfolioSnapshot.portfolio_id == portfolio_id,
                PortfolioSnapshot.snapshot_date <= snapshot_date,
            )
            .order_by(PortfolioSnapshot.snapshot_date.desc(), PortfolioSnapshot.id.desc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def list_by_portfolio_between(
        self,
        *,
        portfolio_id: int,
        start_date: date,
        end_date: date,
    ) -> list[PortfolioSnapshot]:
        statement = (
            select(PortfolioSnapshot)
            .where(
                PortfolioSnapshot.portfolio_id == portfolio_id,
                PortfolioSnapshot.snapshot_date >= start_date,
                PortfolioSnapshot.snapshot_date <= end_date,
            )
            .order_by(PortfolioSnapshot.snapshot_date.asc(), PortfolioSnapshot.id.asc())
        )
        return list(self.db.scalars(statement))

    def get_latest_by_portfolio(self, *, portfolio_id: int) -> PortfolioSnapshot | None:
        statement = (
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.portfolio_id == portfolio_id)
            .order_by(PortfolioSnapshot.snapshot_date.desc(), PortfolioSnapshot.id.desc())
            .limit(1)
        )
        return self.db.scalar(statement)