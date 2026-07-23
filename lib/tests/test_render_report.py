"""Tests for lib.render_report shared rendering module."""

from __future__ import annotations

from pathlib import Path

import pytest

from render_report import (
    apply_max_per_day,
    collect_entries,
    collect_source_counts,
    emit_quality_warning,
    filter_entries,
    format_item,
    format_reference,
    group_by_date,
    rank_hint_value,
    render_markdown,
    resolve_skill_dir,
    sort_entries,
)


@pytest.fixture
def sample_entries():
    return [
        {
            "original_title": "Article A",
            "url": "https://a.com/1",
            "publish_date": "2026-07-23",
            "source": "Src1",
            "en_summary": "English A",
            "cn_title": "中文A",
            "cn_summary": "中文概述A",
            "collected_at": "2026-07-23T10:00:00",
            "rank_hint": 1,
        },
        {
            "original_title": "Article B",
            "url": "https://b.com/2",
            "publish_date": "2026-07-22",
            "source": "Src2",
            "en_summary": "English B",
            "cn_title": "中文B",
            "cn_summary": "中文概述B",
            "collected_at": "2026-07-22T10:00:00",
            "rank_hint": 2,
        },
        {
            "original_title": "Article C",
            "url": "https://c.com/3",
            "publish_date": "2026-07-23",
            "source": "Src1",
            "en_summary": "English C",
            "cn_title": "中文C",
            "cn_summary": "中文概述C",
            "collected_at": "2026-07-23T11:00:00",
        },
    ]


class TestRankHintValue:
    def test_with_int(self):
        assert rank_hint_value({"rank_hint": 1}) == 1.0

    def test_with_none(self):
        assert rank_hint_value({}) == float("inf")

    def test_with_invalid(self):
        assert rank_hint_value({"rank_hint": "bad"}) == float("inf")


class TestSortEntries:
    def test_sorts_by_hint_then_date(self, sample_entries):
        result = sort_entries(sample_entries)
        assert result[0]["rank_hint"] == 1
        assert result[1]["rank_hint"] == 2
        assert "rank_hint" not in result[2]


class TestGroupByDate:
    def test_groups_and_orders(self, sample_entries):
        groups = group_by_date(sample_entries)
        assert len(groups) == 2
        assert groups[0][0] == "2026-07-23"
        assert groups[1][0] == "2026-07-22"


class TestApplyMaxPerDay:
    def test_none_returns_all(self, sample_entries):
        assert apply_max_per_day(sample_entries, None) == sample_entries

    def test_zero_returns_all(self, sample_entries):
        assert apply_max_per_day(sample_entries, 0) == sample_entries

    def test_limits_per_day(self, sample_entries):
        result = apply_max_per_day(sample_entries, 1)
        assert len(result) == 2


class TestFormatItem:
    def test_basic(self):
        entry = {
            "cn_title": "测试",
            "url": "https://x.com/1",
            "cn_summary": "概述",
            "source": "Src",
            "publish_date": "2026-07-23",
        }
        result = format_item(entry)
        assert "测试" in result
        assert "https://x.com/1" in result


class TestFormatReference:
    def test_basic(self):
        entry = {
            "original_title": "Test",
            "url": "https://x.com/1",
        }
        result = format_reference(1, entry)
        assert result == "1. [Test](https://x.com/1)"


class TestRenderMarkdown:
    def test_includes_title_and_subtitle(self, sample_entries):
        result = render_markdown("2026-07-24", sample_entries, "AI 行业动态", "本周 AI 行业动态")
        assert "2026-07-24 AI 行业动态" in result
        assert "本周 AI 行业动态" in result

    def test_reference_section(self, sample_entries):
        result = render_markdown("2026-07-24", sample_entries, "AI 行业动态", "本周 AI 行业动态")
        assert "### 参考来源" in result


class TestEmitQualityWarning:
    def test_no_warning_when_enough(self, capsys):
        assert emit_quality_warning(10, quality_min=5) is False
        captured = capsys.readouterr()
        assert "QUALITY_WARNING" not in captured.err

    def test_warning_when_low(self, capsys):
        assert emit_quality_warning(2, quality_min=5) is True
        captured = capsys.readouterr()
        assert "QUALITY_WARNING" in captured.err


class TestFilterEntries:
    def test_in_range(self, sample_entries):
        in_range, excluded = filter_entries(sample_entries, "2026-07-22", "2026-07-23")
        assert len(in_range) == 3

    def test_out_of_range(self, sample_entries):
        in_range, excluded = filter_entries(sample_entries, "2026-07-23", "2026-07-24")
        assert len(in_range) == 2
        assert len(excluded) == 1


class TestCollectSourceCounts:
    def test_counts(self, sample_entries):
        counts = collect_source_counts(sample_entries)
        assert counts["Src1"] == 2
        assert counts["Src2"] == 1


class TestResolveSkillDir:
    def test_missing_end_date(self, tmp_path):
        with pytest.raises(SystemExit):
            resolve_skill_dir("", "ai-trends", tmp_path)

    def test_missing_dir(self, tmp_path):
        with pytest.raises(SystemExit):
            resolve_skill_dir("2026-07-24", "ai-trends", tmp_path)

    def test_found_dir(self, tmp_path):
        skill_dir = tmp_path / "2026-07-24" / "ai-trends"
        skill_dir.mkdir(parents=True)
        result = resolve_skill_dir("2026-07-24", "ai-trends", tmp_path)
        assert result == skill_dir
