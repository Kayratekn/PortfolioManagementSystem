from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.benchmark import Benchmark
from src.model.benchmark_price import BenchmarkPrice
from src.repositories.benchmark_price_repository import BenchmarkPriceRepository
from src.repositories.benchmark_repository import BenchmarkRepository
from src.services.benchmark_price_import_parser import BenchmarkPriceObservation
from src.services.benchmark_price_import_service import BenchmarkPriceImportService


TODAY = date(2026, 9, 3)


def _build_benchmark(
    *,
    code: str = "BIST100",
    name: str = "BIST 100",
    benchmark_type: str = "MARKET_INDEX",
    native_currency: str = "TRY",
    index_owner: str = "BORSA_ISTANBUL",
    return_type: str = "PRICE_RETURN",
    provider: str = "VERIFIED_PROVIDER",
    provider_symbol: str = "XU100",
    is_active: bool = True,
) -> Benchmark:
    return Benchmark(
        code=code,
        name=name,
        benchmark_type=benchmark_type,
        native_currency=native_currency,
        index_owner=index_owner,
        return_type=return_type,
        provider=provider,
        provider_symbol=provider_symbol,
        is_active=is_active,
    )


def _observation(
    price_date: date,
    close_value: Decimal = Decimal("100.00000001"),
) -> BenchmarkPriceObservation:
    return BenchmarkPriceObservation(price_date=price_date, close_value=close_value)


def _prices(db_session: Session) -> list[BenchmarkPrice]:
    return list(
        db_session.scalars(
            select(BenchmarkPrice).order_by(BenchmarkPrice.benchmark_id, BenchmarkPrice.price_date)
        )
    )


def test_import_requires_existing_active_benchmark(db_session: Session) -> None:
    inactive = BenchmarkRepository(db_session).add(
        _build_benchmark(code="INACTIVE", provider_symbol="INACTIVE", is_active=False)
    )
    assert inactive.id is not None
    service = BenchmarkPriceImportService(db_session, today=TODAY)

    with pytest.raises(LookupError):
        service.import_observations(
            benchmark_code="MISSING",
            source="VERIFIED_DATASET",
            observations=[_observation(date(2026, 9, 1))],
        )
    with pytest.raises(LookupError):
        service.import_observations(
            benchmark_code="INACTIVE",
            source="VERIFIED_DATASET",
            observations=[_observation(date(2026, 9, 1))],
        )


def test_import_inserts_observations_and_preserves_decimal(db_session: Session) -> None:
    benchmark = BenchmarkRepository(db_session).add(_build_benchmark())
    service = BenchmarkPriceImportService(db_session, today=TODAY)

    result = service.import_observations(
        benchmark_code="BIST100",
        source="VERIFIED_DATASET",
        observations=[
            _observation(date(2026, 9, 1), Decimal("14000.12345678")),
            _observation(date(2026, 9, 2), Decimal("14050.59960938")),
        ],
    )

    prices = _prices(db_session)
    assert result.fetched_rows == 2
    assert result.rows_created == 2
    assert result.rows_updated == 0
    assert [(price.benchmark_id, price.price_date, price.close_value, price.source) for price in prices] == [
        (benchmark.id, date(2026, 9, 1), Decimal("14000.12345678"), "VERIFIED_DATASET"),
        (benchmark.id, date(2026, 9, 2), Decimal("14050.59960938"), "VERIFIED_DATASET"),
    ]
    assert all(isinstance(price.close_value, Decimal) for price in prices)


def test_identical_reimport_is_idempotent(db_session: Session) -> None:
    BenchmarkRepository(db_session).add(_build_benchmark())
    service = BenchmarkPriceImportService(db_session, today=TODAY)
    observations = [_observation(date(2026, 9, 1), Decimal("14000.12345678"))]

    service.import_observations(
        benchmark_code="BIST100",
        source="VERIFIED_DATASET",
        observations=observations,
    )
    result = service.import_observations(
        benchmark_code="BIST100",
        source="VERIFIED_DATASET",
        observations=observations,
    )

    assert len(_prices(db_session)) == 1
    assert result.fetched_rows == 1
    assert result.rows_created == 0
    assert result.rows_updated == 0


@pytest.mark.parametrize(
    ("source", "close_value"),
    [
        ("VERIFIED_DATASET", Decimal("14001.12345678")),
        ("OTHER_VERIFIED_DATASET", Decimal("14000.12345678")),
        ("OTHER_VERIFIED_DATASET", Decimal("14001.12345678")),
    ],
)
def test_default_import_rejects_existing_date_conflicts_without_mutating_history(
    db_session: Session,
    source: str,
    close_value: Decimal,
) -> None:
    BenchmarkRepository(db_session).add(_build_benchmark())
    service = BenchmarkPriceImportService(db_session, today=TODAY)
    service.import_observations(
        benchmark_code="BIST100",
        source="VERIFIED_DATASET",
        observations=[_observation(date(2026, 9, 1), Decimal("14000.12345678"))],
    )

    with pytest.raises(ValueError):
        service.import_observations(
            benchmark_code="BIST100",
            source=source,
            observations=[_observation(date(2026, 9, 1), close_value)],
        )

    prices = _prices(db_session)
    assert len(prices) == 1
    assert prices[0].close_value == Decimal("14000.12345678")
    assert prices[0].source == "VERIFIED_DATASET"


