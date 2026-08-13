from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.database import SessionLocal
from src.integrations.tefas_client import CustomTefasClient
from src.repositories.asset_repository import AssetRepository
from src.repositories.tefas_fund_type_history_repository import TefasFundTypeHistoryRepository
from src.services.tefas_fund_type_history_service import TefasFundTypeHistoryService
from src.services.tefas_fund_type_refresh_service import (
    TefasFundTypeRefreshResult,
    TefasFundTypeRefreshService,
)
from src.services.tefas_service import TefasService


def build_refresh_service(db) -> TefasFundTypeRefreshService:
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
    return TefasFundTypeRefreshService(
        asset_repository=asset_repository,
        fund_type_history_service=fund_type_history_service,
    )


def print_result(result: TefasFundTypeRefreshResult) -> None:
    print("TEFAS fund-type refresh completed")
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


def main() -> int:
    db = SessionLocal()
    try:
        refresh_service = build_refresh_service(db)
        result = refresh_service.refresh_active_tefas_funds()
        print_result(result)
        return 1 if result.failed_count > 0 else 0
    except Exception as exc:
        print(f"TEFAS fund-type refresh failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
