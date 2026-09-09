from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.model.portfolio_snapshot import PortfolioSnapshot
from src.model.user import User
from src.repositories.portfolio_repository import PortfolioRepository
from src.repositories.portfolio_snapshot_repository import PortfolioSnapshotRepository
from src.services.portfolio_valuation_service import (
    PORTFOLIO_STATUS_COMPLETE,
    PortfolioValuationService,
)


SNAPSHOT_CURRENCIES = ("TRY", "USD", "EUR", "GBP")
SNAPSHOT_VALUE_QUANTUM = Decimal("0.00000001")
MAX_SNAPSHOT_RANGE_DAYS = 366


class PortfolioSnapshotService:
    def __init__(
        self,
        db: Session,
        portfolio_repository: PortfolioRepository,
        portfolio_snapshot_repository: PortfolioSnapshotRepository,
        portfolio_valuation_service: PortfolioValuationService,
    ) -> None:
        self.db = db
        self.portfolio_repository = portfolio_repository
        self.portfolio_snapshot_repository = portfolio_snapshot_repository
        self.portfolio_valuation_service = portfolio_valuation_service

    def generate_snapshot(
        self,
        *,
        portfolio_id: int,
        current_user: User,
        snapshot_date: date,
    ) -> PortfolioSnapshot:
        try:
            portfolio = self.portfolio_repository.get_by_id_for_user_for_update(
                portfolio_id,
                current_user.id,
            )
            if portfolio is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Portfolio not found.",
                )

            existing_snapshot = (
                self.portfolio_snapshot_repository.get_by_portfolio_and_date(
                    portfolio_id=portfolio_id,
                    snapshot_date=snapshot_date,
                )
            )
            if existing_snapshot is not None:
                return existing_snapshot

            valuations = {
                currency: self.portfolio_valuation_service.get_valuation_in_currency(
                    portfolio_id=portfolio_id,
                    current_user=current_user,
                    valuation_date=snapshot_date,
                    target_currency=currency,
                )
                for currency in SNAPSHOT_CURRENCIES
            }
            if any(
                valuation.status != PORTFOLIO_STATUS_COMPLETE
                or valuation.total_portfolio_value is None
                for valuation in valuations.values()
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Portfolio snapshot cannot be generated from incomplete valuation.",
                )

            snapshot = PortfolioSnapshot(
                portfolio_id=portfolio.id,
                snapshot_date=snapshot_date,
                total_value_try=self._quantize(valuations["TRY"].total_portfolio_value),
                total_value_usd=self._quantize(valuations["USD"].total_portfolio_value),
                total_value_eur=self._quantize(valuations["EUR"].total_portfolio_value),
                total_value_gbp=self._quantize(valuations["GBP"].total_portfolio_value),
            )
            self.portfolio_snapshot_repository.add(snapshot)
            self.db.refresh(snapshot)
            self.db.commit()
            return snapshot
        except Exception:
            self.db.rollback()
            raise

    def list_snapshots(
        self,
        *,
        portfolio_id: int,
        current_user: User,
        start_date: date,
        end_date: date,
    ) -> list[PortfolioSnapshot]:
        portfolio = self.portfolio_repository.get_by_id_for_user(
            portfolio_id,
            current_user.id,
        )
        if portfolio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found.",
            )
        self._validate_date_range(start_date=start_date, end_date=end_date)

        return self.portfolio_snapshot_repository.list_by_portfolio_between(
            portfolio_id=portfolio.id,
            start_date=start_date,
            end_date=end_date,
        )

    @staticmethod
    def _quantize(value: Decimal | None) -> Decimal:
        assert value is not None
        return value.quantize(SNAPSHOT_VALUE_QUANTUM, rounding=ROUND_HALF_UP)

    @staticmethod
    def _validate_date_range(*, start_date: date, end_date: date) -> None:
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="end_date must be greater than or equal to start_date.",
            )
        if (end_date - start_date).days + 1 > MAX_SNAPSHOT_RANGE_DAYS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Portfolio snapshot date range cannot exceed 366 calendar days.",
            )
