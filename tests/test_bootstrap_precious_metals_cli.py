from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from src.model.asset import Asset
from src.services.precious_metal_catalog_bootstrap_service import (
    PreciousMetalCatalogBootstrapConflictError,
    PreciousMetalCatalogBootstrapService,
)


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_precious_metals.py"
spec = importlib.util.spec_from_file_location("bootstrap_precious_metals_cli", SCRIPT_PATH)
bootstrap_cli = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(bootstrap_cli)


def test_help_succeeds_without_opening_database_or_invoking_bootstrap(monkeypatch, capsys) -> None:
    class UnexpectedSessionFactory:
        def __call__(self):
            raise AssertionError("--help must not open a database session")

    monkeypatch.setattr(bootstrap_cli, "SessionLocal", UnexpectedSessionFactory())
    monkeypatch.setattr(
        bootstrap_cli,
        "PreciousMetalCatalogBootstrapService",
        lambda _db: (_ for _ in ()).throw(AssertionError("bootstrap must not run for --help")),
    )

    with pytest.raises(SystemExit) as exit_info:
        bootstrap_cli.main(["--help"])
    assert exit_info.value.code == 0
    captured = capsys.readouterr()
    assert "usage:" in captured.out.lower()
    assert captured.err == ""


def test_normal_execution_still_runs_bootstrap(monkeypatch) -> None:
    calls: list[str] = []

    class FakeSession:
        def close(self) -> None:
            calls.append("close")

    class FakeService:
        def __init__(self, db) -> None:
            assert isinstance(db, FakeSession)
            calls.append("construct")

        def bootstrap(self):
            calls.append("bootstrap")
            return type("Result", (), {"assets_created": 3, "assets_skipped": 0})()

    monkeypatch.setattr(bootstrap_cli, "SessionLocal", FakeSession)
    monkeypatch.setattr(bootstrap_cli, "PreciousMetalCatalogBootstrapService", FakeService)

    assert bootstrap_cli.main([]) == 0
    assert calls == ["construct", "bootstrap", "close"]


def test_catalog_bootstrap_remains_idempotent_and_conflicts_unchanged(db_session) -> None:
    service = PreciousMetalCatalogBootstrapService(db_session)
    first = service.bootstrap()
    second = service.bootstrap()

    assert (first.assets_created, first.assets_skipped) == (3, 0)
    assert (second.assets_created, second.assets_skipped) == (0, 3)

    canonical_gold = db_session.query(Asset).filter_by(
        data_source="BORSA_ISTANBUL", asset_code="GOLD"
    ).one()
    canonical_gold.asset_name = "Incompatible Gold"
    db_session.commit()

    with pytest.raises(PreciousMetalCatalogBootstrapConflictError):
        service.bootstrap()

    db_session.refresh(canonical_gold)
    assert canonical_gold.asset_name == "Incompatible Gold"