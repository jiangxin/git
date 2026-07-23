"""Tests for json_archives.py — shared JSON loading, saving, and merging."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from json_archives import load_json_array, merge_by_key, save_json_atomic


class TestLoadJsonArray:
    def test_valid_array(self, tmp_path):
        p = tmp_path / "data.json"
        p.write_text('[{"a":1}]')
        result = load_json_array(p, "data.json")
        assert result == [{"a": 1}]

    def test_empty_file_exits(self, tmp_path):
        p = tmp_path / "data.json"
        p.write_text("")
        with pytest.raises(SystemExit) as exc:
            load_json_array(p, "data.json")
        assert exc.value.code == 3

    def test_malformed_json_exits(self, tmp_path):
        p = tmp_path / "data.json"
        p.write_text('[{"a": 1')
        with pytest.raises(SystemExit) as exc:
            load_json_array(p, "data.json")
        assert exc.value.code == 3

    def test_non_array_root_exits(self, tmp_path):
        p = tmp_path / "data.json"
        p.write_text('{"key": "value"}')
        with pytest.raises(SystemExit) as exc:
            load_json_array(p, "data.json")
        assert exc.value.code == 3

    def test_empty_array(self, tmp_path):
        p = tmp_path / "data.json"
        p.write_text("[]")
        assert load_json_array(p, "data.json") == []


class TestSaveJsonAtomic:
    def test_creates_file(self, tmp_path):
        target = tmp_path / "out.json"
        save_json_atomic([{"x": 1}], target)
        assert target.exists()
        data = json.loads(target.read_text())
        assert data == [{"x": 1}]

    def test_replaces_existing(self, tmp_path):
        target = tmp_path / "out.json"
        target.write_text("old")
        save_json_atomic([1, 2, 3], target)
        assert json.loads(target.read_text()) == [1, 2, 3]

    def test_no_tmp_file_remains(self, tmp_path):
        target = tmp_path / "out.json"
        save_json_atomic([], target)
        assert not (tmp_path / "out.json.tmp").exists()


class TestMergeByKey:
    def test_deduplicates_by_url(self):
        archives = [{"url": "http://a.com", "title": "A"}]
        new = [
            {"url": "http://a.com", "title": "A dup"},
            {"url": "http://b.com", "title": "B"},
        ]
        merged, added = merge_by_key(archives, new, "url")
        assert added == 1
        assert len(merged) == 2
        assert merged[1]["url"] == "http://b.com"

    def test_deduplicates_by_articleId(self):
        archives = [{"articleId": 100}]
        new = [{"articleId": 100}, {"articleId": 200}]
        merged, added = merge_by_key(archives, new, "articleId")
        assert added == 1
        assert len(merged) == 2

    def test_empty_archives(self):
        merged, added = merge_by_key([], [{"id": 1}, {"id": 2}], "id")
        assert added == 2
        assert len(merged) == 2

    def test_empty_new(self):
        merged, added = merge_by_key([{"id": 1}], [], "id")
        assert added == 0
        assert len(merged) == 1

    def test_none_key_handling(self):
        archives = [{"other": "field"}]
        new = [{"other": "new"}]
        # Both have None for missing key — first one "takes" the None slot
        merged, added = merge_by_key(archives, new, "id")
        assert added == 0
