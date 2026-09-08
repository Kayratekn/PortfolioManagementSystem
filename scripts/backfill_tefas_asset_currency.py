from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.database import SessionLocal
from src.repositories.asset_repository import AssetRepository
from src.services.tefas_asset_currency_backfill_service import (
    TefasAssetCurrencyBackfillResult,
    TefasAssetCurrencyBackfillService,
    TefasAssetCurrencyConflictError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill NULL TEFAS asset currencies to TRY."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the backfill. Without this flag, the script is a dry run.",
    )
    return parser


def print_result(result: TefasAssetCurrencyBackfillResult) -> None:
    print(f"tefas_null_currency_count: {result.null_currency_count}")
    print(f"tefas_try_currency_count: {result.try_currency_count}")
    print(
        "tefas_non_null_non_try_conflict_count: "
        f"{result.non_try_currency_conflict_count}"
    )
    print(f"applied: {result.applied}")
    print(f"affected_count: {result.affected_count}")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db = SessionLocal()
    try:
        service = TefasAssetCurrencyBackfillService(
            db=db,
            asset_repository=AssetRepository(db),
        )
        preflight = service.inspect()
        print_result(preflight)
        if not args.apply:
            return 0
        if preflight.non_try_currency_conflict_count:
            print("Backfill aborted: resolve non-TRY TEFAS currencies first.", file=sys.stderr)
            return 1
        print_result(service.apply())
        return 0
    except TefasAssetCurrencyConflictError as exc:
        print(f"Backfill aborted: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"TEFAS asset currency backfill failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())