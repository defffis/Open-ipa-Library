from __future__ import annotations

from typing import Any

from src.adapters.base import FetchResult
from src.models.canonical import CanonicalApp
from src.models.source_config import SourceConfig
from src.services.http_client import (
    AuthRequiredError,
    HtmlChallengeError,
    HttpClient,
    HttpStatusError,
    NetworkError,
)


class PlayCoverJsonAdapter:
    """Адаптер для источников в формате PlayCover JSON (массив объектов приложений)."""

    def __init__(self, source: SourceConfig) -> None:
        self.source = source
        self._client = HttpClient(
            timeout=source.timeout_sec,
            retries=source.retries,
            auth=source.auth,
        )

    def fetch(self) -> FetchResult:
        url = self.source.catalog_url
        if not url:
            return FetchResult(
                source_id=self.source.id,
                success=False,
                error="catalogUrl is empty for playcover_json source",
            )
        try:
            data = self._client.fetch_json(url)
        except (HtmlChallengeError, AuthRequiredError) as exc:
            return FetchResult(source_id=self.source.id, success=False, error=str(exc))
        except HttpStatusError as exc:
            return FetchResult(
                source_id=self.source.id,
                success=False,
                error=str(exc),
                http_status=exc.status,
            )
        except NetworkError as exc:
            return FetchResult(source_id=self.source.id, success=False, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            return FetchResult(source_id=self.source.id, success=False, error=str(exc))

        if not isinstance(data, list):
            return FetchResult(
                source_id=self.source.id,
                success=False,
                error="source payload must be a JSON array of PlayCover app objects",
            )

        apps: list[CanonicalApp] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            app = self._normalize(item)
            if app is not None:
                apps.append(app)

        return FetchResult(
            source_id=self.source.id,
            apps=apps,
            success=True,
            apps_found=len(data),
        )

    def _normalize(self, payload: dict[str, Any]) -> CanonicalApp | None:
        name = str(payload.get("name", "") or "").strip()
        if not name:
            return None

        bundle_id = str(payload.get("bundleID", "") or "").strip() or None
        version = str(payload.get("version", "") or "").strip() or None
        link = str(payload.get("link", "") or "").strip() or None
        itunes_lookup = str(payload.get("itunesLookup", "") or "").strip() or None

        # link должен оканчиваться на .ipa чтобы считаться валидным download_url
        download_url: str | None = None
        if link and link.lower().endswith(".ipa"):
            download_url = link

        availability = "public" if download_url else "unknown"

        return CanonicalApp(
            source_id=self.source.id,
            bundle_id=bundle_id,
            name=name,
            version=version,
            download_url=download_url,
            app_page_url=None,
            icon_url=None,
            itunes_lookup=itunes_lookup,
            availability=availability,
            requires_auth=False,
            raw=payload,
        )
