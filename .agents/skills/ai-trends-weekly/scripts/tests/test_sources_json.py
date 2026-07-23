"""Validate references/sources.json — parseable array with required fields and enums."""

import json
from pathlib import Path

REQUIRED_FIELDS = {"name", "url", "use_proxy", "fallback"}
VALID_USE_PROXY = {True, False, "auto"}
VALID_FALLBACK = {"search", "aggregate", "skip"}
VALID_FETCH = {"http", "browser"}
OPTIONAL_BOOL_FIELDS = {"allow_undated", "browser_on_cloudflare"}
OPTIONAL_LIST_FIELDS = {"url_include", "url_exclude"}
OPTIONAL_NUMBER_FIELDS = {"max_links", "undated_quota"}

SOURCES_PATH = (
    Path(__file__).resolve().parent.parent.parent / "references" / "sources.json"
)


def _assert_http_url(value: object, label: str) -> None:
    assert isinstance(value, str) and value.startswith(("http://", "https://")), (
        f"{label} must be an http(s) URL"
    )


class TestSourcesJson:
    def test_file_exists(self):
        assert SOURCES_PATH.is_file(), f"missing {SOURCES_PATH}"

    def test_parses_as_json_array(self):
        data = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) > 0

    def test_required_fields_and_enums(self):
        data = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
        for i, entry in enumerate(data):
            assert isinstance(entry, dict), f"entry[{i}] must be an object"
            missing = REQUIRED_FIELDS - entry.keys()
            assert not missing, f"entry[{i}] ({entry.get('name')!r}) missing: {missing}"

            assert isinstance(entry["name"], str) and entry["name"].strip(), (
                f"entry[{i}] name must be a non-empty string"
            )
            _assert_http_url(entry["url"], f"entry[{i}] url")

            assert entry["use_proxy"] in VALID_USE_PROXY, (
                f"entry[{i}] ({entry['name']!r}) use_proxy={entry['use_proxy']!r} "
                f"not in {VALID_USE_PROXY}"
            )
            assert entry["fallback"] in VALID_FALLBACK, (
                f"entry[{i}] ({entry['name']!r}) fallback={entry['fallback']!r} "
                f"not in {VALID_FALLBACK}"
            )

    def test_optional_discovery_fields(self):
        data = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
        for i, entry in enumerate(data):
            label = f"entry[{i}] ({entry.get('name')!r})"
            for key in ("rss_url", "fallback_rss_url"):
                if key in entry:
                    _assert_http_url(entry[key], f"{label} {key}")
            if "date_attr" in entry:
                assert isinstance(entry["date_attr"], str) and entry["date_attr"].strip(), (
                    f"{label} date_attr must be a non-empty string"
                )

            for key in OPTIONAL_BOOL_FIELDS:
                if key in entry:
                    assert isinstance(entry[key], bool), f"{label} {key} must be bool"

            for key in OPTIONAL_LIST_FIELDS:
                if key not in entry:
                    continue
                assert isinstance(entry[key], list), f"{label} {key} must be a list"
                assert all(isinstance(x, str) and x for x in entry[key]), (
                    f"{label} {key} must be non-empty strings"
                )

            for key in OPTIONAL_NUMBER_FIELDS:
                if key not in entry:
                    continue
                assert isinstance(entry[key], (int, float)) and not isinstance(
                    entry[key], bool
                ), f"{label} {key} must be a number"
                assert entry[key] >= 0, f"{label} {key} must be >= 0"

            if "fetch" in entry:
                assert entry["fetch"] in VALID_FETCH, (
                    f"{label} fetch={entry['fetch']!r} not in {VALID_FETCH}"
                )

    def test_some_sources_declare_rss_url(self):
        data = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
        with_rss = [e for e in data if isinstance(e.get("rss_url"), str)]
        assert len(with_rss) >= 3, "expected several sources to declare rss_url"
