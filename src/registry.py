from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.models.source_config import SourceConfig

_SOURCES_ENV = "SOURCES_CONFIG"
_DEFAULT_PATH = Path("config/sources.json")

VALID_TYPES = {"playcover_json", "html_catalog", "static_mirror"}
VALID_ADAPTERS = {
    "playcover_json",
    "decrypt_day_html",
    "armconverter_html",
    "static_json_mirror",
}


class RegistryError(Exception):
    pass


def _validate_entry(d: dict[str, Any], idx: int) -> list[str]:
    errors: list[str] = []
    for key in ("id", "name", "type", "adapter", "catalogUrl"):
        if not d.get(key):
            errors.append(f"sources[{idx}] missing required field '{key}'")
    if d.get("type") and d["type"] not in VALID_TYPES:
        errors.append(f"sources[{idx}] unknown type '{d['type']}'")
    if d.get("adapter") and d["adapter"] not in VALID_ADAPTERS:
        errors.append(f"sources[{idx}] unknown adapter '{d['adapter']}'")
    return errors


def load_sources(path: Path | None = None) -> list[SourceConfig]:
    """Загружает и валидирует sources.json.

    Путь к файлу берётся из аргумента, затем из env SOURCES_CONFIG,
    затем из config/sources.json.
    """
    if path is None:
        env_path = os.getenv(_SOURCES_ENV, "")
        path = Path(env_path) if env_path else _DEFAULT_PATH

    if not path.exists():
        raise RegistryError(f"Sources config not found: {path}")

    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RegistryError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(raw, list):
        raise RegistryError(f"{path} must contain a JSON array")

    all_errors: list[str] = []
    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            all_errors.append(f"sources[{idx}] is not an object")
            continue
        all_errors.extend(_validate_entry(entry, idx))

    if all_errors:
        raise RegistryError("sources.json validation failed:\n" + "\n".join(all_errors))

    configs = [SourceConfig.from_dict(entry) for entry in raw if isinstance(entry, dict)]

    ids = [c.id for c in configs]
    seen: set[str] = set()
    for sid in ids:
        if sid in seen:
            raise RegistryError(f"Duplicate source id '{sid}' in {path}")
        seen.add(sid)

    return configs


def load_enabled_sources(path: Path | None = None) -> list[SourceConfig]:
    """Возвращает только включённые источники, отсортированные по приоритету."""
    all_sources = load_sources(path)
    enabled = [s for s in all_sources if s.enabled]
    return sorted(enabled, key=lambda s: s.priority)
