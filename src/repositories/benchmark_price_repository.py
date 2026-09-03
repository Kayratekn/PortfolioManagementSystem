from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.benchmark_price import BenchmarkPrice


class BenchmarkPriceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, benchmark_price: BenchmarkPrice) -> BenchmarkPrice:
        self.db.add(benchmark_price)
        self.db.flush()
        return benchmark_price

    def get_by_benchmark_and_date(
        self,
        *,
        benchmark_id: int,
        price_date: date,
    ) -> BenchmarkPrice | None:
        statement = select(BenchmarkPrice).where(
            BenchmarkPrice.benchmark_id == benchmark_id,
            BenchmarkPrice.price_date == price_date,
        )
        return self.db.scalar(statement)

    def list_by_benchmark_between(
        self,
        *,
        benchmark_id: int,
        start_date: date,
        end_date: date,
    ) -> list[BenchmarkPrice]:
        statement = (
            select(BenchmarkPrice)
            .where(
                BenchmarkPrice.benchmark_id == benchmark_id,
                BenchmarkPrice.price_date >= start_date,
                BenchmarkPrice.price_date <= end_date,
            )
            .order_by(BenchmarkPrice.price_date.asc(), BenchmarkPrice.id.asc())
        )
        return list(self.db.scalars(statement))

    def get_latest_on_or_before(
        self,
        *,
        benchmark_id: int,
        price_date: date,
    ) -> BenchmarkPrice | None:
        statement = (
            select(BenchmarkPrice)
            .where(
                BenchmarkPrice.benchmark_id == benchmark_id,
                BenchmarkPrice.price_date <= price_date,
            )
            .order_by(BenchmarkPrice.price_date.desc(), BenchmarkPrice.id.desc())
            .limit(1)
        )
        return self.db.scalar(statement)
