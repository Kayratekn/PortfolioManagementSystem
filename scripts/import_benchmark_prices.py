from __future__ import annotations

import argparse
from collections.abc import Sequence
import csv
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.database import SessionLocal
from src.services.benchmark_price_import_parser import parse_benchmark_price_rows
from src.services.benchmark_price_import_service import BenchmarkPriceImportService


def readable_file(value: str) -> Path:
    path = Path(value)
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"file not found: {value}")
    return path


def nonblank(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("value must not be blank")
    if value.strip() != value:
        raise argparse.ArgumentTypeError("value must not include surrounding whitespace")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import benchmark historical close prices from CSV.")
    parser.add_argument("--benchmark-code", required=True, type=nonblank)
    parser.add_argument("--source", required=True, type=nonblank)
    parser.add_argument("--file", required=True, type=readable_file)
    parser.add_argument("--allow-revisions", action="store_true", default=False)
    return parser


def read_canonical_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise ValueError("CSV must include a header row.")
        missing_headers = [header for header in ("date", "close") if header not in fieldnames]
        if missing_headers:
            raise ValueError(f"CSV missing required header(s): {', '.join(missing_headers)}.")

        rows: list[dict[str, str]] = []
        for row_number, row in enumerate(reader, start=2):
            if row.get(None):
                raise ValueError(f"CSV row {row_number} has too many columns.")
            date_value = row.get("date")
            close_value = row.get("close")
            if date_value is None or close_value is None:
                raise ValueError(f"CSV row {row_number} is missing required values.")
            rows.append({"date": date_value, "close": close_value})
        return rows


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        rows = read_canonical_csv(args.file)
        observations = parse_benchmark_price_rows(rows)
    except Exception as exc:
        print(f"Benchmark CSV import failed: {exc}", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        result = BenchmarkPriceImportService(db).import_observations(
            benchmark_code=args.benchmark_code,
            source=args.source,
            observations=observations,
            allow_revisions=args.allow_revisions,
        )
        print("Benchmark price import completed")
        print(f"benchmark_code: {args.benchmark_code}")
        print(f"source: {args.source}")
        print(f"canonical_rows_read: {len(rows)}")
        print(f"fetched_rows: {result.fetched_rows}")
        print(f"rows_created: {result.rows_created}")
        print(f"rows_updated: {result.rows_updated}")
        return 0
    except Exception as exc:
        print(f"Benchmark CSV import failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
