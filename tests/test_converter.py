"""Тесты для старого convert.py (обратная совместимость) и новой multi-source архитектуры."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Старые тесты (convert.py) — обратная совместимость
# ---------------------------------------------------------------------------

from src.convert import dedupe_apps, parse_sources, run
from src.mappers.playcover_to_gbox import PlayCoverApp


def test_parse_sources_newline():
    raw = "https://a.example/source.json\nhttps://b.example/source.json\n"
    assert parse_sources(raw) == ["https://a.example/source.json", "https://b.example/source.json"]


def test_dedupe_prefers_latest_lexicographically():
    a1 = PlayCoverApp("com.demo.app", "Demo", "1.0.0", "", "https://a/app.ipa", "https://a")
    a2 = PlayCoverApp("com.demo.app", "Demo", "1.1.0", "", "https://b/app.ipa", "https://b")

    deduped, removed = dedupe_apps([a1, a2])

    assert len(deduped) == 1
    assert removed == 1
    assert deduped[0].version == "1.1.0"


def test_empty_sources_is_skipped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config/defaults.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "sourceName": "x",
                "sourceAuthor": "x",
                "sourceImage": "x",
                "sourceDescription": "x",
                "appCategories": ["Apps"],
                "defaultAppType": "SELF_SIGN",
                "fallbackAppImage": "x",
            }
        ),
        encoding="utf-8",
    )

    exit_code = run(dry_run=True)

    assert exit_code == 0
    report = json.loads(Path("output/last-run.json").read_text(encoding="utf-8"))
    assert report["status"] == "skipped"


def test_no_valid_apps_is_partial(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config/defaults.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "sourceName": "x",
                "sourceAuthor": "x",
                "sourceImage": "x",
                "sourceDescription": "x",
                "appCategories": ["Apps"],
                "defaultAppType": "SELF_SIGN",
                "fallbackAppImage": "x",
            }
        ),
        encoding="utf-8",
    )

    src_path = tmp_path / "source.json"
    src_path.write_text(json.dumps([{"name": "App", "version": "1.0.0", "link": "https://example.com/nope.zip"}]))
    monkeypatch.setenv("PLAYCOVER_SOURCES", f"file://{src_path}")

    exit_code = run(dry_run=False)

    assert exit_code == 0
    report = json.loads(Path("output/last-run.json").read_text(encoding="utf-8"))
    assert report["status"] == "partial"
    assert not Path("output/catalog.json").exists()


@pytest.mark.skipif(
    __import__("sys").platform == "win32",
    reason="file:// URIs with backslashes are not supported by urllib on Windows",
)
def test_html_source_reports_actionable_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config/defaults.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "sourceName": "x",
                "sourceAuthor": "x",
                "sourceImage": "x",
                "sourceDescription": "x",
                "appCategories": ["Apps"],
                "defaultAppType": "SELF_SIGN",
                "fallbackAppImage": "x",
            }
        ),
        encoding="utf-8",
    )

    html_path = tmp_path / "source.html"
    html_path.write_text("<html><body>Just a moment...</body></html>", encoding="utf-8")
    monkeypatch.setenv("PLAYCOVER_SOURCES", f"file://{html_path}")

    exit_code = run(dry_run=False)

    assert exit_code == 0
    report = json.loads(Path("output/last-run.json").read_text(encoding="utf-8"))
    assert report["status"] == "partial"
    assert report["sourceErrors"]
    assert "HTML" in report["sourceErrors"][0]["error"]


# ---------------------------------------------------------------------------
# Новые тесты — multi-source архитектура
# ---------------------------------------------------------------------------

from src.models.canonical import CanonicalApp
from src.models.source_config import SourceConfig
from src.services.deduplicator import deduplicate
from src.services.validator import validate_app, validate_apps


def _make_source(sid: str = "test", priority: int = 50) -> SourceConfig:
    return SourceConfig(
        id=sid,
        name=f"Test Source {sid}",
        type="playcover_json",
        catalog_url="https://example.com/source.json",
        adapter="playcover_json",
        priority=priority,
    )


def _make_app(
    name: str = "TestApp",
    bundle_id: str | None = "com.test.app",
    version: str | None = "1.0",
    download_url: str | None = "https://example.com/app.ipa",
    source_id: str = "test",
    source_priority: int = 50,
) -> CanonicalApp:
    return CanonicalApp(
        source_id=source_id,
        bundle_id=bundle_id,
        name=name,
        version=version,
        download_url=download_url,
        app_page_url=None,
        icon_url=None,
        itunes_lookup=None,
        availability="public" if download_url else "unknown",
        requires_auth=False,
        raw={"_source_priority": source_priority},
    )


class TestCanonicalApp:
    def test_is_exportable_true(self):
        app = _make_app()
        assert app.is_exportable is True

    def test_is_exportable_no_download_url(self):
        app = _make_app(download_url=None)
        assert app.is_exportable is False

    def test_dedup_key_bundle_id(self):
        app = _make_app(bundle_id="com.Foo.Bar")
        assert app.dedup_key() == "bundle:com.foo.bar"

    def test_dedup_key_fallback_name_ver(self):
        app = _make_app(bundle_id=None, name="My App", version="2.0")
        assert app.dedup_key() == "name_ver:my app|2.0"

    def test_metadata_score(self):
        app = _make_app()
        assert app.metadata_score() >= 2


class TestDeduplicator:
    def test_dedup_by_bundle_id(self):
        a1 = _make_app(version="1.0", source_priority=50)
        a2 = _make_app(version="1.1", source_priority=10)  # более высокий приоритет (меньше число)
        deduped, removed = deduplicate([a1, a2])
        assert removed == 1
        assert len(deduped) == 1
        assert deduped[0].raw["_source_priority"] == 10

    def test_dedup_keeps_download_url(self):
        # Одинаковый приоритет источника → побеждает тот, у кого есть download_url
        a_no_dl = _make_app(download_url=None, source_priority=50)
        a_with_dl = _make_app(download_url="https://example.com/app.ipa", source_priority=50)
        deduped, removed = deduplicate([a_no_dl, a_with_dl])
        assert removed == 1
        assert deduped[0].download_url is not None

    def test_different_bundle_ids_not_deduped(self):
        a1 = _make_app(bundle_id="com.foo.app")
        a2 = _make_app(bundle_id="com.bar.app")
        deduped, removed = deduplicate([a1, a2])
        assert removed == 0
        assert len(deduped) == 2

    def test_dedup_empty_list(self):
        deduped, removed = deduplicate([])
        assert deduped == []
        assert removed == 0


class TestValidator:
    def test_valid_app_no_errors(self):
        app = _make_app()
        assert validate_app(app) == []

    def test_missing_name(self):
        app = _make_app(name="")
        errors = validate_app(app)
        assert any("name" in e for e in errors)

    def test_invalid_download_url_scheme(self):
        app = _make_app(download_url="ftp://example.com/app.ipa")
        errors = validate_app(app)
        assert any("scheme" in e for e in errors)

    def test_validate_apps_filters_invalid(self):
        good = _make_app(name="Good App")
        bad = _make_app(name="")
        valid, warnings = validate_apps([good, bad])
        assert len(valid) == 1
        assert len(warnings) == 1


class TestPlayCoverJsonAdapter:
    def test_fetch_with_file_url(self, tmp_path):
        from src.adapters.playcover_json import PlayCoverJsonAdapter

        data = [
            {"bundleID": "com.test.app", "name": "TestApp", "version": "1.0", "link": "https://x.com/app.ipa"},
            {"name": "NoLink"},
        ]
        src_file = tmp_path / "source.json"
        src_file.write_text(json.dumps(data), encoding="utf-8")

        source = SourceConfig(
            id="pc-test",
            name="PC Test",
            type="playcover_json",
            catalog_url=src_file.as_uri(),
            adapter="playcover_json",
        )
        adapter = PlayCoverJsonAdapter(source)
        result = adapter.fetch()

        assert result.success is True
        assert result.apps_found == 2
        # Только первое приложение имеет валидный .ipa link
        assert len(result.apps) == 2
        exportable = [a for a in result.apps if a.is_exportable]
        assert len(exportable) == 1
        assert exportable[0].bundle_id == "com.test.app"

    def test_fetch_html_returns_error(self, tmp_path):
        from src.adapters.playcover_json import PlayCoverJsonAdapter

        html_file = tmp_path / "page.html"
        html_file.write_text("<html><body>Just a moment...</body></html>", encoding="utf-8")

        source = SourceConfig(
            id="pc-html",
            name="PC HTML",
            type="playcover_json",
            catalog_url=html_file.as_uri(),
            adapter="playcover_json",
        )
        adapter = PlayCoverJsonAdapter(source)
        result = adapter.fetch()

        assert result.success is False
        assert result.error is not None
        assert "HTML" in result.error

    def test_fetch_non_array_returns_error(self, tmp_path):
        from src.adapters.playcover_json import PlayCoverJsonAdapter

        json_file = tmp_path / "bad.json"
        json_file.write_text(json.dumps({"key": "value"}), encoding="utf-8")

        source = SourceConfig(
            id="pc-bad",
            name="PC Bad",
            type="playcover_json",
            catalog_url=json_file.as_uri(),
            adapter="playcover_json",
        )
        adapter = PlayCoverJsonAdapter(source)
        result = adapter.fetch()

        assert result.success is False
        assert "array" in result.error.lower()


class TestRegistry:
    def test_load_sources_valid(self, tmp_path):
        from src.registry import load_sources

        sources_json = [
            {
                "id": "src1",
                "name": "Source 1",
                "type": "playcover_json",
                "adapter": "playcover_json",
                "catalogUrl": "https://example.com/s.json",
            }
        ]
        path = tmp_path / "sources.json"
        path.write_text(json.dumps(sources_json), encoding="utf-8")

        sources = load_sources(path)
        assert len(sources) == 1
        assert sources[0].id == "src1"

    def test_load_sources_missing_field(self, tmp_path):
        from src.registry import load_sources, RegistryError

        path = tmp_path / "sources.json"
        path.write_text(json.dumps([{"id": "x", "name": "X"}]), encoding="utf-8")

        with pytest.raises(RegistryError, match="missing required field"):
            load_sources(path)

    def test_load_sources_duplicate_id(self, tmp_path):
        from src.registry import load_sources, RegistryError

        entry = {
            "id": "dup",
            "name": "Dup",
            "type": "playcover_json",
            "adapter": "playcover_json",
            "catalogUrl": "https://example.com/s.json",
        }
        path = tmp_path / "sources.json"
        path.write_text(json.dumps([entry, entry]), encoding="utf-8")

        with pytest.raises(RegistryError, match="Duplicate source id"):
            load_sources(path)

    def test_load_enabled_sources_filters_disabled(self, tmp_path):
        from src.registry import load_enabled_sources

        sources_json = [
            {
                "id": "enabled",
                "name": "Enabled",
                "type": "playcover_json",
                "adapter": "playcover_json",
                "catalogUrl": "https://example.com/s.json",
                "enabled": True,
                "priority": 10,
            },
            {
                "id": "disabled",
                "name": "Disabled",
                "type": "playcover_json",
                "adapter": "playcover_json",
                "catalogUrl": "https://example.com/s2.json",
                "enabled": False,
                "priority": 5,
            },
        ]
        path = tmp_path / "sources.json"
        path.write_text(json.dumps(sources_json), encoding="utf-8")

        sources = load_enabled_sources(path)
        assert len(sources) == 1
        assert sources[0].id == "enabled"


class TestOrchestratorRun:
    def _setup_env(self, tmp_path):
        (tmp_path / "config").mkdir()
        (tmp_path / "output").mkdir()
        (tmp_path / "config" / "defaults.json").write_text(
            json.dumps({
                "version": "1.0",
                "sourceName": "Test",
                "sourceAuthor": "Test",
                "sourceImage": "https://example.com/img.png",
                "sourceDescription": "Test catalog",
                "appCategories": ["Apps"],
                "defaultAppType": "SELF_SIGN",
                "fallbackAppImage": "https://example.com/icon.png",
            }),
            encoding="utf-8",
        )

    def test_no_enabled_sources_is_skipped(self, tmp_path, monkeypatch):
        from src.orchestrator import run

        monkeypatch.chdir(tmp_path)
        self._setup_env(tmp_path)

        sources_path = tmp_path / "config" / "sources.json"
        sources_path.write_text(json.dumps([
            {
                "id": "disabled",
                "name": "Disabled",
                "type": "playcover_json",
                "adapter": "playcover_json",
                "catalogUrl": "https://example.com/s.json",
                "enabled": False,
            }
        ]), encoding="utf-8")

        code = run(sources_path=sources_path, report_path=tmp_path / "output" / "last-run.json")
        assert code == 0
        report = json.loads((tmp_path / "output" / "last-run.json").read_text())
        assert report["status"] == "skipped"

    def test_valid_source_produces_catalog(self, tmp_path, monkeypatch):
        from src.orchestrator import run

        monkeypatch.chdir(tmp_path)
        self._setup_env(tmp_path)

        ipa_data = [
            {
                "bundleID": "com.test.app",
                "name": "TestApp",
                "version": "2.0",
                "link": "https://example.com/testapp.ipa",
            }
        ]
        ipa_file = tmp_path / "source.json"
        ipa_file.write_text(json.dumps(ipa_data), encoding="utf-8")

        sources_path = tmp_path / "config" / "sources.json"
        sources_path.write_text(json.dumps([
            {
                "id": "local",
                "name": "Local",
                "type": "playcover_json",
                "adapter": "playcover_json",
                "catalogUrl": ipa_file.as_uri(),
                "enabled": True,
                "priority": 10,
            }
        ]), encoding="utf-8")

        output_path = tmp_path / "output" / "catalog.json"
        code = run(
            sources_path=sources_path,
            output_path=output_path,
            report_path=tmp_path / "output" / "last-run.json",
            status_path=tmp_path / "output" / "sources-status.json",
        )
        assert code == 0
        assert output_path.exists()
        catalog = json.loads(output_path.read_text())
        assert catalog["appRepositories"]
        assert catalog["appRepositories"][0]["appName"] == "TestApp"

    def test_partial_when_no_exportable_apps(self, tmp_path, monkeypatch):
        from src.orchestrator import run

        monkeypatch.chdir(tmp_path)
        self._setup_env(tmp_path)

        ipa_data = [{"name": "App", "version": "1.0", "link": "https://example.com/nope.zip"}]
        ipa_file = tmp_path / "source.json"
        ipa_file.write_text(json.dumps(ipa_data), encoding="utf-8")

        sources_path = tmp_path / "config" / "sources.json"
        sources_path.write_text(json.dumps([
            {
                "id": "local",
                "name": "Local",
                "type": "playcover_json",
                "adapter": "playcover_json",
                "catalogUrl": ipa_file.as_uri(),
                "enabled": True,
            }
        ]), encoding="utf-8")

        output_path = tmp_path / "output" / "catalog.json"
        code = run(
            sources_path=sources_path,
            output_path=output_path,
            report_path=tmp_path / "output" / "last-run.json",
            status_path=tmp_path / "output" / "sources-status.json",
        )
        assert code == 0
        report = json.loads((tmp_path / "output" / "last-run.json").read_text())
        assert report["status"] == "partial"
        assert not output_path.exists()
