from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class PlayCoverApp:
    bundle_id: str
    name: str
    version: str
    itunes_lookup: str
    link: str
    source_url: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any], source_url: str) -> "PlayCoverApp":
        return cls(
            bundle_id=str(payload.get("bundleID", "") or "").strip(),
            name=str(payload.get("name", "") or "").strip(),
            version=str(payload.get("version", "") or "").strip(),
            itunes_lookup=str(payload.get("itunesLookup", "") or "").strip(),
            link=str(payload.get("link", "") or "").strip(),
            source_url=source_url,
        )

    def is_valid(self) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if not self.name:
            errors.append("missing name")
        if not self.version:
            errors.append("missing version")
        if not self.link:
            errors.append("missing link")
        elif not self.link.lower().endswith(".ipa"):
            errors.append("link is not .ipa")
        return (not errors, errors)


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def map_app_to_gbox(
    app: PlayCoverApp,
    *,
    app_type: str,
    fallback_icon: str,
    app_cate_index: int = 0,
    updated_at: str | None = None,
) -> dict[str, Any]:
    update_time = updated_at or iso_utc_now()
    description = (
        f"Imported from PlayCover source. bundleID={app.bundle_id or 'N/A'}; "
        f"itunesLookup={app.itunes_lookup or 'N/A'}; source={app.source_url}"
    )

    return {
        "appType": app_type,
        "appCateIndex": app_cate_index,
        "appUpdateTime": update_time,
        "appName": app.name,
        "appVersion": app.version,
        "appImage": fallback_icon,
        "appPackage": app.link,
        "appDescription": description,
    }
