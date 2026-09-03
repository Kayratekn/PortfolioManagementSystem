from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.model.benchmark_price import BenchmarkPrice
from src.repositories.benchmark_price_repository import BenchmarkPriceRepository
from src.repositories.benchmark_repository import BenchmarkRepository
from src.services.benchmark_price_import_parser import BenchmarkPriceObservation


BENCHMARK_CLOSE_SCALE = Decimal("0.00000001")


@dataclass(frozen=True)
class BenchmarkPriceImportResult:
    fetched_rows: int
    rows_created: int
    rows_updated: int


class BenchmarkPriceImportService:
    def __init__(
        self,
        db: Session,
        *,
        today: date | None = None,
    ) -> None:
        self.db = db
        self.today = today or date.today()
        self.benchmark_repository = BenchmarkRepository(db)
        self.benchmark_price_repository = BenchmarkPriceRepository(db)

    def import_observations(
        self,
        *,
        benchmark_code: str,
        source: str,
        observations: list[BenchmarkPriceObservation],
        allow_revisions: bool = False,
    ) -> BenchmarkPriceImportResult:
        normalized_source = source.strip() if isinstance(source, str) else ""
        if not normalized_source:
            raise ValueError("source must not be blank.")

        benchmark = self.benchmark_repository.get_by_code(benchmark_code)
        if benchmark is None or benchmark.is_active is not True:
            raise LookupError(f"Active benchmark not found: {benchmark_code}")

        self._validate_observations(observations)

        if not observations:
            return BenchmarkPriceImportResult(fetched_rows=0, rows_created=0, rows_updated=0)

        rows_created = 0
        rows_updated = 0

        try:
            for observation in observations:
                existing_price = self.benchmark_price_repository.get_by_benchmark_and_date(
                    benchmark_id=benchmark.id,
                    price_date=observation.price_date,
                )
                if existing_price is None:
                    self.benchmark_price_repository.add(
                        BenchmarkPrice(
                            benchmark_id=benchmark.id,
                            price_date=observation.price_date,
                            close_value=observation.close_value,
                            source=normalized_source,
                        )
                    )
                    rows_created += 1
                    continue

                close_changed = existing_price.close_value != observation.close_value
                source_changed = existing_price.source != normalized_source
                if not close_changed and not source_changed:
                    continue
                if not allow_revisions:
                    raise ValueError(
                        "Benchmark price revision requires explicit allow_revisions=True for "
                        f"benchmark_code={benchmark_code}, "
                        f"price_date={observation.price_date.isoformat()}."
                    )

                if close_changed:
                    existing_price.close_value = observation.close_value
                if source_changed:
                    existing_price.source = normalized_source
                rows_updated += 1

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return BenchmarkPriceImportResult(
            fetched_rows=len(observations),
            rows_created=rows_created,
            rows_updated=rows_updated,
        )

    def _validate_observations(self, observations: list[BenchmarkPriceObservation]) -> None:
        seen_dates: set[date] = set()
        for observation in observations:
            if observation.price_date in seen_dates:
                raise ValueError(
                    "Duplicate benchmark price observation for "
                    f"date={observation.price_date.isoformat()}."
                )
            seen_dates.add(observation.price_date)
            if not isinstance(observation.close_value, Decimal):
                raise ValueError("Benchmark close value must be a Decimal.")
            if not observation.close_value.is_finite() or observation.close_value <= Decimal("0"):
                raise ValueError("Benchmark close value must be greater than zero.")
            if observation.close_value.quantize(BENCHMARK_CLOSE_SCALE) != observation.close_value:
                raise ValueError("Benchmark close value must fit NUMERIC(20,8) without rounding.")
            if observation.price_date >= self.today:
                raise ValueError("Benchmark price observations must be before the current date.")