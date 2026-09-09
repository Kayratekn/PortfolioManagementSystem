from datetime import date
import importlib.util
from pathlib import Path

from sqlalchemy.orm import Session

from src.integrations.borsa_istanbul_reference_prices_client import BorsaIstanbulHistoricalObservation
from src.model.asset_price import AssetPrice
from src.services.precious_metal_catalog_bootstrap_service import PreciousMetalCatalogBootstrapService


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "backfill_borsa_istanbul_precious_metals.py"
spec = importlib.util.spec_from_file_location("bist_backfill_cli", SCRIPT_PATH)
cli = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(cli)


class Client:
    def __init__(self, fail=False): self.fail = fail
    def fetch_historical(self, *, start_date, end_date, provider_metal_code):
        if self.fail: raise RuntimeError("transport failed")
        if provider_metal_code == "AU": return [BorsaIstanbulHistoricalObservation("AU", start_date, 1000)]
        return []


def factory_for(session): return lambda: Session(bind=session.get_bind())


def test_cli_dry_run_does_not_write_and_apply_writes(db_session):
    PreciousMetalCatalogBootstrapService(db_session).bootstrap()
    args=["--start-date","2026-09-08","--end-date","2026-09-08","--metal","GOLD"]
    assert cli.main(args, session_factory=factory_for(db_session), client_factory=Client) == 0
    assert db_session.query(AssetPrice).count() == 0
    assert cli.main([*args,"--apply"], session_factory=factory_for(db_session), client_factory=Client) == 0
    assert db_session.query(AssetPrice).count() == 1


def test_cli_requires_dates_validates_arguments_and_returns_nonzero_on_failure(db_session):
    try:
        cli.main(["--start-date","not-a-date","--end-date","2026-09-08"], session_factory=factory_for(db_session), client_factory=Client)
    except SystemExit as exc:
        assert exc.code != 0
    else:
        raise AssertionError("expected argparse failure")
    assert cli.main(["--start-date","2026-09-08","--end-date","2026-09-08"], session_factory=factory_for(db_session), client_factory=lambda: Client(fail=True)) == 1