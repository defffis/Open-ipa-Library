from __future__ import annotations

from abc import ABC, abstractmethod

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
from src.services.html_parser import HtmlParser


class HtmlCatalogAdapter(ABC):
    """Абстрактный базовый класс для адаптеров HTML-каталогов.

    Подклассы реализуют `parse_html` для извлечения приложений из HTML-страницы.
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
            html = self._client.fetch_html(url)
        except HtmlChallengeError as exc:
            return FetchResult(source_id=self.source.id, success=False, error=str(exc))
        except AuthRequiredError as exc:
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

        try:
            parser = HtmlParser(html)
            apps = self.parse_html(parser, html)
        except Exception as exc:  # noqa: BLE001
            return FetchResult(source_id=self.source.id, success=False, error=f"parse error: {exc}")

        return FetchResult(
            source_id=self.source.id,
            apps=apps,
            success=True,
            apps_found=len(apps),
        )

    @abstractmethod
    def parse_html(self, parser: HtmlParser, raw_html: str) -> list[CanonicalApp]:
        """Извлекает и нормализует список приложений из HTML-страницы."""
        ...
