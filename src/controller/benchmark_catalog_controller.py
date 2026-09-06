from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from src.config.dependencies import get_benchmark_catalog_service, get_current_user
from src.model.user import User
from src.response.benchmark_catalog_response import BenchmarkCatalogResponse
from src.services.benchmark_catalog_service import BenchmarkCatalogService


router = APIRouter(prefix="/api/v1/benchmarks", tags=["benchmarks"])


@router.get("", response_model=BenchmarkCatalogResponse)
def list_benchmarks(
    current_user: Annotated[User, Depends(get_current_user)],
    benchmark_catalog_service: Annotated[
        BenchmarkCatalogService,
        Depends(get_benchmark_catalog_service),
    ],
) -> BenchmarkCatalogResponse:
    return benchmark_catalog_service.list_benchmarks()