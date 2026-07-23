"""Validate references/sources.json — parseable array with required fields and enums."""

import json
from pathlib import Path

REQUIRED_FIELDS = {"name", "url", "use_proxy", "fallback"}
VALID_USE_PROXY = {True, False, "auto"}
VALID_FALLBACK = {"search", "aggregate", "skip"}

SOURCES_PATH = (
    Path(__file__).resolve().parent.parent.parent / "references" / "sources.json"
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
            assert isinstance(entry["url"], str) and entry["url"].startswith(
                ("http://", "https://")
            ), f"entry[{i}] url must be an http(s) URL"

            assert entry["use_proxy"] in VALID_USE_PROXY, (
                f"entry[{i}] ({entry['name']!r}) use_proxy={entry['use_proxy']!r} "
                f"not in {VALID_USE_PROXY}"
            )
            assert entry["fallback"] in VALID_FALLBACK, (
                f"entry[{i}] ({entry['name']!r}) fallback={entry['fallback']!r} "
                f"not in {VALID_FALLBACK}"
            )
