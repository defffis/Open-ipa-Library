from __future__ import annotations

import re

from src.adapters.html_base import HtmlCatalogAdapter
from src.models.canonical import CanonicalApp
from src.services.html_parser import HtmlParser

_IPA_RE = re.compile(r'https?://[^\s"\'<>]+\.ipa', re.IGNORECASE)
_VERSION_RE = re.compile(r'\b(\d+\.\d+[\.\d]*)\b')


class ArmConverterHtmlAdapter(HtmlCatalogAdapter):
    """Адаптер для armconverter.com/decryptedappstore.

    armconverter отображает таблицу/сетку приложений с именем, версией,
    bundle_id и ссылкой для скачивания.
    """

    def parse_html(self, parser: HtmlParser, raw_html: str) -> list[CanonicalApp]:
        apps: list[CanonicalApp] = []
        base_url = "https://armconverter.com"

        # Ищем строки таблицы или карточки приложений
        rows = (
            parser.select("tr[data-bundle], tr[data-app]")
            or parser.select(".app-row, .app-item, .app-card")
            or parser.select("table tbody tr")
        )

        for row in rows:
            name_el = (
                row.select_one(".app-name, .name, td.name, [data-field='name']")
                if hasattr(row, "select_one") else None
            )
            name = parser.text(name_el) if name_el else ""
            if not name:
                # Берём первый непустой td
                tds = row.find_all("td") if hasattr(row, "find_all") else []
                for td in tds:
                    candidate = parser.text(td)
                    if candidate and len(candidate) > 1:
                        name = candidate
                        break
            if not name or len(name) < 2:
                continue

            ver_el = (
                row.select_one(".version, .app-version, td.version, [data-field='version']")
                if hasattr(row, "select_one") else None
            )
            version = parser.text(ver_el) if ver_el else None

            bundle_id = (
                parser.attr(row, "data-bundle")
                or parser.attr(row, "data-bundle-id")
                or parser.attr(row, "data-app")
                or None
            )

            # Ссылка на скачивание
            dl_el = (
                row.select_one("a[href$='.ipa'], a.download, a[download]")
                if hasattr(row, "select_one") else None
            )
            download_url: str | None = None
            if dl_el:
                href = parser.attr(dl_el, "href")
                if href:
                    download_url = href if href.startswith("http") else f"{base_url}{href}"

            # Ссылка на страницу приложения
            page_el = (
                row.select_one("a[href*='/app/'], a[href*='/decrypted/']")
                if hasattr(row, "select_one") else None
            )
            page_url: str | None = None
            if page_el:
                href = parser.attr(page_el, "href")
                if href:
                    page_url = href if href.startswith("http") else f"{base_url}{href}"

            apps.append(CanonicalApp(
                source_id=self.source.id,
                bundle_id=bundle_id,
                name=name,
                version=version,
                download_url=download_url,
                app_page_url=page_url,
                icon_url=None,
                itunes_lookup=None,
                availability="public" if download_url else "unknown",
                requires_auth=False,
                raw={"name": name, "version": version, "bundle_id": bundle_id},
            ))

        # Запасной метод: регулярный поиск .ipa ссылок
        if not apps:
            apps = self._fallback_ipa_links(raw_html)

        return apps

    def _fallback_ipa_links(self, raw_html: str) -> list[CanonicalApp]:
        apps: list[CanonicalApp] = []
        seen: set[str] = set()
        for match in _IPA_RE.finditer(raw_html):
            url = match.group(0)
            if url in seen:
                continue
            seen.add(url)
            filename = url.rstrip("/").split("/")[-1].replace(".ipa", "")
            # Ищем версию в имени файла
            ver_match = _VERSION_RE.search(filename)
            version = ver_match.group(1) if ver_match else None
            name = re.sub(r'[_\-]' + re.escape(version) + r'.*$', '', filename) if version else filename
            name = name.replace("-", " ").replace("_", " ").strip() or url
            apps.append(CanonicalApp(
                source_id=self.source.id,
                bundle_id=None,
                name=name,
                version=version,
                download_url=url,
                app_page_url=None,
                icon_url=None,
                itunes_lookup=None,
                availability="public",
                requires_auth=False,
                raw={"ipa_url": url},
            ))
        return apps
