"""Точка входа для новой multi-source архитектуры.

Запуск:
    python src/app.py
    python src/app.py --dry-run
    python src/app.py --fail-on-no-sources --fail-on-no-apps
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build GBox catalog from multiple IPA sources"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and fetch only; do not write catalog",
    )
    parser.add_argument(
        "--fail-on-no-sources",
        action="store_true",
        help="Exit with error if no enabled sources are configured",
    )
    parser.add_argument(
        "--fail-on-no-apps",
        action="store_true",
        help="Exit with error if no exportable apps were produced",
    )
    parser.add_argument(
        "--sources",
        metavar="PATH",
        default=None,
        help="Path to sources.json (default: config/sources.json)",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default=None,
        help="Path to output catalog.json (default: output/catalog.json)",
    )
    args = parser.parse_args()

    # Импорт здесь, чтобы ошибки импорта не мешали --help
    try:
        from src.orchestrator import run
    except ModuleNotFoundError:
        from orchestrator import run  # type: ignore[no-redef]

    sources_path = Path(args.sources) if args.sources else None
    output_path = Path(args.output) if args.output else None

    return run(
        dry_run=args.dry_run,
        fail_on_no_sources=args.fail_on_no_sources,
        fail_on_no_apps=args.fail_on_no_apps,
        sources_path=sources_path,
        output_path=output_path,
    )


if __name__ == "__main__":
    sys.exit(main())
