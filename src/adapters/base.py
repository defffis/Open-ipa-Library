from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from src.models.canonical import CanonicalApp
from src.models.source_config import SourceConfig


@dataclass
class AppRef:
    """Минимальная ссылка на приложение до полной нормализации."""
    source_id: str
    raw_id: str                     # bundle_id или внутренний id страницы
    name: str
    page_url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class FetchResult:
    source_id: str
    apps: list[CanonicalApp] = field(default_factory=list)
    success: bool = True
    error: str | None = None
    http_status: int | None = None
    apps_found: int = 0             # до фильтрации/нормализации

    @property
    def status(self) -> str:
        if self.success and self.apps:
            return "ok"
        if self.success and not self.apps:
            return "partial"
        return "error"


@runtime_checkable
class SourceAdapter(Protocol):
    """Протокол адаптера источника."""

    source: SourceConfig

    def fetch(self) -> FetchResult:
        """Загружает и нормализует список приложений из источника."""
        ...
