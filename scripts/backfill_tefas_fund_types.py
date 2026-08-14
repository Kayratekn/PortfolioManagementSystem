from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.database import SessionLocal
from src.integrations.tefas_client import CustomTefasClient
from src.repositories.asset_repository import AssetRepository
from src.repositories.tefas_fund_type_history_repository import TefasFundTypeHistoryRepository
from src.services.tefas_fund_type_backfill_service import (
    TefasFundTypeBackfillResult,
    TefasFundTypeBackfillService,
)
from src.services.tefas_fund_type_history_service import TefasFundTypeHistoryService
from src.services.tefas_service import TefasService


FUND_KINDS = ("YAT", "EMK", "BYF", "GYF", "GSYF")


def parse_positive_int(value: str) -> int:
    try:
        parsed_value = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid positive integer: {value}") from exc
    if parsed_value <= 0:
        raise argparse.ArgumentTypeError("limit must be positive")
    return parsed_value


def parse_nonnegative_float(value: str) -> float:
    try:
        parsed_value = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid nonnegative float: {value}") from exc
    if parsed_value < 0:
        raise argparse.ArgumentTypeError("delay_seconds must be greater than or equal to 0")
    return parsed_value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Controlled TEFAS fund-type backfill for funds missing current history."
    )
    parser.add_argument("--kind", required=True, choices=FUND_KINDS)
    parser.add_argument("--limit", required=True, type=parse_positive_int)
    parser.add_argument(
        "--delay-seconds",
        dest="delay_seconds",
        type=parse_nonnegative_float,
        default=1.0,
    )
    return parser


def build_backfill_service(db) -> TefasFundTypeBackfillService:
    asset_repository = AssetRepository(db)
    fund_type_history_repository = TefasFundTypeHistoryRepository(db)
    tefas_client = CustomTefasClient()
    tefas_service = TefasService(tefas_client)
    fund_type_history_service = TefasFundTypeHistoryService(
        db,
        asset_repository=asset_repository,
        fund_type_history_repository=fund_type_history_repository,
        tefas_service=tefas_service,
    )
    return TefasFundTypeBackfillService(
        asset_repository=asset_repository,
        fund_type_history_service=fund_type_history_service,
    )


def print_result(result: TefasFundTypeBackfillResult) -> None:
    print("TEFAS fund-type backfill completed")
    print(f"fund_kind: {result.fund_kind}")
    print(f"limit: {result.limit}")
    print(f"attempted_count: {result.attempted_count}")
    print(f"succeeded_count: {result.succeeded_count}")
    print(f"failed_count: {result.failed_count}")
    print(f"created_count: {result.created_count}")
    print(f"unchanged_count: {result.unchanged_count}")
    print(f"changed_count: {result.changed_count}")
    for failure in result.failures:
        print(
            "failure: "
            f"fund_code={failure.fund_code} "
            f"error_type={failure.error_type} "
            f"message={failure.message}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        backfill_service = build_backfill_service(db)
        result = backfill_service.backfill_missing_active_tefas_funds(
            fund_kind=args.kind,
            limit=args.limit,
            delay_seconds=args.delay_seconds,
        )
        print_result(result)
        return 1 if result.failed_count > 0 else 0
    except Exception as exc:
        print(f"TEFAS fund-type backfill failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
