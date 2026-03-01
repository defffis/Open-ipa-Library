from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from src.mappers.playcover_to_gbox import PlayCoverApp, iso_utc_now, map_app_to_gbox
    from src.validators import validate_gbox_catalog
except ModuleNotFoundError:
    from mappers.playcover_to_gbox import PlayCoverApp, iso_utc_now, map_app_to_gbox
    from validators import validate_gbox_catalog


@dataclass
class ConvertStats:
    sources_total: int = 0
    sources_ok: int = 0
    apps_seen: int = 0
    apps_valid: int = 0
    duplicates_removed: int = 0
    errors: int = 0


def parse_sources(raw: str) -> list[str]:
    raw = (raw or "").strip()
    if not raw:
        return []

    if raw.startswith("["):
        maybe_json = json.loads(raw)
        if not isinstance(maybe_json, list):
            raise ValueError("PLAYCOVER_SOURCES JSON must be an array of URLs")
        return [str(url).strip() for url in maybe_json if str(url).strip()]

    sources: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if line:
            sources.append(line)
    return sources


def _summarize_non_json(content: str) -> str:
    snippet = " ".join(content.strip().split())[:140]
    lower = content.lower()
    if "just a moment" in lower or "cf_chl" in lower or "cloudflare" in lower:
        return f"response is HTML Cloudflare challenge (snippet: {snippet})"
    if content.lstrip().startswith("<"):
        return f"response is HTML, not JSON (snippet: {snippet})"
    return f"response is not valid JSON (snippet: {snippet})"


def fetch_json(url: str, timeout: int = 20, retries: int = 2) -> Any:
    headers = {
        "User-Agent": "playcover-to-gbox-catalog/1.2",
        "Accept": "application/json,text/plain,*/*",
    }
    req = Request(url, headers=headers)
    last_exc: Exception | None = None

    for _ in range(retries + 1):
        try:
            with urlopen(req, timeout=timeout) as response:
                status = getattr(response, "status", None)
                if status is not None and (status < 200 or status >= 300):
                    raise RuntimeError(f"HTTP {status}")
                content = response.read().decode("utf-8", errors="replace")
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    raise RuntimeError(_summarize_non_json(content)) from None
        except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
            last_exc = exc

    assert last_exc is not None
    raise RuntimeError(f"Failed to fetch {url}: {last_exc}")


