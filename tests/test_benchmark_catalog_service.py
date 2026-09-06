from __future__ import annotations

from types import SimpleNamespace

from src.services.benchmark_catalog_service import BenchmarkCatalogService


class FakeBenchmarkRepository:
    def __init__(self) -> None:
        self.list_active_calls = 0
        self.benchmarks = [
            SimpleNamespace(
                id=3,
                code="BIST100",
                name="BIST 100",
                benchmark_type="MARKET_INDEX",
                native_currency="TRY",
                index_owner="BORSA_ISTANBUL",
                return_type="PRICE_RETURN",
                provider="YAHOO_FINANCE",
                provider_symbol="XU100.IS",
                is_active=True,
            ),
            SimpleNamespace(
                id=7,
                code="SP500",
                name="S&P 500",
                benchmark_type="MARKET_INDEX",
                native_currency="USD",
                index_owner="SP_DOW_JONES_INDICES",
                return_type="PRICE_RETURN",
                provider="YAHOO_FINANCE",
                provider_symbol="^GSPC",
                is_active=True,
            ),
        ]

    def list_active(self) -> list[SimpleNamespace]:
        self.list_active_calls += 1
        return self.benchmarks


def test_list_benchmarks_returns_repository_order_and_total() -> None:
    repository = FakeBenchmarkRepository()
    service = BenchmarkCatalogService(repository)

    result = service.list_benchmarks()

    assert repository.list_active_calls == 1
    assert result.total == 2
    assert [item.code for item in result.items] == ["BIST100", "SP500"]
    assert result.items[0].name == "BIST 100"
    assert result.items[1].native_currency == "USD"