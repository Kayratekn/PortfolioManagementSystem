from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.exchange_rate import ExchangeRate


class ExchangeRateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, exchange_rate: ExchangeRate) -> ExchangeRate:
        self.db.add(exchange_rate)
        self.db.flush()
        return exchange_rate

    def get_by_pair_and_date(
        self,
        *,
        base_currency: str,
        quote_currency: str,
        rate_date: date,
        source: str,
    ) -> ExchangeRate | None:
        statement = select(ExchangeRate).where(
            ExchangeRate.base_currency == base_currency,
            ExchangeRate.quote_currency == quote_currency,
            ExchangeRate.rate_date == rate_date,
            ExchangeRate.source == source,
        )
        return self.db.scalar(statement)

    def get_latest_on_or_before(
        self,
        *,
        base_currency: str,
        quote_currency: str,
        rate_date: date,
        source: str,
    ) -> ExchangeRate | None:
        statement = (
            select(ExchangeRate)
            .where(
                ExchangeRate.base_currency == base_currency,
                ExchangeRate.quote_currency == quote_currency,
                ExchangeRate.rate_date <= rate_date,
                ExchangeRate.source == source,
            )
            .order_by(ExchangeRate.rate_date.desc())
            .limit(1)
        )
        return self.db.scalar(statement)