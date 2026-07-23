"""Tests for render_ai_trends.py — fixed archives fixtures, structure assertions."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from render_ai_trends import (  # noqa: E402
    format_item,
    render_markdown,
    run,
    sort_entries,
)

END_DATE = "2026-05-10"
START_DATE = "2026-05-03"


def make_entry(
    i: int,
    *,
    publish_date: str = "2026-05-05",
    rank_hint=None,
    source: str = "Test Source",
) -> dict:
    entry = {
        "original_title": f"Original Title {i}",
        "en_summary": f"English summary {i}.",
        "cn_title": f"中文标题 {i}",
        "cn_summary": f"中文概述 {i}",
        "url": f"https://example.com/article-{i}",
        "publish_date": publish_date,
        "source": source,
        "collected_at": "2026-05-10T10:00:00",
    }
    if rank_hint is not None:
        entry["rank_hint"] = rank_hint
    return entry


@pytest.fixture
def week_env(tmp_path):
    """Build weekly/<end_date>/ai-trends/archives.json."""

    def _make(archives, end_date=END_DATE):
        weekly_root = tmp_path / "weekly"
        ai_trends = weekly_root / end_date / "ai-trends"
        ai_trends.mkdir(parents=True)
        (ai_trends / "archives.json").write_text(
            json.dumps(archives, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return weekly_root, ai_trends

    return _make


def test_format_item_shape():
    entry = make_entry(1, publish_date="2026-05-05", source="Anthropic Blog")
    line = format_item(entry)
    assert line == (
        "* **[中文标题 1](https://example.com/article-1)**："
        "中文概述 1。📰 Anthropic Blog 📅 2026-05-05"
    )


def test_sort_rank_hint_before_date():
    """rank_hint ascending wins over newer publish_date."""
    entries = [
        make_entry(1, publish_date="2026-05-09"),  # no hint → inf
        make_entry(2, publish_date="2026-05-04", rank_hint=1),
        make_entry(3, publish_date="2026-05-08", rank_hint=2),
        make_entry(4, publish_date="2026-05-07"),  # no hint, newer than #1's peers
    ]
    sorted_ = sort_entries(entries)
    # hint 1 → hint 2 → no-hint by date desc (1 newer than 4)
    assert [e["cn_title"] for e in sorted_] == [
        "中文标题 2",
        "中文标题 3",
        "中文标题 1",
        "中文标题 4",
    ]


def test_sort_same_hint_date_desc():
    entries = [
        make_entry(1, publish_date="2026-05-04", rank_hint=1),
        make_entry(2, publish_date="2026-05-08", rank_hint=1),
        make_entry(3, publish_date="2026-05-06", rank_hint=1),
    ]
    sorted_ = sort_entries(entries)
    assert [e["publish_date"] for e in sorted_] == [
        "2026-05-08",
        "2026-05-06",
        "2026-05-04",
    ]


def test_render_le_10_no_details():
    entries = [make_entry(i, publish_date=f"2026-05-{3 + i:02d}") for i in range(1, 8)]
    md = render_markdown(END_DATE, sort_entries(entries))
    assert f"## {END_DATE} AI 行业动态周报" in md
    assert "### 本周 AI 行业动态" in md
    assert "<details>" not in md
    assert "更多…" not in md
    assert "### 参考来源" in md
    assert md.count("* **[") == 7
    assert re.search(r"^1\. \[Original Title ", md, re.M)
    assert re.search(r"^7\. \[Original Title ", md, re.M)
    assert not re.search(r"^8\. ", md, re.M)


def test_render_11_to_50_has_details():
    entries = [make_entry(i) for i in range(1, 16)]  # 15 items
    md = render_markdown(END_DATE, entries)
    assert "<details>" in md
    assert "<summary>更多…（共 5 篇）</summary>" in md
    assert "</details>" in md
    # 10 visible + 5 in details
    assert md.count("* **[") == 15
    # references cover all 15
    assert re.search(r"^15\. \[Original Title ", md, re.M)
    assert not re.search(r"^16\. ", md, re.M)
    # details section comes before 参考来源
    assert md.index("</details>") < md.index("### 参考来源")


def test_render_over_50_caps_at_50():
    entries = [make_entry(i, rank_hint=i) for i in range(1, 56)]  # 55
    md = render_markdown(END_DATE, sort_entries(entries))
    assert md.count("* **[") == 50
    assert "<summary>更多…（共 40 篇）</summary>" in md
    assert re.search(r"^50\. \[Original Title ", md, re.M)
    assert not re.search(r"^51\. ", md, re.M)
    # 51st+ must not appear
    assert "中文标题 51" not in md
    assert "article-51" not in md


def test_run_filters_out_of_range_and_writes_file(week_env):
    archives = [
        make_entry(1, publish_date="2026-05-05"),
        make_entry(2, publish_date="2026-04-01"),  # out of range
        make_entry(3, publish_date="2026-05-09", rank_hint=1),
        make_entry(4, publish_date="2026-05-20"),  # out of range
    ]
    weekly_root, ai_trends = week_env(archives)
    out = run(START_DATE, END_DATE, weekly_root=weekly_root)
    assert out == ai_trends.parent / "AI-trends.md"
    assert out.is_file()
    md = out.read_text(encoding="utf-8")
    assert "article-1" in md
    assert "article-3" in md
    assert "article-2" not in md
    assert "article-4" not in md
    # rank_hint=1 (entry 3) before entry 1
    pos3 = md.index("中文标题 3")
    pos1 = md.index("中文标题 1")
    assert pos3 < pos1


def test_run_exactly_10_no_details(week_env):
    archives = [make_entry(i, publish_date="2026-05-05") for i in range(1, 11)]
    weekly_root, _ = week_env(archives)
    md = run(START_DATE, END_DATE, weekly_root=weekly_root).read_text(encoding="utf-8")
    assert "<details>" not in md
    assert md.count("* **[") == 10


def test_run_11_items_details_n_is_1(week_env):
    archives = [make_entry(i, publish_date="2026-05-05") for i in range(1, 12)]
    weekly_root, _ = week_env(archives)
    md = run(START_DATE, END_DATE, weekly_root=weekly_root).read_text(encoding="utf-8")
    assert "<summary>更多…（共 1 篇）</summary>" in md
