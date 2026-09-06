from __future__ import annotations

from src.repositories.benchmark_repository import BenchmarkRepository
from src.response.benchmark_catalog_response import (
    BenchmarkCatalogItemResponse,
    BenchmarkCatalogResponse,
)


class BenchmarkCatalogService:
    def __init__(self, benchmark_repository: BenchmarkRepository) -> None:
        self.benchmark_repository = benchmark_repository

    def list_benchmarks(self) -> BenchmarkCatalogResponse:
        benchmarks = self.benchmark_repository.list_active()
        return BenchmarkCatalogResponse(
            items=[BenchmarkCatalogItemResponse.model_validate(benchmark) for benchmark in benchmarks],
            total=len(benchmarks),
        )