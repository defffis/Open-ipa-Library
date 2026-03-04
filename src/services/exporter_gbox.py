from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.models.canonical import CanonicalApp

try:
    from src.validators import validate_gbox_catalog
except ModuleNotFoundError:
    from validators import validate_gbox_catalog  # type: ignore[no-redef]


def _load_defaults(path: Path = Path("config/defaults.json")) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _app_to_gbox(app: CanonicalApp, *, app_type: str, fallback_icon: str, updated_at: str) -> dict[str, Any]:
    description_parts = [f"source={app.source_id}"]
    if app.bundle_id:
        description_parts.insert(0, f"bundleID={app.bundle_id}")
    if app.itunes_lookup:
        description_parts.append(f"itunesLookup={app.itunes_lookup}")

    icon = app.icon_url or fallback_icon

    return {
        "appType": app_type,
        "appCateIndex": 0,
        "appUpdateTime": updated_at,
        "appName": app.name,
        "appVersion": app.version or "",
        "appImage": icon,
        "appPackage": app.download_url or "",
        "appDescription": "; ".join(description_parts),
    }


def build_gbox_catalog(
    apps: list[CanonicalApp],
    updated_at: str,
    defaults_path: Path | None = None,
) -> dict[str, Any]:
    """Собирает GBox-каталог из списка CanonicalApp.

    Экспортирует только приложения с download_url и availability == 'public'.
    """
    defaults = _load_defaults(defaults_path or Path("config/defaults.json"))

    app_type = os.getenv("GBOX_DEFAULT_APP_TYPE", defaults.get("defaultAppType", "SELF_SIGN"))
    fallback_icon = os.getenv("GBOX_FALLBACK_ICON", defaults.get("fallbackAppImage", ""))

    exportable = [a for a in apps if a.is_exportable]

    repositories = [
        _app_to_gbox(app, app_type=app_type, fallback_icon=fallback_icon, updated_at=updated_at)
        for app in exportable
    ]

    catalog = {
        "version": defaults.get("version", "1.0"),
        "sourceName": os.getenv("GBOX_SOURCE_NAME", defaults.get("sourceName", "Open IPA Library")),
        "sourceAuthor": os.getenv("GBOX_SOURCE_AUTHOR", defaults.get("sourceAuthor", "GitHub Actions")),
        "sourceLinkTitle": defaults.get("sourceLinkTitle", "Repository"),
        "sourceLinkUrl": defaults.get("sourceLinkUrl", ""),
        "sourceImage": os.getenv("GBOX_SOURCE_IMAGE", defaults.get("sourceImage", "")),
        "sourceUpdateTime": updated_at,
        "sourceDescription": os.getenv(
            "GBOX_SOURCE_DESCRIPTION",
            defaults.get("sourceDescription", "Generated from multiple IPA sources"),
        ),
        "appCategories": defaults.get("appCategories", ["Apps"]),
        "appRepositories": repositories,
    }

    errors = validate_gbox_catalog(catalog)
    if errors:
        raise ValueError("GBox catalog validation failed: " + "; ".join(errors))

    return catalog


def write_if_changed(path: Path, payload: dict[str, Any]) -> bool:
    """Записывает JSON только если содержимое изменилось. Возвращает True при записи."""
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == serialized:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8")
    return True
