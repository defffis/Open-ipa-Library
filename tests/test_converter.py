import json
from pathlib import Path

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
