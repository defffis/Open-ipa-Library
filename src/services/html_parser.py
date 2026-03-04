from __future__ import annotations

from typing import Any

try:
    from bs4 import BeautifulSoup, Tag
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False
    BeautifulSoup = None  # type: ignore[assignment,misc]
    Tag = None            # type: ignore[assignment,misc]


def _require_bs4() -> None:
    if not _BS4_AVAILABLE:
        raise ImportError(
            "beautifulsoup4 is required for HTML adapters. "
            "Install it with: pip install beautifulsoup4"
        )


class HtmlParser:
    """Тонкая обёртка над BeautifulSoup для работы с HTML-каталогами."""

    def __init__(self, html: str, parser: str = "html.parser") -> None:
        _require_bs4()
        self._soup = BeautifulSoup(html, parser)

    @property
    def soup(self) -> Any:
        return self._soup

    def select(self, selector: str) -> list[Any]:
        return self._soup.select(selector)

    def select_one(self, selector: str) -> Any | None:
        return self._soup.select_one(selector)

    def find(self, tag: str, attrs: dict[str, Any] | None = None, **kwargs: Any) -> Any | None:
        return self._soup.find(tag, attrs or {}, **kwargs)

    def find_all(self, tag: str, attrs: dict[str, Any] | None = None, **kwargs: Any) -> list[Any]:
        return self._soup.find_all(tag, attrs or {}, **kwargs)

    def text(self, element: Any) -> str:
        if element is None:
            return ""
        return element.get_text(strip=True)

    def attr(self, element: Any, name: str, default: str = "") -> str:
        if element is None:
            return default
        value = element.get(name, default)
        return str(value).strip() if value else default
