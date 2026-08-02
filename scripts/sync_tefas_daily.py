from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import date, datetime, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.database import SessionLocal
from src.services.tefas_fetch_log_service import TefasFetchLogService
from src.services.tefas_sync_service import TefasSyncService


MVP_FUND_KINDS = ("YAT",)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)



def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO date: {value}") from exc



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one-day TEFAS synchronization.")
    parser.add_argument("--date", dest="data_date", required=True, type=parse_iso_date)
    parser.add_argument("--kind", default="YAT", choices=MVP_FUND_KINDS)
    parser.add_argument("--fund-code", dest="fund_code", default=None)
    return parser



def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    sync_session = SessionLocal()
    log_session = SessionLocal()
    try:
        sync_service = TefasSyncService(sync_session)
        fetch_log_service = TefasFetchLogService(log_session)

        try:
            fetch_log_id = fetch_log_service.start(
                fund_kind=args.kind,
                fund_code=args.fund_code,
                start_date=args.data_date,
                end_date=args.data_date,
                started_at=utc_now(),
            )
        except Exception as exc:
            print(f"TEFAS fetch log start failed: {exc}", file=sys.stderr)
            return 1

        try:
            result = sync_service.sync_general_info(
                start_date=args.data_date,
                end_date=args.data_date,
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
        print(f"date: {args.data_date.isoformat()}")
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
