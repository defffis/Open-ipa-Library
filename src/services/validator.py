from __future__ import annotations

from src.models.canonical import CanonicalApp


def validate_app(app: CanonicalApp) -> list[str]:
    """Валидирует один CanonicalApp. Возвращает список ошибок (пустой = OK)."""
    errors: list[str] = []
    if not app.name or not app.name.strip():
        errors.append("missing name")
    if app.download_url and not app.download_url.startswith(("http://", "https://")):
        errors.append(f"download_url has invalid scheme: {app.download_url[:60]}")
    if app.app_page_url and not app.app_page_url.startswith(("http://", "https://")):
        errors.append(f"app_page_url has invalid scheme: {app.app_page_url[:60]}")
    if app.availability not in ("public", "login_required", "unavailable", "unknown"):
        errors.append(f"unknown availability value: {app.availability!r}")
    return errors


def validate_apps(apps: list[CanonicalApp]) -> tuple[list[CanonicalApp], list[str]]:
    """Фильтрует невалидные приложения и возвращает (валидные, список предупреждений)."""
    valid: list[CanonicalApp] = []
    warnings: list[str] = []
    for app in apps:
        errs = validate_app(app)
        if errs:
            warnings.append(f"[{app.source_id}] '{app.name}': {'; '.join(errs)}")
        else:
            valid.append(app)
    return valid, warnings
