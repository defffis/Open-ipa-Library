from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.models.reports import RunReport, SourceStatus


def write_run_report(report: RunReport, path: Path = Path("output/last-run.json")) -> None:
    """Записывает RunReport в JSON-файл."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_sources_status(
    statuses: list[SourceStatus],
    path: Path = Path("output/sources-status.json"),
) -> None:
    """Записывает статусы источников в JSON-файл."""
    payload: list[dict[str, Any]] = [
        {
            "sourceId": s.source_id,
            "sourceName": s.source_name,
            "status": s.status,
            "appsFound": s.apps_found,
            "appsExportable": s.apps_exportable,
            "error": s.error,
        }
        for s in statuses
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
