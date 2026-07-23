"""Tests for discover_and_fetch.py — local HTML fixtures, no network."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from discover_and_fetch import (  # noqa: E402
    FetchError,
    date_allows,
    extract_links,
    extract_text,
    format_summary,
    run,
)
from check_cloudflare import is_cloudflare  # noqa: E402

END_DATE = "2026-07-24"
START_DATE = "2026-07-18"

LIST_HTML = """<!DOCTYPE html>
<html><head><title>Blog</title></head>
<body>
  <h1>Posts</h1>
  <ul>
    <li>
      <a href="/posts/in-range" data-date="2026-07-20">In Range Article</a>
    </li>
    <li>
      <a href="/posts/already-archived" data-date="2026-07-19">Already Archived</a>
    </li>
    <li>
      <a href="/posts/out-of-range" data-date="2026-06-01">Out Of Range</a>
    </li>
    <li>
      <a href="/posts/unknown-date">Unknown Date Article</a>
    </li>
    <li>
      <a href="/assets/logo.png">Logo</a>
    </li>
  </ul>
</body></html>
"""

DETAIL_HTML = """<!DOCTYPE html>
<html><head><title>Detail</title></head>
<body>
  <script>var x = 1;</script>
  <style>.x{color:red}</style>
  <article>
    <h1>Article Body</h1>
    <p>Hello world content for testing.</p>
  </article>
