from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.database import SessionLocal
from src.services.precious_metal_catalog_bootstrap_service import (
    PreciousMetalCatalogBootstrapService,
)


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="Bootstrap the canonical Borsa Istanbul precious-metal assets."
    )


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    db = SessionLocal()
    try:
        result = PreciousMetalCatalogBootstrapService(db).bootstrap()
        print(f"assets_created: {result.assets_created}")
        print(f"assets_skipped: {result.assets_skipped}")
        return 0
    except Exception as exc:
        print(f"Precious-metal catalog bootstrap failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())