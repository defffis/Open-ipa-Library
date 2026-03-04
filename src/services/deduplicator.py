from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from src.models.canonical import CanonicalApp


def _load_dedupe_config(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        path = Path("config/dedupe.json")
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _winner(a: CanonicalApp, b: CanonicalApp) -> CanonicalApp:
    """Выбирает победителя из двух дубликатов.

    Приоритет: меньший priority (число) источника → наличие download_url → полнота метаданных.
    Примечание: priority хранится в source.priority, но у CanonicalApp его нет;
    передаём через raw['_source_priority'] если оркестратор заполнил.
    """
    p_a = int(a.raw.get("_source_priority", 50))
    p_b = int(b.raw.get("_source_priority", 50))

    if p_a != p_b:
        return a if p_a < p_b else b

    has_dl_a = a.download_url is not None
    has_dl_b = b.download_url is not None
    if has_dl_a != has_dl_b:
        return a if has_dl_a else b

    return a if a.metadata_score() >= b.metadata_score() else b


def deduplicate(
    apps: list[CanonicalApp],
    config_path: Path | None = None,
) -> tuple[list[CanonicalApp], int]:
    """Дедуплицирует список приложений.

    Ключ в порядке приоритета:
      1. bundle_id (нижний регистр)
      2. normalize(name) + version
      3. app_page_url

    Возвращает (дедупл. список, кол-во удалённых дубликатов).
    """
    _load_dedupe_config(config_path)  # зарезервировано для будущих правил

    seen: dict[str, CanonicalApp] = {}
    for app in apps:
        key = app.dedup_key()
        if key in seen:
            seen[key] = _winner(seen[key], app)
        else:
            seen[key] = app

    deduped = sorted(seen.values(), key=lambda a: (a.name or "").lower())
    removed = max(0, len(apps) - len(deduped))
    return deduped, removed