</body></html>
"""

CF_HTML = """<!DOCTYPE html>
<html><body>
Checking your browser before accessing example.com
cdn-cgi/challenge-platform
Enable JavaScript and cookies to continue
</body></html>
"""


@pytest.fixture
def week_env(tmp_path):
    """Build weekly/<end_date>/ai-trends/ plus a tiny sources.json."""

    def _make(archives=None, sources=None, end_date=END_DATE):
        weekly_root = tmp_path / "weekly"
        ai_trends = weekly_root / end_date / "ai-trends"
        ai_trends.mkdir(parents=True)
        archives_path = ai_trends / "archives.json"
        archives_path.write_text(
            json.dumps(archives if archives is not None else [], ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        sources_path = tmp_path / "sources.json"
        if sources is None:
            sources = [
                {
                    "name": "Fixture Blog",
                    "url": "https://example.com/blog",
                    "use_proxy": False,
                    "fallback": "skip",
                }
            ]
        sources_path.write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n")
        return weekly_root, ai_trends, sources_path

    return _make


def make_fetch(pages: dict[str, str]):
    """Return a fetch_fn that serves local HTML only (raises if missing)."""

    def _fetch(url: str, *, proxy=None, use_proxy_flag: bool = False, timeout: int = 30) -> str:
        if url not in pages:
            raise FetchError(url, "curl(direct)", f"not in fixture map: {url}")
        return pages[url]

    return _fetch


class TestExtractLinks:
    def test_stable_link_extraction(self):
        links = extract_links(LIST_HTML, "https://example.com/blog")
        urls = [x["url"] for x in links]
        assert urls == [
            "https://example.com/posts/in-range",
            "https://example.com/posts/already-archived",
            "https://example.com/posts/out-of-range",
            "https://example.com/posts/unknown-date",
        ]
        by_url = {x["url"]: x for x in links}
        assert by_url["https://example.com/posts/in-range"]["publish_date"] == "2026-07-20"
        assert by_url["https://example.com/posts/out-of-range"]["publish_date"] == "2026-06-01"
        assert by_url["https://example.com/posts/unknown-date"]["publish_date"] is None
        assert by_url["https://example.com/posts/in-range"]["original_title"] == "In Range Article"


class TestDateAllows:
    def test_unknown_may_enter(self):
        assert date_allows(None, START_DATE, END_DATE) is True

    def test_out_of_range_excluded(self):
        assert date_allows("2026-06-01", START_DATE, END_DATE) is False

    def test_in_range_included(self):
        assert date_allows("2026-07-20", START_DATE, END_DATE) is True


class TestCloudflare:
    def test_fixture_detected(self):
        assert is_cloudflare(CF_HTML) is True
        assert is_cloudflare(LIST_HTML) is False


class TestDiscoverAndFetchRun:
    def test_archives_dedupe_and_date_filters(self, week_env):
        weekly_root, ai_trends, sources_path = week_env(
            archives=[
                {
                    "url": "https://example.com/posts/already-archived",
                    "original_title": "Old",
                    "publish_date": "2026-07-19",
                    "source": "Fixture Blog",
                }
            ]
        )
        pages = {
            "https://example.com/blog": LIST_HTML,
            "https://example.com/posts/in-range": DETAIL_HTML,
            "https://example.com/posts/unknown-date": DETAIL_HTML,
        }
        counts = run(
            START_DATE,
            END_DATE,
            weekly_root=weekly_root,
            sources_path=sources_path,
            proxy=None,
            fetch_fn=make_fetch(pages),
            save_raw=True,
        )

        pending = json.loads((ai_trends / "pending.json").read_text(encoding="utf-8"))
        pending_urls = {e["url"] for e in pending}

        assert "https://example.com/posts/already-archived" not in pending_urls
        assert "https://example.com/posts/out-of-range" not in pending_urls
        assert "https://example.com/posts/in-range" in pending_urls
        assert "https://example.com/posts/unknown-date" in pending_urls

        in_range = next(e for e in pending if e["url"].endswith("/in-range"))
        assert in_range["original_title"] == "In Range Article"
        assert in_range["publish_date"] == "2026-07-20"
        assert in_range["source"] == "Fixture Blog"
        assert "Hello world content" in in_range["content"]
        assert "var x" not in in_range["content"]
        assert in_range["fetched_at"]

        raw_files = list((ai_trends / "raw").glob("*.txt"))
        assert len(raw_files) >= 1

        assert counts["sources"] == 1
        assert counts["pending"] == 2
        assert counts["skipped"] >= 2
        assert counts["errors"] == 0
        assert format_summary(counts).startswith("sources=1 pending=2")

    def test_cloudflare_list_page_skips_source(self, week_env):
        weekly_root, ai_trends, sources_path = week_env(archives=[])
        pages = {"https://example.com/blog": CF_HTML}
        counts = run(
            START_DATE,
            END_DATE,
            weekly_root=weekly_root,
            sources_path=sources_path,
            proxy=None,
            fetch_fn=make_fetch(pages),
            save_raw=False,
        )

        pending = json.loads((ai_trends / "pending.json").read_text(encoding="utf-8"))
        assert pending == []
        assert counts["pending"] == 0
        assert counts["errors"] == 1

        error_log = (ai_trends / "error.log").read_text(encoding="utf-8")
        assert "Cloudflare challenge" in error_log
        assert "https://example.com/blog" in error_log

    def test_overwrite_pending_each_run(self, week_env):
        weekly_root, ai_trends, sources_path = week_env(archives=[])
        (ai_trends / "pending.json").write_text(
            json.dumps([{"url": "https://stale.example/old"}], indent=2) + "\n"
        )
        pages = {
            "https://example.com/blog": LIST_HTML,
            "https://example.com/posts/in-range": DETAIL_HTML,
            "https://example.com/posts/unknown-date": DETAIL_HTML,
        }
        run(
            START_DATE,
            END_DATE,
            weekly_root=weekly_root,
            sources_path=sources_path,
            fetch_fn=make_fetch(pages),
            save_raw=False,
        )
        pending = json.loads((ai_trends / "pending.json").read_text(encoding="utf-8"))
        assert all(e["url"] != "https://stale.example/old" for e in pending)
        assert len(pending) == 2


class TestExtractText:
    def test_strips_script_style_and_truncates(self):
        full = extract_text(DETAIL_HTML)
        assert "Hello world content" in full
        assert "var x" not in full
        assert ".x{color" not in full
        truncated = extract_text(DETAIL_HTML, max_chars=20)
        assert len(truncated) <= 20
        assert truncated == full[:20]
