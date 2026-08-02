from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import date
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.database import SessionLocal
from src.services.tefas_sync_service import TefasSyncService


MVP_FUND_KINDS = ("YAT",)


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

    session = SessionLocal()
    try:
        service = TefasSyncService(session)
        result = service.sync_general_info(
            start_date=args.data_date,
            end_date=args.data_date,
            fund_kind=args.kind,
            fund_code=args.fund_code,
        )
    except Exception as exc:
        print(f"TEFAS sync failed: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()

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


if __name__ == "__main__":
    sys.exit(main())
