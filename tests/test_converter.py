from src.convert import dedupe_apps, parse_sources
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
