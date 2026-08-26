from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from src.integrations.tcmb_client import TcmbClient, TcmbExchangeRateObservation
from src.model.exchange_rate import ExchangeRate
from src.repositories.exchange_rate_repository import ExchangeRateRepository


TCMB_SOURCE = "TCMB"


@dataclass(frozen=True)
class TcmbSyncResult:
    fetched_rows: int
    rows_created: int
    rows_updated: int


class TcmbSyncService:
    def __init__(
        self,
        db: Session,
        tcmb_client: TcmbClient | None = None,
    ) -> None:
        self.db = db
        self.tcmb_client = tcmb_client or TcmbClient()
        self.exchange_rate_repository = ExchangeRateRepository(db)

    def sync_current_rates(self) -> TcmbSyncResult:
        observations = self.tcmb_client.fetch_current_rates()
        return self._persist_observations(observations)

    def sync_historical_rates(self, *, rate_date: date) -> TcmbSyncResult:
        observations = self.tcmb_client.fetch_historical_rates(rate_date=rate_date)
        return self._persist_observations(observations)

    def _persist_observations(
        self,
        observations: list[TcmbExchangeRateObservation],
    ) -> TcmbSyncResult:
        if not observations:
            return TcmbSyncResult(fetched_rows=0, rows_created=0, rows_updated=0)

        rows_created = 0
        rows_updated = 0

        try:
            for observation in observations:
                existing_rate = self.exchange_rate_repository.get_by_pair_and_date(
                    base_currency=observation.base_currency,
                    quote_currency=observation.quote_currency,
                    rate_date=observation.rate_date,
                    source=TCMB_SOURCE,
                )

                if existing_rate is None:
                    self.exchange_rate_repository.add(
                        ExchangeRate(
                            base_currency=observation.base_currency,
                            quote_currency=observation.quote_currency,
                            rate_date=observation.rate_date,
                            forex_buying=observation.forex_buying,
                            forex_selling=observation.forex_selling,
                            source=TCMB_SOURCE,
                        )
                    )
                    rows_created += 1
                    continue

                rate_changed = False
                if existing_rate.forex_buying != observation.forex_buying:
                    existing_rate.forex_buying = observation.forex_buying
                    rate_changed = True
                if existing_rate.forex_selling != observation.forex_selling:
                    existing_rate.forex_selling = observation.forex_selling
                    rate_changed = True
                if rate_changed:
                    rows_updated += 1

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return TcmbSyncResult(
            fetched_rows=len(observations),
            rows_created=rows_created,
            rows_updated=rows_updated,
        )