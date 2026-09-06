from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.database import SessionLocal
from src.config.supported_benchmarks import SUPPORTED_BENCHMARKS
from src.services.benchmark_daily_sync_service import BenchmarkDailySyncService


ISTANBUL_TIMEZONE = timezone(timedelta(hours=3), "Europe/Istanbul")


def current_date(now: datetime | None = None) -> date:
    reference_time = now or datetime.now(timezone.utc)
    if reference_time.tzinfo is None:
        raise ValueError("current_date requires an aware datetime when now is supplied.")
    return reference_time.astimezone(ISTANBUL_TIMEZONE).date()


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO date: {value}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync supported benchmark daily close prices.")
    parser.add_argument("--code", choices=tuple(SUPPORTED_BENCHMARKS.keys()))
    parser.add_argument("--reference-date", type=parse_iso_date)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    operational_today = current_date()
    reference_date = args.reference_date or operational_today
    if reference_date > operational_today:
        parser.error(
            "--reference-date must not be after the current Europe/Istanbul date "
            f"({operational_today.isoformat()})"
        )
    benchmark_codes = [args.code] if args.code else list(SUPPORTED_BENCHMARKS.keys())

    print("Benchmark scheduled sync")
    print(f"reference_date: {reference_date.isoformat()}")
    print(f"benchmark_codes: {', '.join(benchmark_codes)}")

    failed = False
    for benchmark_code in benchmark_codes:
        db = SessionLocal()
        try:
            result = BenchmarkDailySyncService(db).sync(
                benchmark_code=benchmark_code,
                reference_date=reference_date,
            )
            print(
                f"{benchmark_code}: ok "
                f"symbol={result.provider_symbol} "
                f"range=[{result.start_date.isoformat()}, {result.end_date.isoformat()}) "
                f"fetched_rows={result.fetched_rows} "
                f"rows_created={result.rows_created} "
                f"rows_updated={result.rows_updated}"
            )
        except Exception as exc:
            failed = True
            print(f"{benchmark_code}: failed {exc}", file=sys.stderr)
        finally:
            db.close()

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