@pytest.mark.parametrize(
    ("source", "close_value"),
    [
        ("VERIFIED_DATASET", Decimal("14001.12345678")),
        ("SOURCE_B_REVISED", Decimal("14000.12345678")),
        ("SOURCE_B_REVISED", Decimal("14001.12345678")),
    ],
)
def test_allow_revisions_updates_existing_date_without_duplicate(
    db_session: Session,
    source: str,
    close_value: Decimal,
) -> None:
    BenchmarkRepository(db_session).add(_build_benchmark())
    service = BenchmarkPriceImportService(db_session, today=TODAY)
    service.import_observations(
        benchmark_code="BIST100",
        source="VERIFIED_DATASET",
        observations=[_observation(date(2026, 9, 1), Decimal("14000.12345678"))],
    )

    result = service.import_observations(
        benchmark_code="BIST100",
        source=source,
        observations=[_observation(date(2026, 9, 1), close_value)],
        allow_revisions=True,
    )

    prices = _prices(db_session)
    assert len(prices) == 1
    assert prices[0].close_value == close_value
    assert prices[0].source == source
    assert result.rows_created == 0
    assert result.rows_updated == 1


def test_allow_revisions_updates_only_same_benchmark_date(db_session: Session) -> None:
    repository = BenchmarkRepository(db_session)
    first = repository.add(_build_benchmark(code="BIST100", provider_symbol="XU100"))
    second = repository.add(_build_benchmark(code="OTHER", provider_symbol="OTHER"))
    price_repository = BenchmarkPriceRepository(db_session)
    first_price = price_repository.add(
        BenchmarkPrice(
            benchmark_id=first.id,
            price_date=date(2026, 9, 1),
            close_value=Decimal("100.00000000"),
            source="SOURCE_A",
        )
    )
    untouched_price = price_repository.add(
        BenchmarkPrice(
            benchmark_id=second.id,
            price_date=date(2026, 9, 1),
            close_value=Decimal("200.00000000"),
            source="OTHER_SOURCE",
        )
    )
    service = BenchmarkPriceImportService(db_session, today=TODAY)

    service.import_observations(
        benchmark_code="BIST100",
        source="SOURCE_B_REVISED",
        observations=[_observation(date(2026, 9, 1), Decimal("101.00000000"))],
        allow_revisions=True,
    )

    db_session.refresh(first_price)
    db_session.refresh(untouched_price)
    assert first_price.close_value == Decimal("101.00000000")
    assert first_price.source == "SOURCE_B_REVISED"
    assert untouched_price.benchmark_id == second.id
    assert untouched_price.close_value == Decimal("200.00000000")
    assert untouched_price.source == "OTHER_SOURCE"


def test_import_isolates_benchmark_identity_for_same_dates(db_session: Session) -> None:
    repository = BenchmarkRepository(db_session)
    first = repository.add(_build_benchmark(code="BIST100", provider_symbol="XU100"))
    second = repository.add(_build_benchmark(code="OTHER", provider_symbol="OTHER"))
    price_repository = BenchmarkPriceRepository(db_session)
    untouched_price = price_repository.add(
        BenchmarkPrice(
            benchmark_id=second.id,
            price_date=date(2026, 9, 1),
            close_value=Decimal("200.00000000"),
            source="OTHER_SOURCE",
        )
    )
    service = BenchmarkPriceImportService(db_session, today=TODAY)

    service.import_observations(
        benchmark_code="BIST100",
        source="VERIFIED_DATASET",
        observations=[_observation(date(2026, 9, 1), Decimal("14000.00000000"))],
    )

    db_session.refresh(untouched_price)
    first_price = price_repository.get_by_benchmark_and_date(
        benchmark_id=first.id,
        price_date=date(2026, 9, 1),
    )
    assert first_price is not None
    assert first_price.close_value == Decimal("14000.00000000")
    assert untouched_price.benchmark_id == second.id
    assert untouched_price.close_value == Decimal("200.00000000")
    assert untouched_price.source == "OTHER_SOURCE"


