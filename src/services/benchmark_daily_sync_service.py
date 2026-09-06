from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from src.config.supported_benchmarks import SUPPORTED_BENCHMARKS
from src.integrations.yahoo_finance_benchmark_client import YahooFinanceBenchmarkClient
from src.repositories.benchmark_price_repository import BenchmarkPriceRepository
from src.repositories.benchmark_repository import BenchmarkRepository
from src.services.benchmark_price_import_parser import BenchmarkPriceObservation
from src.services.benchmark_price_import_service import BenchmarkPriceImportService


YAHOO_FINANCE_DAILY_CLOSE_SOURCE = "YAHOO_FINANCE_DAILY_CLOSE"


@dataclass(frozen=True)
class BenchmarkDailySyncResult:
    benchmark_code: str
    provider_symbol: str
    start_date: date
    end_date: date
    fetched_rows: int
    rows_created: int
    rows_updated: int


class BenchmarkDailySyncService:
    def __init__(
        self,
        db: Session,
        *,
        client: YahooFinanceBenchmarkClient | None = None,
    ) -> None:
        self.db = db
        self.client = client or YahooFinanceBenchmarkClient()
        self.benchmark_repository = BenchmarkRepository(db)
        self.benchmark_price_repository = BenchmarkPriceRepository(db)

    def sync(
        self,
        *,
        benchmark_code: str,
        reference_date: date,
    ) -> BenchmarkDailySyncResult:
        normalized_code = benchmark_code.strip().upper() if isinstance(benchmark_code, str) else ""
        metadata = SUPPORTED_BENCHMARKS.get(normalized_code)
        if metadata is None:
            raise ValueError(f"Unsupported benchmark code: {benchmark_code}")

        benchmark = self.benchmark_repository.get_active_by_code(normalized_code)
        if benchmark is None:
            raise LookupError(f"Active benchmark not found: {normalized_code}")

        latest_price = self.benchmark_price_repository.get_latest_by_benchmark(
            benchmark_id=benchmark.id
        )
        if latest_price is None:
            raise ValueError(
                f"Benchmark {normalized_code} has no persisted price history; "
                "historical bootstrap is required before daily sync."
            )

        start_date = latest_price.price_date + timedelta(days=1)
        end_date = reference_date
        if start_date >= end_date:
            return BenchmarkDailySyncResult(
                benchmark_code=normalized_code,
                provider_symbol=metadata.provider_symbol,
                start_date=start_date,
                end_date=end_date,
                fetched_rows=0,
                rows_created=0,
                rows_updated=0,
            )

        observations = self.client.fetch_daily_close(
            symbol=metadata.provider_symbol,
            start_date=start_date,
            end_date=end_date,
        )
        self._validate_provider_observations(
            observations,
            benchmark_code=normalized_code,
            start_date=start_date,
            end_date=end_date,
        )
        import_result = BenchmarkPriceImportService(
            self.db,
            today=reference_date,
        ).import_observations(
            benchmark_code=normalized_code,
            source=YAHOO_FINANCE_DAILY_CLOSE_SOURCE,
            observations=observations,
            allow_revisions=False,
        )
        return BenchmarkDailySyncResult(
            benchmark_code=normalized_code,
            provider_symbol=metadata.provider_symbol,
            start_date=start_date,
            end_date=end_date,
            fetched_rows=import_result.fetched_rows,
            rows_created=import_result.rows_created,
            rows_updated=import_result.rows_updated,
        )

    def _validate_provider_observations(
        self,
        observations: list[BenchmarkPriceObservation],
        *,
        benchmark_code: str,
        start_date: date,
        end_date: date,
    ) -> None:
        for observation in observations:
            if not isinstance(observation.close_value, Decimal):
                raise ValueError(
                    "Yahoo Finance benchmark close value must be Decimal before import."
                )
            if observation.price_date < start_date or observation.price_date >= end_date:
                raise ValueError(
                    "Yahoo Finance observation outside requested range for "
                    f"benchmark_code={benchmark_code}, "
                    f"price_date={observation.price_date.isoformat()}, "
                    f"range=[{start_date.isoformat()}, {end_date.isoformat()})."
                )
