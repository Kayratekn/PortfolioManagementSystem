from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.database import SessionLocal
from src.config.supported_benchmarks import SUPPORTED_BENCHMARKS
from src.services.benchmark_bootstrap_service import BenchmarkBootstrapService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap supported benchmark metadata.")
    parser.add_argument("--code", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    metadata = SUPPORTED_BENCHMARKS.get(args.code)
    if metadata is None:
        print(f"Unsupported benchmark code: {args.code}", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        result = BenchmarkBootstrapService(db).bootstrap(metadata)
        print(result.status)
        return 0
    except Exception as exc:
        print(f"Benchmark bootstrap failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
