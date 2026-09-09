from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.database import SessionLocal
from src.integrations.borsa_istanbul_current_reference_prices_client import (
    BorsaIstanbulCurrentReferencePricesClient,
)
from src.repositories.data_sync_run_repository import DataSyncRunRepository
from src.services.borsa_istanbul_daily_reference_price_sync_service import (
    BorsaIstanbulDailyReferencePriceSyncService,
)
from src.services.data_sync_run_service import (
    SYNC_TYPE_BIST_REFERENCE_PRICES_DAILY,
    DataSyncRunService,
)


ISTANBUL_TIMEZONE = timezone(timedelta(hours=3), "Europe/Istanbul")


def current_date(now: datetime | None = None):
    reference_time = now or datetime.now(timezone.utc)
    if reference_time.tzinfo is None:
        raise ValueError("current_date requires an aware datetime when now is supplied.")
    return reference_time.astimezone(ISTANBUL_TIMEZONE).date()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_data_sync_run_service(db) -> DataSyncRunService:
    return DataSyncRunService(db=db, repository=DataSyncRunRepository(db))


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="Sync the current Borsa Istanbul precious-metal reference-price snapshot."
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    session_factory=SessionLocal,
    client_factory=BorsaIstanbulCurrentReferencePricesClient,
) -> int:
    build_parser().parse_args(argv)
    print("Borsa Istanbul reference-price scheduled sync")
    print(f"execution_date: {current_date().isoformat()}")

    audit_db = session_factory()
    try:
        audit_service = build_data_sync_run_service(audit_db)
        run_id = audit_service.start(SYNC_TYPE_BIST_REFERENCE_PRICES_DAILY, utc_now())
        work_db = session_factory()
        try:
            result = BorsaIstanbulDailyReferencePriceSyncService(
                work_db,
                client_factory(),
            ).sync()
        except Exception as exc:
            audit_service.mark_failed(run_id, "BIST current reference-price sync failed.", utc_now())
            print(f"BIST current reference-price sync failed: {exc}", file=sys.stderr)
            return 1
        finally:
            work_db.close()

        audit_service.mark_success(run_id, utc_now())
        print(f"effective_date: {result.effective_date.isoformat()}")
        print(f"provider_observations: {result.provider_observations}")
        print(f"rows_inserted: {result.rows_inserted}")
        print(f"rows_skipped: {result.rows_skipped}")
        return 0
    finally:
        audit_db.close()


if __name__ == "__main__":
    sys.exit(main())