@pytest.mark.parametrize("price_date", [TODAY, date(2026, 9, 4)])
def test_import_rejects_current_or_future_dates(db_session: Session, price_date: date) -> None:
    BenchmarkRepository(db_session).add(_build_benchmark())
    service = BenchmarkPriceImportService(db_session, today=TODAY)

    with pytest.raises(ValueError):
        service.import_observations(
            benchmark_code="BIST100",
            source="VERIFIED_DATASET",
            observations=[_observation(price_date)],
        )


@pytest.mark.parametrize("price_date", [date(2026, 9, 1), date(2026, 9, 2)])
def test_import_accepts_historical_dates(db_session: Session, price_date: date) -> None:
    BenchmarkRepository(db_session).add(_build_benchmark())
    service = BenchmarkPriceImportService(db_session, today=TODAY)

    result = service.import_observations(
        benchmark_code="BIST100",
        source="VERIFIED_DATASET",
        observations=[_observation(price_date)],
    )

    assert result.rows_created == 1


def test_import_rejects_duplicate_validated_observation_dates(db_session: Session) -> None:
    BenchmarkRepository(db_session).add(_build_benchmark())
    service = BenchmarkPriceImportService(db_session, today=TODAY)

    with pytest.raises(ValueError):
        service.import_observations(
            benchmark_code="BIST100",
            source="VERIFIED_DATASET",
            observations=[
                _observation(date(2026, 9, 1), Decimal("100")),
                _observation(date(2026, 9, 1), Decimal("100")),
            ],
        )


def test_import_rejects_non_decimal_close_without_float_conversion(db_session: Session) -> None:
    BenchmarkRepository(db_session).add(_build_benchmark())
    service = BenchmarkPriceImportService(db_session, today=TODAY)

    with pytest.raises(ValueError):
        service.import_observations(
            benchmark_code="BIST100",
            source="VERIFIED_DATASET",
            observations=[BenchmarkPriceObservation(date(2026, 9, 1), 100.1)],  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "close_value",
    [Decimal("14050.59960938"), Decimal("123"), Decimal("1.230000000")],
)
def test_import_accepts_values_representable_at_scale_8_without_rounding(
    db_session: Session,
    close_value: Decimal,
) -> None:
    BenchmarkRepository(db_session).add(_build_benchmark())
    service = BenchmarkPriceImportService(db_session, today=TODAY)

    result = service.import_observations(
        benchmark_code="BIST100",
        source="VERIFIED_DATASET",
        observations=[_observation(date(2026, 9, 1), close_value)],
    )

    assert result.rows_created == 1
    assert _prices(db_session)[0].close_value == close_value


def test_import_rejects_value_requiring_scale_8_rounding(db_session: Session) -> None:
    BenchmarkRepository(db_session).add(_build_benchmark())
    service = BenchmarkPriceImportService(db_session, today=TODAY)

    with pytest.raises(ValueError):
        service.import_observations(
            benchmark_code="BIST100",
            source="VERIFIED_DATASET",
            observations=[_observation(date(2026, 9, 1), Decimal("14050.599609375"))],
        )


def test_import_rolls_back_earlier_mutations_when_later_conflict_occurs(db_session: Session) -> None:
    BenchmarkRepository(db_session).add(_build_benchmark())
    service = BenchmarkPriceImportService(db_session, today=TODAY)
    service.import_observations(
        benchmark_code="BIST100",
        source="SOURCE_A",
        observations=[_observation(date(2026, 9, 2), Decimal("102.00000000"))],
    )

    with pytest.raises(ValueError):
        service.import_observations(
            benchmark_code="BIST100",
            source="SOURCE_B",
            observations=[
                _observation(date(2026, 9, 1), Decimal("101.00000000")),
                _observation(date(2026, 9, 2), Decimal("102.00000000")),
            ],
        )

    prices = _prices(db_session)
    assert [(price.price_date, price.close_value, price.source) for price in prices] == [
        (date(2026, 9, 2), Decimal("102.00000000"), "SOURCE_A")
    ]


def test_import_rolls_back_complete_batch_on_persistence_failure(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    BenchmarkRepository(db_session).add(_build_benchmark())
    original_add = BenchmarkPriceRepository.add

    def failing_add(
        self: BenchmarkPriceRepository,
        benchmark_price: BenchmarkPrice,
    ) -> BenchmarkPrice:
        if benchmark_price.price_date == date(2026, 9, 2):
            raise RuntimeError("benchmark price add failed")
        return original_add(self, benchmark_price)

    monkeypatch.setattr(BenchmarkPriceRepository, "add", failing_add)
    service = BenchmarkPriceImportService(db_session, today=TODAY)

    with pytest.raises(RuntimeError):
        service.import_observations(
            benchmark_code="BIST100",
            source="VERIFIED_DATASET",
            observations=[
                _observation(date(2026, 9, 1), Decimal("100")),
                _observation(date(2026, 9, 2), Decimal("101")),
            ],
        )

    assert _prices(db_session) == []