def load_defaults(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dedupe_apps(apps: list[PlayCoverApp]) -> tuple[list[PlayCoverApp], int]:
    seen: dict[str, PlayCoverApp] = {}

    for app in apps:
        key = app.bundle_id.lower() if app.bundle_id else f"{app.name}|{app.version}|{app.link}"
        if key in seen:
            existing = seen[key]
            chosen = app if app.version > existing.version else existing
            seen[key] = chosen
        else:
            seen[key] = app

    deduped = sorted(seen.values(), key=lambda a: a.name.lower())
    return deduped, max(0, len(apps) - len(deduped))


def build_catalog(defaults: dict[str, Any], apps: list[PlayCoverApp], update_time: str) -> dict[str, Any]:
    app_type = os.getenv("GBOX_DEFAULT_APP_TYPE", defaults.get("defaultAppType", "SELF_SIGN"))
    fallback_icon = os.getenv("GBOX_FALLBACK_ICON", defaults.get("fallbackAppImage", ""))

    repositories = [
        map_app_to_gbox(
            app,
            app_type=app_type,
            fallback_icon=fallback_icon,
            app_cate_index=0,
            updated_at=update_time,
        )
        for app in apps
    ]

    return {
        "version": defaults.get("version", "1.0"),
        "sourceName": os.getenv("GBOX_SOURCE_NAME", defaults.get("sourceName", "PlayCover Feed")),
        "sourceAuthor": os.getenv("GBOX_SOURCE_AUTHOR", defaults.get("sourceAuthor", "GitHub Actions")),
        "sourceLinkTitle": defaults.get("sourceLinkTitle", "Repository"),
        "sourceLinkUrl": defaults.get("sourceLinkUrl", ""),
        "sourceImage": os.getenv("GBOX_SOURCE_IMAGE", defaults.get("sourceImage", "")),
        "sourceUpdateTime": update_time,
        "sourceDescription": os.getenv(
            "GBOX_SOURCE_DESCRIPTION", defaults.get("sourceDescription", "Generated from PlayCover sources")
        ),
        "appCategories": defaults.get("appCategories", ["Apps"]),
        "appRepositories": repositories,
    }


def write_if_changed(path: Path, payload: dict[str, Any]) -> bool:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == serialized:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8")
    return True


def _write_report(report_path: Path, report: dict[str, Any]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(
    dry_run: bool = False,
    fail_on_empty_sources: bool = False,
    fail_on_no_valid_apps: bool = False,
) -> int:
    defaults = load_defaults(Path("config/defaults.json"))
    sources = parse_sources(os.getenv("PLAYCOVER_SOURCES", ""))
    output_path = Path(os.getenv("OUTPUT_PATH", "output/catalog.json"))
    report_path = Path("output/last-run.json")
    stats = ConvertStats(sources_total=len(sources))
    source_errors: list[dict[str, str]] = []

    if not sources:
        report = {
            "updatedAt": iso_utc_now(),
            "sourcesTotal": 0,
            "sourcesOk": 0,
            "appsSeen": 0,
            "appsValid": 0,
            "duplicatesRemoved": 0,
            "errors": 1,
            "outputChanged": False,
            "dryRun": dry_run,
            "status": "skipped",
            "message": "PLAYCOVER_SOURCES is empty; catalog generation skipped.",
            "sourceErrors": source_errors,
        }
        _write_report(report_path, report)
        print(json.dumps(report, ensure_ascii=False))
        if fail_on_empty_sources:
            raise RuntimeError("No sources found. Set PLAYCOVER_SOURCES variable.")
        return 0

    collected_apps: list[PlayCoverApp] = []

    for source_url in sources:
        try:
            data = fetch_json(source_url)
            if not isinstance(data, list):
                raise ValueError("source payload must be an array of PlayCover app objects")
            stats.sources_ok += 1
            for item in data:
                if not isinstance(item, dict):
                    stats.errors += 1
                    continue
                stats.apps_seen += 1
                app = PlayCoverApp.from_payload(item, source_url)
                valid, _ = app.is_valid()
                if valid:
                    collected_apps.append(app)
                    stats.apps_valid += 1
                else:
                    stats.errors += 1
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            print(f"[WARN] Source failed: {source_url}: {msg}")
            source_errors.append({"url": source_url, "error": msg})
            stats.errors += 1

    deduped_apps, removed = dedupe_apps(collected_apps)
    stats.duplicates_removed = removed

    if not deduped_apps:
        report = {
            "updatedAt": iso_utc_now(),
            "sourcesTotal": stats.sources_total,
            "sourcesOk": stats.sources_ok,
            "appsSeen": stats.apps_seen,
            "appsValid": stats.apps_valid,
            "duplicatesRemoved": stats.duplicates_removed,
            "errors": stats.errors,
            "outputChanged": False,
            "dryRun": dry_run,
            "status": "partial",
            "message": "No valid apps were produced from sources. Existing catalog preserved.",
            "sourceErrors": source_errors,
            "hint": (
                "Each source URL must return a JSON array in PlayCover format. "
                "Web pages/challenge pages are not valid sources."
            ),
        }
        _write_report(report_path, report)
        print(json.dumps(report, ensure_ascii=False))
        if fail_on_no_valid_apps:
            raise RuntimeError("No valid apps were produced from all provided sources.")
        return 0

    updated_at = iso_utc_now()
    catalog = build_catalog(defaults, deduped_apps, updated_at)
    validation_errors = validate_gbox_catalog(catalog)
    if validation_errors:
        raise RuntimeError("; ".join(validation_errors))

    changed = False if dry_run else write_if_changed(output_path, catalog)

    report = {
        "updatedAt": updated_at,
        "sourcesTotal": stats.sources_total,
        "sourcesOk": stats.sources_ok,
        "appsSeen": stats.apps_seen,
        "appsValid": stats.apps_valid,
        "duplicatesRemoved": stats.duplicates_removed,
        "errors": stats.errors,
        "outputChanged": changed,
        "dryRun": dry_run,
        "status": "ok",
        "sourceErrors": source_errors,
    }

    _write_report(report_path, report)
    print(json.dumps(report, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert PlayCover sources to GBox catalog")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, no catalog write")
    parser.add_argument(
        "--fail-on-empty-sources",
        action="store_true",
        help="Fail if PLAYCOVER_SOURCES is empty instead of skipping gracefully",
    )
    parser.add_argument(
        "--fail-on-no-valid-apps",
        action="store_true",
        help="Fail if all sources are unavailable/invalid and no apps were produced",
    )
    args = parser.parse_args()
    return run(
        dry_run=args.dry_run,
        fail_on_empty_sources=args.fail_on_empty_sources,
        fail_on_no_valid_apps=args.fail_on_no_valid_apps,
    )


if __name__ == "__main__":
    raise SystemExit(main())
