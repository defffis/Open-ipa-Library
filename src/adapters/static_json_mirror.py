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


class StaticJsonMirrorAdapter:
    """Адаптер для статических JSON-зеркал каталога в GBox-формате.

    Ожидает JSON-объект с полем `appRepositories` (стандартный GBox-формат)
    или произвольный массив объектов приложений.
    """

    def __init__(self, source: SourceConfig) -> None:
        self.source = source
        self._client = HttpClient(
            timeout=source.timeout_sec,
            retries=source.retries,
            auth=source.auth,
        )

    def fetch(self) -> FetchResult:
        url = self.source.catalog_url
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

        apps: list[CanonicalApp] = []

        if isinstance(data, dict):
            # GBox-формат: { "appRepositories": [...] }
            repos = data.get("appRepositories", [])
            if isinstance(repos, list):
                for item in repos:
                    if isinstance(item, dict):
                        app = self._normalize_gbox(item)
                        if app is not None:
                            apps.append(app)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    app = self._normalize_generic(item)
                    if app is not None:
                        apps.append(app)
        else:
            return FetchResult(
                source_id=self.source.id,
                success=False,
                error="static mirror must return a JSON object or array",
            )

        return FetchResult(
            source_id=self.source.id,
            apps=apps,
            success=True,
            apps_found=len(apps),
        )

    def _normalize_gbox(self, item: dict[str, Any]) -> CanonicalApp | None:
        name = str(item.get("appName", "") or "").strip()
        if not name:
            return None
        link = str(item.get("appPackage", "") or "").strip() or None
        download_url = link if (link and link.lower().endswith(".ipa")) else None
        return CanonicalApp(
            source_id=self.source.id,
            bundle_id=None,
            name=name,
            version=str(item.get("appVersion", "") or "").strip() or None,
            download_url=download_url,
            app_page_url=None,
            icon_url=str(item.get("appImage", "") or "").strip() or None,
            itunes_lookup=None,
            availability="public" if download_url else "unknown",
            requires_auth=False,
            raw=item,
        )

    def _normalize_generic(self, item: dict[str, Any]) -> CanonicalApp | None:
        name = (
            str(item.get("name", "") or item.get("appName", "") or item.get("title", "") or "").strip()
        )
        if not name:
            return None
        link = str(
            item.get("link", "") or item.get("appPackage", "") or item.get("download_url", "") or ""
        ).strip() or None
        download_url = link if (link and link.lower().endswith(".ipa")) else None
        bundle_id = str(item.get("bundleID", "") or item.get("bundle_id", "") or "").strip() or None
        return CanonicalApp(
            source_id=self.source.id,
            bundle_id=bundle_id,
            name=name,
            version=str(item.get("version", "") or "").strip() or None,
            download_url=download_url,
            app_page_url=None,
            icon_url=None,
            itunes_lookup=str(item.get("itunesLookup", "") or "").strip() or None,
            availability="public" if download_url else "unknown",
            requires_auth=False,
            raw=item,
        )
