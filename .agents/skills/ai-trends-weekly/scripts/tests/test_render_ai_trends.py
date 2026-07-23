"""Tests for render_ai_trends.py — sidecar-based fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from render_ai_trends import (  # noqa: E402
    DEFAULT_QUALITY_MIN,
    apply_max_per_day,
    collect_entries,
    collect_source_counts,
    format_item,
    group_by_date,
    render_html,
    render_markdown,
    run,
    sort_entries,
)
from site_store import claim_url  # noqa: E402
from summary_io import summary_path, write_summary  # noqa: E402

END_DATE = "2026-05-10"
START_DATE = "2026-05-03"

VALID_SUMMARY = {
    "en_summary": "English summary.",
    "cn_title": "中文标题",
    "cn_summary": "中文概述",
    "collected_at": "2026-05-10T10:00:00",
}


def _seed(
    ai_trends, slug, url, *,
    publish_date="2026-05-05", rank_hint=None, source="Test Source",
    with_summary=True,
):
    r = claim_url(
        ai_trends, url=url, slug=slug,
        meta={
            "original_title": f"Title {url}",
            "publish_date": publish_date,
            "source": source,
            "status": "fetched",
        },
        body="c" * 500,
    )
    assert r.won
    if with_summary:
        sp = summary_path(ai_trends, slug, r.hash)
        sdata = dict(VALID_SUMMARY)
        sdata["cn_title"] = f"中文 {url}"
        sdata["cn_summary"] = f"概述 {url}"
        sdata["en_summary"] = f"Summary {url}"
        if rank_hint is not None:
            sdata["rank_hint"] = rank_hint
        write_summary(sp, sdata)
    return r


@pytest.fixture
def week_env(tmp_path):
    def _make(end_date=END_DATE):
        weekly_root = tmp_path / "weekly"
        ai_trends = weekly_root / end_date / "ai-trends"
        ai_trends.mkdir(parents=True)
        return weekly_root, ai_trends
    return _make


def test_format_item_shape():
    entry = {
        "original_title": "Original Title 1",
        "cn_title": "中文标题 1",
        "cn_summary": "中文概述 1",
        "url": "https://example.com/article-1",
        "publish_date": "2026-05-05",
        "source": "Anthropic Blog",
    }
    line = format_item(entry)
    assert "* **[中文标题 1](https://example.com/article-1)**" in line
    assert "中文概述 1" in line
    assert "Anthropic Blog" in line
    assert "2026-05-05" in line


def test_sort_rank_hint_before_date():
    entries = [
        {"publish_date": "2026-05-09"},
        {"publish_date": "2026-05-04", "rank_hint": 1},
        {"publish_date": "2026-05-08", "rank_hint": 2},
        {"publish_date": "2026-05-07"},
    ]
    sorted_ = sort_entries(entries)
    assert [e["publish_date"] for e in sorted_] == [
        "2026-05-04", "2026-05-08", "2026-05-09", "2026-05-07",
    ]


def test_group_by_date_newest_first():
    entries = [
        {"publish_date": "2026-05-04", "rank_hint": 1},
        {"publish_date": "2026-05-08", "rank_hint": 2},
        {"publish_date": "2026-05-08", "rank_hint": 1},
    ]
    groups = group_by_date(entries)
    assert [d for d, _ in groups] == ["2026-05-08", "2026-05-04"]


def test_render_over_50_caps_at_50():
    entries = [{"publish_date": "2026-05-05", "rank_hint": i} for i in range(1, 56)]
    md = render_markdown(END_DATE, sort_entries(entries))
    assert md.count("* **[") == 50


def test_collect_entries_from_sidecars(week_env):
    weekly_root, ai_trends = week_env()
    _seed(ai_trends, "s", "https://e.com/1", publish_date="2026-05-05")
    _seed(ai_trends, "s", "https://e.com/2", publish_date="2026-05-06")
    entries = collect_entries(ai_trends)
    assert len(entries) == 2
    urls = {e["url"] for e in entries}
    assert urls == {"https://e.com/1", "https://e.com/2"}


def test_collect_skips_invalid_summary(week_env):
    weekly_root, ai_trends = week_env()
    _seed(ai_trends, "s", "https://e.com/1", with_summary=False)
    entries = collect_entries(ai_trends)
    assert len(entries) == 0


def test_run_filters_and_renders(week_env):
    weekly_root, ai_trends = week_env()
    _seed(ai_trends, "s", "https://e.com/in1", publish_date="2026-05-05", rank_hint=2)
    _seed(ai_trends, "s", "https://e.com/out1", publish_date="2026-04-01", rank_hint=1)
    _seed(ai_trends, "s", "https://e.com/in2", publish_date="2026-05-09", rank_hint=1)
    out = run(START_DATE, END_DATE, weekly_root=weekly_root)
    md = out.read_text(encoding="utf-8")
    assert "in1" in md
    assert "in2" in md
    assert "out1" not in md


def test_apply_max_per_day_caps():
    entries = [
        {"publish_date": "2026-05-08", "rank_hint": 1},
        {"publish_date": "2026-05-08", "rank_hint": 2},
        {"publish_date": "2026-05-08", "rank_hint": 3},
        {"publish_date": "2026-05-07", "rank_hint": 1},
    ]
    capped = apply_max_per_day(entries, 2)
    assert len([e for e in capped if e["publish_date"] == "2026-05-08"]) == 2


def test_quality_warning(week_env, capsys):
    weekly_root, ai_trends = week_env()
    _seed(ai_trends, "s", "https://e.com/1", publish_date="2026-05-05", rank_hint=1)
    run(START_DATE, END_DATE, weekly_root=weekly_root, quality_min=5)
    err = capsys.readouterr().err
    assert "QUALITY_WARNING" in err


def test_no_quality_warning_when_enough(week_env, capsys):
    weekly_root, ai_trends = week_env()
    for i in range(1, 6):
        _seed(ai_trends, "s", f"https://e.com/{i}", publish_date="2026-05-05", rank_hint=i)
    run(START_DATE, END_DATE, weekly_root=weekly_root, quality_min=DEFAULT_QUALITY_MIN)
    assert "QUALITY_WARNING" not in capsys.readouterr().err


class TestCollectSourceCounts:
    def test_empty(self):
        assert collect_source_counts([]) == {}

    def test_single_source(self):
        entries = [{"source": "A"}, {"source": "A"}, {"source": "A"}]
        assert collect_source_counts(entries) == {"A": 3}

    def test_multiple_sources(self):
        entries = [{"source": "A"}, {"source": "B"}, {"source": "A"}]
        counts = collect_source_counts(entries)
        assert counts == {"A": 2, "B": 1}

    def test_missing_source(self):
        entries = [{"source": "A"}, {}]
        counts = collect_source_counts(entries)
        assert "(unknown)" in counts
        assert counts["(unknown)"] == 1


class TestRenderHtml:
    def test_contains_source_names_and_counts(self):
        entries = [
            {"source": "TechCrunch AI", "url": "https://e.com/1", "cn_title": "T1", "cn_summary": "S1", "original_title": "O1", "publish_date": "2026-05-05"},
            {"source": "TechCrunch AI", "url": "https://e.com/2", "cn_title": "T2", "cn_summary": "S2", "original_title": "O2", "publish_date": "2026-05-05"},
            {"source": "The Verge AI", "url": "https://e.com/3", "cn_title": "T3", "cn_summary": "S3", "original_title": "O3", "publish_date": "2026-05-06"},
        ]
        counts = collect_source_counts(entries)
        html_output = render_html("2026-05-10", entries, counts)
        assert "TechCrunch AI (2)" in html_output
        assert "The Verge AI (1)" in html_output

    def test_contains_data_source_attribute(self):
        entries = [
            {"source": "Src A", "url": "https://e.com/1", "cn_title": "T", "cn_summary": "S", "original_title": "O", "publish_date": "2026-05-05"},
        ]
        counts = collect_source_counts(entries)
        html_output = render_html("2026-05-10", entries, counts)
        assert 'data-source="Src A"' in html_output

    def test_contains_all_and_clear_buttons(self):
        entries = [
            {"source": "X", "url": "https://e.com/1", "cn_title": "T", "cn_summary": "S", "original_title": "O", "publish_date": "2026-05-05"},
        ]
        counts = collect_source_counts(entries)
        html_output = render_html("2026-05-10", entries, counts)
        assert "全部" in html_output
        assert "清空" in html_output
        assert '__all__' in html_output
        assert '__none__' in html_output

    def test_contains_inline_css_and_js(self):
        entries = []
        html_output = render_html("2026-05-10", entries, {})
        assert "<style>" in html_output
        assert "<script>" in html_output


def test_run_generates_html(week_env):
    weekly_root, ai_trends = week_env()
    _seed(ai_trends, "s", "https://e.com/1", publish_date="2026-05-05", source="TestSrc")
    out = run(START_DATE, END_DATE, weekly_root=weekly_root)
    html_path = out.parent / "AI-trends.html"
    assert html_path.is_file()
    content = html_path.read_text(encoding="utf-8")
    assert "TestSrc" in content
    assert "<!DOCTYPE html>" in content
    assert out.is_file()
