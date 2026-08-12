from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import date, datetime, timezone
from pathlib import Path
import sys
from typing import get_args

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.database import SessionLocal
from src.integrations.tefas_client import FundKind
from src.services.tefas_fetch_log_service import TefasFetchLogService
from src.services.tefas_sync_service import TefasSyncService


MVP_FUND_KINDS = ("YAT",)
SYNC_FUND_KINDS = tuple(get_args(FundKind))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)



def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO date: {value}") from exc



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run TEFAS synchronization.")
    parser.add_argument("--date", dest="data_date", type=parse_iso_date)
    parser.add_argument("--start-date", dest="start_date", type=parse_iso_date)
    parser.add_argument("--end-date", dest="end_date", type=parse_iso_date)
    parser.add_argument("--kind", default="YAT", choices=SYNC_FUND_KINDS)
    parser.add_argument("--fund-code", dest="fund_code", default=None)
    return parser



def select_requested_date_range(args: argparse.Namespace, parser: argparse.ArgumentParser) -> tuple[date, date, bool]:
    has_date = args.data_date is not None
    has_start_date = args.start_date is not None
    has_end_date = args.end_date is not None
    has_range = has_start_date or has_end_date

    if has_date and has_range:
        parser.error("--date cannot be combined with --start-date or --end-date")
    if has_start_date != has_end_date:
        parser.error("--start-date and --end-date must be provided together")
    if not has_date and not has_range:
        parser.error("either --date or --start-date/--end-date is required")

    if has_date:
        return args.data_date, args.data_date, False

    if args.start_date > args.end_date:
        parser.error("--start-date cannot be later than --end-date")
    if args.fund_code is None or not args.fund_code.strip():
        parser.error("--fund-code is required when --start-date and --end-date are used")

    return args.start_date, args.end_date, True



def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    start_date, end_date, is_range_mode = select_requested_date_range(args, parser)

    sync_session = SessionLocal()
    log_session = SessionLocal()
    try:
        sync_service = TefasSyncService(sync_session)
        fetch_log_service = TefasFetchLogService(log_session)

        try:
            fetch_log_id = fetch_log_service.start(
                fund_kind=args.kind,
                fund_code=args.fund_code,
                start_date=start_date,
                end_date=end_date,
                started_at=utc_now(),
            )
        except Exception as exc:
            print(f"TEFAS fetch log start failed: {exc}", file=sys.stderr)
            return 1

        try:
            result = sync_service.sync_general_info(
                start_date=start_date,
                end_date=end_date,
                fund_kind=args.kind,
                fund_code=args.fund_code,
            )
        except Exception as exc:
            try:
                fetch_log_service.mark_failed(
                    fetch_log_id=fetch_log_id,
                    error_message=str(exc),
                    completed_at=utc_now(),
                )
            except Exception as log_exc:
                print(f"TEFAS fetch log update failed: {log_exc}", file=sys.stderr)
                print(f"TEFAS sync failed: {exc}", file=sys.stderr)
                return 1

            print(f"TEFAS sync failed: {exc}", file=sys.stderr)
            return 1

        try:
            fetch_log_service.mark_success(
                fetch_log_id=fetch_log_id,
                fetched_rows=result.fetched_rows,
                assets_created=result.assets_created,
                assets_updated=result.assets_updated,
                daily_rows_created=result.daily_rows_created,
                daily_rows_updated=result.daily_rows_updated,
                completed_at=utc_now(),
            )
        except Exception as exc:
            print(f"TEFAS fetch log update failed: {exc}", file=sys.stderr)
            return 1

        print("TEFAS sync completed successfully")
        if is_range_mode:
            print(f"start date: {start_date.isoformat()}")
            print(f"end date: {end_date.isoformat()}")
        else:
            print(f"date: {start_date.isoformat()}")
        print(f"fund kind: {args.kind}")
        print(f"fund code: {args.fund_code}")
        print(f"fetched_rows: {result.fetched_rows}")
        print(f"assets_created: {result.assets_created}")
        print(f"assets_updated: {result.assets_updated}")
        print(f"daily_rows_created: {result.daily_rows_created}")
        print(f"daily_rows_updated: {result.daily_rows_updated}")
        return 0
    finally:
        sync_session.close()
        log_session.close()


if __name__ == "__main__":
    sys.exit(main())
