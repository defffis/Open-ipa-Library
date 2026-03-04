from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FetchResult:
    source_id: str
    success: bool
    apps_found: int = 0
    error: str | None = None
    status_code: int | None = None


@dataclass
class SourceStatus:
    source_id: str
    source_name: str
    status: str                     # ok | partial | error | skipped
    apps_found: int = 0
    apps_exportable: int = 0
    error: str | None = None


@dataclass
class RunReport:
    updated_at: str
    status: str                     # ok | partial | skipped | error
    sources_processed: int = 0
    sources_ok: int = 0
    sources_partial: int = 0
    sources_error: int = 0
    apps_found: int = 0
    apps_normalized: int = 0
    apps_exportable: int = 0
    apps_dropped: int = 0
    duplicates_removed: int = 0
    output_changed: bool = False
    dry_run: bool = False
    message: str = ""
    source_statuses: list[SourceStatus] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "updatedAt": self.updated_at,
            "status": self.status,
            "sourcesProcessed": self.sources_processed,
            "sourcesOk": self.sources_ok,
            "sourcesPartial": self.sources_partial,
            "sourcesError": self.sources_error,
            "appsFound": self.apps_found,
            "appsNormalized": self.apps_normalized,
            "appsExportable": self.apps_exportable,
            "appsDropped": self.apps_dropped,
            "duplicatesRemoved": self.duplicates_removed,
            "outputChanged": self.output_changed,
            "dryRun": self.dry_run,
            "message": self.message,
            "sourceErrors": self.errors,
        }
