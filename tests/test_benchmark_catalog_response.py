from __future__ import annotations

from src.model.benchmark import Benchmark
from src.response.benchmark_catalog_response import (
    BenchmarkCatalogItemResponse,
    BenchmarkCatalogResponse,
)


def _build_benchmark() -> Benchmark:
    return Benchmark(
        id=11,
        code="SP500",
        name="S&P 500",
        benchmark_type="MARKET_INDEX",
        native_currency="USD",
        index_owner="SP_DOW_JONES_INDICES",
        return_type="PRICE_RETURN",
        provider="YAHOO_FINANCE",
        provider_symbol="^GSPC",
        is_active=True,
    )


def test_benchmark_catalog_item_response_exposes_public_fields_only() -> None:
    response = BenchmarkCatalogItemResponse.model_validate(_build_benchmark())

    body = response.model_dump()

    assert body == {
        "id": 11,
        "code": "SP500",
        "name": "S&P 500",
        "benchmark_type": "MARKET_INDEX",
        "native_currency": "USD",
        "index_owner": "SP_DOW_JONES_INDICES",
        "return_type": "PRICE_RETURN",
    }
    assert "provider" not in body
    assert "provider_symbol" not in body
    assert "is_active" not in body
    assert "created_at" not in body
    assert "updated_at" not in body


def test_benchmark_catalog_response_preserves_items_and_total() -> None:
    item = BenchmarkCatalogItemResponse.model_validate(_build_benchmark())

    response = BenchmarkCatalogResponse(items=[item], total=1)

    assert response.items == [item]
    assert response.total == 1