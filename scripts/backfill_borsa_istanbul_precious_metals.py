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
from src.config.supported_precious_metals import SUPPORTED_PRECIOUS_METALS
from src.integrations.borsa_istanbul_reference_prices_client import BorsaIstanbulReferencePricesClient
from src.services.borsa_istanbul_historical_backfill_service import DEFAULT_BATCH_DAYS, BorsaIstanbulHistoricalBackfillService


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO date: {value}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill Borsa Istanbul precious-metal reference prices.")
    parser.add_argument("--start-date", required=True, type=parse_iso_date)
    parser.add_argument("--end-date", required=True, type=parse_iso_date)
    parser.add_argument("--metal", action="append", choices=tuple(SUPPORTED_PRECIOUS_METALS))
    parser.add_argument("--batch-days", type=int, default=DEFAULT_BATCH_DAYS)
    parser.add_argument("--apply", action="store_true", help="Persist validated observations. Default is dry-run.")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    session_factory=SessionLocal,
    client_factory=BorsaIstanbulReferencePricesClient,
) -> int:
    args = build_parser().parse_args(argv)
    db = session_factory()
    try:
        result = BorsaIstanbulHistoricalBackfillService(db, client_factory()).backfill(
            start_date=args.start_date,
            end_date=args.end_date,
            asset_codes=tuple(args.metal or SUPPORTED_PRECIOUS_METALS.keys()),
            batch_days=args.batch_days,
            apply=args.apply,
        )
        print(f"mode: {'apply' if args.apply else 'dry-run'}")
        print(f"provider_observations: {result.provider_observations}")
        print(f"rows_inserted: {result.rows_inserted}")
        print(f"rows_skipped: {result.rows_skipped}")
        print(f"batches_completed: {result.batches_completed}")
        return 0
    except Exception as exc:
        print(f"BIST precious-metal backfill failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
