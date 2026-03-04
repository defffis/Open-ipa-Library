from __future__ import annotations

import re

from src.adapters.html_base import HtmlCatalogAdapter
from src.models.canonical import CanonicalApp
from src.services.html_parser import HtmlParser

_IPA_RE = re.compile(r'https?://[^\s"\']+\.ipa', re.IGNORECASE)


class DecryptDayHtmlAdapter(HtmlCatalogAdapter):
    """Адаптер для decrypt.day — HTML-каталог расшифрованных IPA-файлов.

    decrypt.day показывает список приложений в виде карточек или строк таблицы.
    Адаптер парсит имя, версию, bundle_id и ссылку на страницу/скачивание.
    """

    def parse_html(self, parser: HtmlParser, raw_html: str) -> list[CanonicalApp]:
        apps: list[CanonicalApp] = []
        base_url = self.source.options.get("appBaseUrl", "https://decrypt.day").rstrip("/")

        # decrypt.day использует карточки вида: <a href="/app/...">...</a>
        # с именем, версией и bundle_id внутри
        app_links = parser.select("a[href^='/app/']") or parser.select("a[href*='/app/']")

        seen_urls: set[str] = set()
        for link in app_links:
            href = parser.attr(link, "href")
            if not href or href in seen_urls:
                continue
            seen_urls.add(href)

            page_url = href if href.startswith("http") else f"{base_url}{href}"

            # Имя: ищем внутри ссылки элемент с именем или берём весь текст
            name_el = link.select_one(".app-name, .name, h3, h2, strong") if hasattr(link, "select_one") else None
            name = parser.text(name_el) if name_el else parser.text(link)
            name = name.strip()
            if not name or len(name) < 2:
                continue

            # Версия
            ver_el = link.select_one(".version, .app-version, [class*='version']") if hasattr(link, "select_one") else None
            version = parser.text(ver_el) if ver_el else None
            version = version.strip() if version else None

            # Bundle ID из data-атрибута или текста
            bundle_id = parser.attr(link, "data-bundle-id") or parser.attr(link, "data-bundleid") or None

            # Ищем прямую ссылку на .ipa внутри карточки
            ipa_link_el = link.select_one("a[href$='.ipa']") if hasattr(link, "select_one") else None
            download_url: str | None = None
            if ipa_link_el:
                dl_href = parser.attr(ipa_link_el, "href")
                download_url = dl_href if dl_href.startswith("http") else f"{base_url}{dl_href}"

            apps.append(CanonicalApp(
                source_id=self.source.id,
                bundle_id=bundle_id if bundle_id else None,
                name=name,
                version=version,
                download_url=download_url,
                app_page_url=page_url,
                icon_url=None,
                itunes_lookup=None,
                availability="public" if download_url else "unknown",
                requires_auth=False,
                raw={"href": href, "name": name, "version": version},
            ))

        # Запасной метод: ищем прямые ссылки на .ipa если карточки не нашлись
        if not apps:
            apps = self._fallback_ipa_links(parser, raw_html, base_url)

        return apps

    def _fallback_ipa_links(self, parser: HtmlParser, raw_html: str, base_url: str) -> list[CanonicalApp]:
        apps: list[CanonicalApp] = []
        for match in _IPA_RE.finditer(raw_html):
            url = match.group(0)
            # Извлекаем имя из последнего сегмента URL
            filename = url.rstrip("/").split("/")[-1].replace(".ipa", "")
            name = filename.replace("-", " ").replace("_", " ").strip() or url
            apps.append(CanonicalApp(
                source_id=self.source.id,
                bundle_id=None,
                name=name,
                version=None,
                download_url=url,
                app_page_url=None,
                icon_url=None,
                itunes_lookup=None,
                availability="public",
                requires_auth=False,
                raw={"ipa_url": url},
            ))
        return apps
