from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.benchmark import Benchmark


class BenchmarkRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, benchmark: Benchmark) -> Benchmark:
        self.db.add(benchmark)
        self.db.flush()
        return benchmark

    def get_by_id(self, benchmark_id: int) -> Benchmark | None:
        return self.db.get(Benchmark, benchmark_id)

    def get_by_code(self, code: str) -> Benchmark | None:
        statement = select(Benchmark).where(Benchmark.code == code)
        return self.db.scalar(statement)

    def list_active(self) -> list[Benchmark]:
        statement = (
            select(Benchmark)
            .where(Benchmark.is_active.is_(True))
            .order_by(Benchmark.code.asc(), Benchmark.id.asc())
        )
        return list(self.db.scalars(statement))
