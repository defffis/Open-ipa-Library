from __future__ import annotations

from typing import Any

REQUIRED_ROOT_FIELDS = {
    "version",
    "sourceName",
    "sourceAuthor",
    "sourceImage",
    "sourceUpdateTime",
    "sourceDescription",
    "appCategories",
    "appRepositories",
}


def validate_gbox_catalog(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    missing = sorted(field for field in REQUIRED_ROOT_FIELDS if field not in payload)
    if missing:
        errors.append(f"Missing root fields: {', '.join(missing)}")

    repos = payload.get("appRepositories")
    if not isinstance(repos, list) or not repos:
        errors.append("appRepositories must be a non-empty list")
    else:
        for idx, app in enumerate(repos):
            package = app.get("appPackage") if isinstance(app, dict) else None
            if not isinstance(package, str) or not package.strip():
                errors.append(f"appRepositories[{idx}].appPackage must be non-empty string")

    return errors
