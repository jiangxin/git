"""Tests for lib.check_helpers shared check module."""

from __future__ import annotations

from pathlib import Path

import pytest

from check_helpers import (
    check_summaries,
    check_url,
    format_result,
    get_url_index,
    resolve_skill_dir,
)


class TestResolveSkillDir:
    def test_missing_end_date(self, tmp_path):
        with pytest.raises(SystemExit):
            resolve_skill_dir("", "ai-trends", tmp_path)

    def test_missing_dir(self, tmp_path):
        with pytest.raises(SystemExit):
            resolve_skill_dir("2026-07-24", "ai-trends", tmp_path)

    def test_found_dir(self, tmp_path):
        skill_dir = tmp_path / "2026-07-24" / "git-news"
        skill_dir.mkdir(parents=True)
        result = resolve_skill_dir("2026-07-24", "git-news", tmp_path)
        assert result == skill_dir


class TestCheckSummaries:
    def test_empty_when_no_sites(self, tmp_path):
        skill_dir = tmp_path / "2026-07-24" / "test-skill"
        skill_dir.mkdir(parents=True)
        result = check_summaries(skill_dir)
        assert result == {"summarized": 0, "missing": 0, "sites": 0}

    def test_counts_correctly(self, tmp_path):
        skill_dir = tmp_path / "2026-07-24" / "test-skill"
        sites_dir = skill_dir / "sites" / "test-site" / "articles"
        sites_dir.mkdir(parents=True)

        meta = sites_dir / "abc123.meta.json"
        meta.write_text('{"url":"https://x.com","status":"fetched","source":"Test","hash":"abc123","publish_date":"2026-07-23"}')

        result = check_summaries(skill_dir)
        assert result["missing"] == 1
        assert result["summarized"] == 0
        assert result["sites"] == 1


class TestFormatResult:
    def test_format(self):
        counts = {"summarized": 10, "missing": 2, "sites": 3}
        result = format_result(counts)
        assert "summarized=10" in result
        assert "missing=2" in result
        assert "sites=3" in result


class TestGetUrlIndex:
    def test_missing_end_date(self):
        with pytest.raises(SystemExit):
            get_url_index("", "ai-trends")

    def test_missing_file(self, tmp_path):
        with pytest.raises(SystemExit):
            get_url_index("2026-07-24", "ai-trends", root_override=tmp_path)

    def test_loads_file(self, tmp_path):
        skill_dir = tmp_path / "2026-07-24" / "ai-trends"
        skill_dir.mkdir(parents=True)
        idx_path = skill_dir / "url_index.jsonl"
        idx_path.write_text('{"url":"https://x.com","site":"test","hash":"h1","at":"2026-07-24"}\n')
        result = get_url_index("2026-07-24", "ai-trends", root_override=tmp_path)
        assert "https://x.com" in result


class TestCheckUrl:
    def test_found(self):
        index = {"https://x.com": {"site": "test"}}
        result = check_url(index, "https://x.com")
        assert result == {"site": "test"}

    def test_not_found(self):
        index = {"https://x.com": {"site": "test"}}
        result = check_url(index, "https://y.com")
        assert result is None
