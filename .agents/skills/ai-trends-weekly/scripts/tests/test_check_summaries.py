"""Tests for check_summaries.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from check_summaries import check, format_result, resolve_ai_trends_dir  # noqa: E402
from site_store import claim_url  # noqa: E402
from summary_io import write_summary  # noqa: E402

VALID_SUMMARY = {
    "en_summary": "English summary text.",
    "cn_title": "中文标题",
    "cn_summary": "中文概述内容。",
    "collected_at": "2026-07-23T11:30:00",
}


@pytest.fixture
def ai_trends(tmp_path):
    d = tmp_path / "weekly" / "2026-07-24" / "ai-trends"
    d.mkdir(parents=True)
    return d


def _seed_article(ai_trends, slug, url, body="c" * 500, status="fetched"):
    r = claim_url(
        ai_trends,
        url=url,
        slug=slug,
        meta={"original_title": "T", "source": "s", "status": status},
        body=body,
    )
    assert r.won
    return r


class TestResolveAiTrendsDir:
    def test_missing_end_date_exits(self):
        with pytest.raises(SystemExit):
            resolve_ai_trends_dir("")

    def test_missing_dir_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            resolve_ai_trends_dir("2026-07-24", weekly_root=tmp_path / "nope")

    def test_found(self, ai_trends):
        result = resolve_ai_trends_dir("2026-07-24", weekly_root=ai_trends.parents[1])
        assert result == ai_trends


class TestCheck:
    def test_empty_sites(self, ai_trends):
        counts = check(ai_trends)
        assert counts == {"summarized": 0, "missing": 0, "sites": 0}

    def test_no_sites_dir(self, tmp_path):
        ai = tmp_path / "empty"
        ai.mkdir()
        counts = check(ai)
        assert counts == {"summarized": 0, "missing": 0, "sites": 0}

    def test_all_summarized(self, ai_trends):
        _seed_article(ai_trends, "s1", "https://e.com/1")
        _seed_article(ai_trends, "s1", "https://e.com/2")
        from summary_io import summary_path
        for url in ["https://e.com/1", "https://e.com/2"]:
            from site_store import url_hash
            h = url_hash(url)
            sp = summary_path(ai_trends, "s1", h)
            write_summary(sp, VALID_SUMMARY)
        counts = check(ai_trends)
        assert counts["summarized"] == 2
        assert counts["missing"] == 0
        assert counts["sites"] == 1

    def test_missing_one_summary(self, ai_trends):
        _seed_article(ai_trends, "s1", "https://e.com/1")
        _seed_article(ai_trends, "s1", "https://e.com/2")
        from summary_io import summary_path
        from site_store import url_hash
        sp = summary_path(ai_trends, "s1", url_hash("https://e.com/1"))
        write_summary(sp, VALID_SUMMARY)
        counts = check(ai_trends)
        assert counts["summarized"] == 1
        assert counts["missing"] == 1

    def test_skips_non_terminal_status(self, ai_trends):
        _seed_article(ai_trends, "s1", "https://e.com/err", status="error")
        counts = check(ai_trends)
        assert counts["summarized"] == 0
        assert counts["missing"] == 0
        assert counts["sites"] == 0

    def test_counts_sites_not_articles(self, ai_trends):
        _seed_article(ai_trends, "s1", "https://e.com/1")
        _seed_article(ai_trends, "s1", "https://e.com/2")
        _seed_article(ai_trends, "s2", "https://e.com/3")
        counts = check(ai_trends)
        assert counts["sites"] == 2
        assert counts["missing"] == 3

    def test_invalid_summary_counts_as_missing(self, ai_trends):
        _seed_article(ai_trends, "s1", "https://e.com/1")
        from summary_io import summary_path
        from site_store import url_hash
        sp = summary_path(ai_trends, "s1", url_hash("https://e.com/1"))
        sp.write_text("---\nen_summary: only-one-field\n---\n")
        counts = check(ai_trends)
        assert counts["missing"] == 1
        assert counts["summarized"] == 0

    def test_cached_status_included(self, ai_trends):
        _seed_article(ai_trends, "s1", "https://e.com/1", status="cached")
        from summary_io import summary_path
        from site_store import url_hash
        sp = summary_path(ai_trends, "s1", url_hash("https://e.com/1"))
        write_summary(sp, VALID_SUMMARY)
        counts = check(ai_trends)
        assert counts["summarized"] == 1
        assert counts["missing"] == 0


class TestFormatResult:
    def test_format(self):
        assert format_result({"summarized": 5, "missing": 0, "sites": 2}) == (
            "OK: summarized=5 missing=0 sites=2"
        )


class TestMainExitCode:
    def test_exit_0_when_complete(self, ai_trends, monkeypatch, capsys):
        _seed_article(ai_trends, "s", "https://e.com/1")
        from summary_io import summary_path
        from site_store import url_hash
        sp = summary_path(ai_trends, "s", url_hash("https://e.com/1"))
        write_summary(sp, VALID_SUMMARY)
        import check_summaries
        monkeypatch.setattr(check_summaries, "resolve_ai_trends_dir", lambda *a, **kw: ai_trends)
        monkeypatch.setattr(sys, "argv", ["check_summaries.py", "--end-date", "2026-07-24"])
        check_summaries.main()
        out = capsys.readouterr().out
        assert "summarized=1" in out
        assert "missing=0" in out

    def test_exit_1_when_missing(self, ai_trends, monkeypatch):
        _seed_article(ai_trends, "s", "https://e.com/1")
        import check_summaries
        monkeypatch.setattr(check_summaries, "resolve_ai_trends_dir", lambda *a, **kw: ai_trends)
        monkeypatch.setattr(sys, "argv", ["check_summaries.py", "--end-date", "2026-07-24"])
        with pytest.raises(SystemExit) as exc:
            check_summaries.main()
        assert exc.value.code == 1
