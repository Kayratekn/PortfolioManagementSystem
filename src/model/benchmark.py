from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Integer, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column, validates

from src.model.base import Base, TimestampMixin


class Benchmark(TimestampMixin, Base):
    __tablename__ = "benchmarks"
    __table_args__ = (
        UniqueConstraint("code", name="uq_benchmarks_code"),
        UniqueConstraint(
            "provider",
            "provider_symbol",
            name="uq_benchmarks_provider_provider_symbol",
        ),
        CheckConstraint(
            "benchmark_type IN ('MARKET_INDEX', 'TEFAS_FUND')",
            name="ck_benchmarks_benchmark_type_allowed",
        ),
        CheckConstraint(
            "length(native_currency) = 3 "
            "AND native_currency = upper(native_currency) "
            "AND substr(native_currency, 1, 1) BETWEEN 'A' AND 'Z' "
            "AND substr(native_currency, 2, 1) BETWEEN 'A' AND 'Z' "
            "AND substr(native_currency, 3, 1) BETWEEN 'A' AND 'Z'",
            name="ck_benchmarks_native_currency_uppercase_3",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    benchmark_type: Mapped[str] = mapped_column(String(20), nullable=False)
    native_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_symbol: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    @validates("native_currency")
    def validate_native_currency(self, _key: str, value: str) -> str:
        normalized_value = value.strip().upper() if isinstance(value, str) else ""
        if (
            len(normalized_value) != 3
            or not normalized_value.isascii()
            or not normalized_value.isalpha()
        ):
            raise ValueError("native_currency must be a 3-character uppercase currency code.")
        return normalized_value
