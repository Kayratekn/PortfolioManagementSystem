from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.config.supported_benchmarks import SupportedBenchmark
from src.model.benchmark import Benchmark
from src.repositories.benchmark_repository import BenchmarkRepository


BENCHMARK_BOOTSTRAP_CREATED = "CREATED"
BENCHMARK_BOOTSTRAP_ALREADY_EXISTS = "ALREADY_EXISTS"


@dataclass(frozen=True)
class BenchmarkBootstrapResult:
    status: str
    benchmark: Benchmark


class BenchmarkBootstrapConflictError(ValueError):
    pass


class BenchmarkBootstrapService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.benchmark_repository = BenchmarkRepository(db)

    def bootstrap(self, metadata: SupportedBenchmark) -> BenchmarkBootstrapResult:
        try:
            self._validate_metadata(metadata)
            existing = self.benchmark_repository.get_by_code(metadata.code)
            if existing is not None:
                self._raise_if_metadata_conflicts(existing, metadata)
                return BenchmarkBootstrapResult(
                    status=BENCHMARK_BOOTSTRAP_ALREADY_EXISTS,
                    benchmark=existing,
                )

            provider_owner = self.benchmark_repository.get_by_provider_symbol(
                provider=metadata.provider,
                provider_symbol=metadata.provider_symbol,
            )
            if provider_owner is not None:
                raise BenchmarkBootstrapConflictError(
                    "Benchmark provider identity conflict: "
                    f"provider={metadata.provider}, "
                    f"provider_symbol={metadata.provider_symbol}, "
                    f"existing_code={provider_owner.code}."
                )

            benchmark = self.benchmark_repository.add(
                Benchmark(
                    code=metadata.code,
                    name=metadata.name,
                    benchmark_type=metadata.benchmark_type,
                    native_currency=metadata.native_currency,
                    index_owner=metadata.index_owner,
                    return_type=metadata.return_type,
                    provider=metadata.provider,
                    provider_symbol=metadata.provider_symbol,
                    is_active=metadata.is_active,
                )
            )
            self.db.commit()
            return BenchmarkBootstrapResult(
                status=BENCHMARK_BOOTSTRAP_CREATED,
                benchmark=benchmark,
            )
        except Exception:
            self.db.rollback()
            raise

    def _validate_metadata(self, metadata: SupportedBenchmark) -> None:
        fields = (
            "code",
            "name",
            "benchmark_type",
            "native_currency",
            "index_owner",
            "return_type",
            "provider",
            "provider_symbol",
        )
        for field_name in fields:
            value = getattr(metadata, field_name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{field_name} must be a nonblank string.")
            if value.strip() != value:
                raise ValueError(f"{field_name} must not include surrounding whitespace.")
        for field_name in ("native_currency", "index_owner", "return_type"):
            value = getattr(metadata, field_name)
            if value.upper() != value:
                raise ValueError(f"{field_name} must be uppercase.")
        if metadata.is_active is not True:
            raise ValueError("Supported benchmark metadata must be active.")

    def _raise_if_metadata_conflicts(
        self,
        existing: Benchmark,
        metadata: SupportedBenchmark,
    ) -> None:
        mismatches: list[str] = []
        for field_name in (
            "code",
            "name",
            "benchmark_type",
            "native_currency",
            "index_owner",
            "return_type",
            "provider",
            "provider_symbol",
            "is_active",
        ):
            if getattr(existing, field_name) != getattr(metadata, field_name):
                mismatches.append(field_name)

        if mismatches:
            raise BenchmarkBootstrapConflictError(
                "Benchmark metadata conflict for "
                f"code={metadata.code}: {', '.join(mismatches)}."
            )
