from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupportedBenchmark:
    code: str
    name: str
    benchmark_type: str
    native_currency: str
    index_owner: str
    return_type: str
    provider: str
    provider_symbol: str
    is_active: bool


BIST100_BENCHMARK = SupportedBenchmark(
    code="BIST100",
    name="BIST 100",
    benchmark_type="MARKET_INDEX",
    native_currency="TRY",
    index_owner="BORSA_ISTANBUL",
    return_type="PRICE_RETURN",
    provider="YAHOO_FINANCE",
    provider_symbol="XU100.IS",
    is_active=True,
)


SUPPORTED_BENCHMARKS: dict[str, SupportedBenchmark] = {
    BIST100_BENCHMARK.code: BIST100_BENCHMARK,
}
