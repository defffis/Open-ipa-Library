from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.adapters.armconverter_html import ArmConverterHtmlAdapter
from src.adapters.decrypt_day_html import DecryptDayHtmlAdapter
from src.adapters.playcover_json import PlayCoverJsonAdapter
from src.adapters.static_json_mirror import StaticJsonMirrorAdapter
from src.models.canonical import CanonicalApp
from src.models.reports import RunReport, SourceStatus
from src.models.source_config import SourceConfig
from src.registry import load_enabled_sources
from src.services.deduplicator import deduplicate
from src.services.exporter_gbox import build_gbox_catalog, write_if_changed
from src.services.reporter import write_run_report, write_sources_status
from src.services.validator import validate_apps

_ADAPTER_MAP = {
    "playcover_json": PlayCoverJsonAdapter,
    "decrypt_day_html": DecryptDayHtmlAdapter,
    "armconverter_html": ArmConverterHtmlAdapter,
    "static_json_mirror": StaticJsonMirrorAdapter,
}


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _make_adapter(source: SourceConfig) -> Any:
    cls = _ADAPTER_MAP.get(source.adapter)
    if cls is None:
        raise ValueError(f"Unknown adapter '{source.adapter}' for source '{source.id}'")
    return cls(source)


def run(
    *,
    dry_run: bool = False,
    fail_on_no_sources: bool = False,
    fail_on_no_apps: bool = False,
    sources_path: Path | None = None,
    output_path: Path | None = None,
    report_path: Path = Path("output/last-run.json"),
    status_path: Path = Path("output/sources-status.json"),
) -> int:
    updated_at = _iso_utc_now()
    output_path = output_path or Path(os.getenv("OUTPUT_PATH", "output/catalog.json"))

    # Загружаем источники
    try:
        sources = load_enabled_sources(sources_path)
    except Exception as exc:  # noqa: BLE001
        report = RunReport(
            updated_at=updated_at,
            status="error",
            message=f"Failed to load sources: {exc}",
            errors=[{"error": str(exc)}],
        )
        write_run_report(report, report_path)
        print(_report_json(report))
        if fail_on_no_sources:
            raise
        return 1

    if not sources:
        report = RunReport(
            updated_at=updated_at,
            status="skipped",
            message="No enabled sources found in config/sources.json.",
        )
        write_run_report(report, report_path)
        print(_report_json(report))
        if fail_on_no_sources:
            raise RuntimeError("No enabled sources found.")
        return 0

    # Обходим источники
    all_apps: list[CanonicalApp] = []
    source_statuses: list[SourceStatus] = []
    run_errors: list[dict[str, str]] = []

    sources_ok = 0
    sources_partial = 0
    sources_error = 0

    for source in sources:
        try:
            adapter = _make_adapter(source)
        except ValueError as exc:
            run_errors.append({"sourceId": source.id, "error": str(exc)})
            sources_error += 1
            source_statuses.append(SourceStatus(
                source_id=source.id,
                source_name=source.name,
                status="error",
                error=str(exc),
            ))
            continue

        result = adapter.fetch()

        # Метим приложения приоритетом источника для дедупликации
        for app in result.apps:
            app.raw["_source_priority"] = source.priority

        all_apps.extend(result.apps)

        exportable_count = sum(1 for a in result.apps if a.is_exportable)

        if result.success and result.apps:
            sources_ok += 1
            status = "ok"
        elif result.success and not result.apps:
            sources_partial += 1
            status = "partial"
        else:
            sources_error += 1
            status = "error"
            run_errors.append({"sourceId": source.id, "error": result.error or "unknown error"})

        source_statuses.append(SourceStatus(
            source_id=source.id,
            source_name=source.name,
            status=status,
            apps_found=result.apps_found,
            apps_exportable=exportable_count,
            error=result.error,
        ))

    apps_found = len(all_apps)

    # Валидация
    valid_apps, _warnings = validate_apps(all_apps)
    apps_normalized = len(valid_apps)
    apps_dropped = apps_found - apps_normalized

    # Дедупликация
    deduped, duplicates_removed = deduplicate(valid_apps)
    apps_exportable = sum(1 for a in deduped if a.is_exportable)

    # Нет экспортируемых приложений
    if not any(a.is_exportable for a in deduped):
        report = RunReport(
            updated_at=updated_at,
            status="partial",
            sources_processed=len(sources),
            sources_ok=sources_ok,
            sources_partial=sources_partial,
            sources_error=sources_error,
            apps_found=apps_found,
            apps_normalized=apps_normalized,
            apps_exportable=0,
            apps_dropped=apps_dropped,
            duplicates_removed=duplicates_removed,
            output_changed=False,
            dry_run=dry_run,
            message="No exportable apps (with download_url and availability=public). Existing catalog preserved.",
            source_statuses=source_statuses,
            errors=run_errors,
        )
        write_run_report(report, report_path)
        write_sources_status(source_statuses, status_path)
        print(_report_json(report))
        if fail_on_no_apps:
            raise RuntimeError("No exportable apps produced from all sources.")
        return 0

    # Сборка и запись каталога
    try:
        catalog = build_gbox_catalog(deduped, updated_at)
    except ValueError as exc:
        report = RunReport(
            updated_at=updated_at,
            status="error",
            message=f"Catalog validation failed: {exc}",
            errors=[{"error": str(exc)}],
        )
        write_run_report(report, report_path)
        print(_report_json(report))
        return 1

    changed = False if dry_run else write_if_changed(output_path, catalog)

    report = RunReport(
        updated_at=updated_at,
        status="ok",
        sources_processed=len(sources),
        sources_ok=sources_ok,
        sources_partial=sources_partial,
        sources_error=sources_error,
        apps_found=apps_found,
        apps_normalized=apps_normalized,
        apps_exportable=apps_exportable,
        apps_dropped=apps_dropped,
        duplicates_removed=duplicates_removed,
        output_changed=changed,
        dry_run=dry_run,
        source_statuses=source_statuses,
        errors=run_errors,
    )

    write_run_report(report, report_path)
    write_sources_status(source_statuses, status_path)
    print(_report_json(report))
    return 0


def _report_json(report: RunReport) -> str:
    import json
    return json.dumps(report.to_dict(), ensure_ascii=False)
