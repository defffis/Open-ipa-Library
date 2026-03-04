from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CanonicalApp:
    source_id: str
    bundle_id: str | None
    name: str
    version: str | None
    download_url: str | None        # None → не попадает в GBox-каталог
    app_page_url: str | None
    icon_url: str | None
    itunes_lookup: str | None
    availability: str               # public | login_required | unavailable | unknown
    requires_auth: bool
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_exportable(self) -> bool:
        return self.download_url is not None and self.availability == "public"

    def dedup_key(self) -> str:
        """Первичный ключ дедупликации — bundle_id (нижний регистр)."""
        if self.bundle_id:
            return f"bundle:{self.bundle_id.lower()}"
        name_norm = (self.name or "").lower().strip()
        ver = (self.version or "").strip()
        if name_norm and ver:
            return f"name_ver:{name_norm}|{ver}"
        if self.app_page_url:
            return f"page:{self.app_page_url.lower()}"
        return f"name:{name_norm}"

    def metadata_score(self) -> int:
        """Количество заполненных необязательных полей (для выбора победителя при дедупликации)."""
        return sum(
            1
            for v in (self.bundle_id, self.version, self.download_url,
                      self.icon_url, self.itunes_lookup, self.app_page_url)
            if v
        )
