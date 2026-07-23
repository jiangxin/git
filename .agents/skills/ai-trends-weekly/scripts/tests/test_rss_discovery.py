"""Tests for RSS/Atom parse and discovery fallback routing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from discover_and_fetch import (  # noqa: E402
    CONTENT_MIN,
    FetchError,
    discover_source_items,
    run,
)
from restricted_search import (  # noqa: E402
    SearchSkipped,
    build_site_query,
    resolve_search_config,
    restricted_search,
)
from rss_parse import parse_feed, parse_feed_date  # noqa: E402

END_DATE = "2026-07-24"
START_DATE = "2026-07-18"

_DETAIL_BODY = (
    "Hello world content for testing. "
    "This paragraph expands the article body so the content length gate "
    "accepts fixture pages used across discover_and_fetch unit tests. "
    "Additional sentences keep the extracted text well above the minimum "
    "threshold while remaining easy to assert on in tests. "
) * 3
assert len(_DETAIL_BODY) >= CONTENT_MIN

DETAIL_HTML = f"""<!DOCTYPE html>
<html><head><title>Detail</title>
<meta property="og:title" content="OG Detail Title" />
</head>
<body><article><p>{_DETAIL_BODY}</p></article></body></html>
"""

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Fixture Feed</title>
    <item>
      <title>In Range Article</title>
      <link>https://example.com/posts/in-range</link>
      <pubDate>Mon, 20 Jul 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Out Of Range</title>
      <link>https://example.com/posts/out-of-range</link>
      <pubDate>Sun, 01 Jun 2026 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

ATOM_XML = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Fixture Atom</title>
  <entry>
    <title>Atom In Range</title>
    <link href="https://example.com/posts/atom-in-range" rel="alternate"/>
    <published>2026-07-21T10:00:00Z</published>
  </entry>
</feed>
"""

FALLBACK_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Fallback Hit</title>
    <link>https://example.com/posts/fallback-hit</link>
    <pubDate>Tue, 21 Jul 2026 08:00:00 GMT</pubDate>
  </item>
</channel></rss>
"""


@pytest.fixture
def week_env(tmp_path):
    def _make(archives=None, sources=None, end_date=END_DATE):
        weekly_root = tmp_path / "weekly"
        ai_trends = weekly_root / end_date / "ai-trends"
        ai_trends.mkdir(parents=True)
        (ai_trends / "archives.json").write_text(
            json.dumps(archives if archives is not None else [], indent=2) + "\n",
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
        sources_path.write_text(json.dumps(sources, indent=2) + "\n")
        return weekly_root, ai_trends, sources_path

    return _make


def make_fetch(pages: dict[str, str]):
    def _fetch(url: str, *, proxy=None, use_proxy_flag: bool = False, timeout: int = 30) -> str:
        if url not in pages:
            raise FetchError(url, "curl(direct)", f"not in fixture map: {url}")
        return pages[url]

    return _fetch


class TestRssParse:
    def test_rss20_items_and_rfc822_dates(self):
        items = parse_feed(RSS_XML)
        assert len(items) == 2
        by_url = {x["url"]: x for x in items}
        assert by_url["https://example.com/posts/in-range"]["original_title"] == (
            "In Range Article"
        )
        assert by_url["https://example.com/posts/in-range"]["publish_date"] == "2026-07-20"
        assert by_url["https://example.com/posts/out-of-range"]["publish_date"] == "2026-06-01"

    def test_atom_entries(self):
        items = parse_feed(ATOM_XML)
        assert len(items) == 1
        assert items[0]["url"] == "https://example.com/posts/atom-in-range"
        assert items[0]["original_title"] == "Atom In Range"
        assert items[0]["publish_date"] == "2026-07-21"

    def test_malformed_returns_empty(self):
        assert parse_feed("<not-xml") == []
        assert parse_feed("") == []

    def test_parse_feed_date_matrix(self):
        assert parse_feed_date("2026-07-20") == "2026-07-20"
        assert parse_feed_date("2026-07-20T12:00:00Z") == "2026-07-20"
        assert parse_feed_date("Mon, 20 Jul 2026 12:00:00 GMT") == "2026-07-20"
        assert parse_feed_date(None) is None
        assert parse_feed_date("not-a-date") is None


class TestDiscoverRouting:
    def test_rss_url_preferred_over_html(self):
        source = {
            "name": "Fixture Blog",
            "url": "https://example.com/blog",
            "rss_url": "https://example.com/feed.xml",
            "use_proxy": False,
            "fallback": "skip",
        }
        pages = {
            "https://example.com/feed.xml": RSS_XML,
            # HTML must not be fetched when RSS succeeds
        }
        fetch_log: list[str] = []

        def tracking(url: str, *, proxy=None, use_proxy_flag: bool = False, timeout: int = 30):
            fetch_log.append(url)
            return make_fetch(pages)(url, proxy=proxy, use_proxy_flag=use_proxy_flag)

        items, errs = discover_source_items(
            source,
            start_date=START_DATE,
            end_date=END_DATE,
            use_proxy=False,
            proxy=None,
            fetch_fn=tracking,
        )
        assert fetch_log == ["https://example.com/feed.xml"]
        assert [x["url"] for x in items] == [
            "https://example.com/posts/in-range",
            "https://example.com/posts/out-of-range",
        ]
        assert errs == []

    def test_aggregate_fallback_uses_fallback_rss_url(self):
        source = {
            "name": "Fixture Blog",
            "url": "https://example.com/blog",
            "use_proxy": False,
            "fallback": "aggregate",
            "fallback_rss_url": "https://example.com/backup.xml",
        }
        pages = {
            # list page fails
            "https://example.com/backup.xml": FALLBACK_RSS,
        }

        def fetch(url: str, *, proxy=None, use_proxy_flag: bool = False, timeout: int = 30):
            if url == "https://example.com/blog":
                raise FetchError(url, "curl(direct)", "HTTP 403")
            return make_fetch(pages)(url, proxy=proxy, use_proxy_flag=use_proxy_flag)

        items, errs = discover_source_items(
            source,
            start_date=START_DATE,
            end_date=END_DATE,
            use_proxy=False,
            proxy=None,
            fetch_fn=fetch,
        )
        assert [x["url"] for x in items] == ["https://example.com/posts/fallback-hit"]
        assert items[0]["publish_date"] == "2026-07-21"
        assert any("HTTP 403" in reason for _m, _u, reason in errs)

    def test_aggregate_probes_common_feed_paths(self):
        source = {
            "name": "Fixture Blog",
            "url": "https://example.com/blog",
            "use_proxy": False,
            "fallback": "aggregate",
        }

        def fetch(url: str, *, proxy=None, use_proxy_flag: bool = False, timeout: int = 30):
            if url == "https://example.com/blog":
                raise FetchError(url, "curl(direct)", "HTTP 500")
            if url == "https://example.com/feed":
                return FALLBACK_RSS
            raise FetchError(url, "curl(direct)", "HTTP 404")

        items, _errs = discover_source_items(
            source,
            start_date=START_DATE,
            end_date=END_DATE,
            use_proxy=False,
            proxy=None,
            fetch_fn=fetch,
        )
        assert items[0]["url"] == "https://example.com/posts/fallback-hit"

    def test_search_fallback_invokes_search_fn(self):
        source = {
            "name": "Fixture Blog",
            "url": "https://example.com/blog",
            "use_proxy": False,
            "fallback": "search",
        }
        called: dict[str, object] = {}

        def fetch(url: str, *, proxy=None, use_proxy_flag: bool = False, timeout: int = 30):
            raise FetchError(url, "curl(direct)", "HTTP 403")

        def search_fn(**kwargs):
            called.update(kwargs)
            return [
                {
                    "url": "https://example.com/posts/search-hit",
                    "original_title": "Search Hit",
                    "publish_date": "2026-07-22",
                }
            ]

        items, errs = discover_source_items(
            source,
            start_date=START_DATE,
            end_date=END_DATE,
            use_proxy=False,
            proxy=None,
            fetch_fn=fetch,
            search_fn=search_fn,
            search_cfg={"provider": "serper", "api_key": "test"},
        )
        assert items[0]["url"] == "https://example.com/posts/search-hit"
        assert called["source_name"] == "Fixture Blog"
        assert called["start_date"] == START_DATE

    def test_search_without_key_skips(self):
        source = {
            "name": "Fixture Blog",
            "url": "https://example.com/blog",
            "use_proxy": False,
            "fallback": "search",
        }

        def fetch(url: str, *, proxy=None, use_proxy_flag: bool = False, timeout: int = 30):
            raise FetchError(url, "curl(direct)", "HTTP 403")

        items, errs = discover_source_items(
            source,
            start_date=START_DATE,
            end_date=END_DATE,
            use_proxy=False,
            proxy=None,
            fetch_fn=fetch,
            search_cfg=None,
        )
        assert items == []
        assert any("search API key not configured" in r for _m, _u, r in errs)

    def test_skip_fallback_logs_and_returns_empty(self):
        source = {
            "name": "Fixture Blog",
            "url": "https://example.com/blog",
            "use_proxy": False,
            "fallback": "skip",
        }

        def fetch(url: str, *, proxy=None, use_proxy_flag: bool = False, timeout: int = 30):
            raise FetchError(url, "curl(direct)", "Cloudflare challenge")

        items, errs = discover_source_items(
            source,
            start_date=START_DATE,
            end_date=END_DATE,
            use_proxy=False,
            proxy=None,
            fetch_fn=fetch,
        )
        assert items == []
        assert any("fallback=skip" in r for _m, _u, r in errs)


class TestRestrictedSearchHelpers:
    def test_resolve_search_config_from_env(self):
        assert resolve_search_config({}, env={}) is None
        cfg = resolve_search_config(
            {"search_api": {"provider": "serper", "api_key_env": "MY_KEY"}},
            env={"MY_KEY": "abc"},
        )
        assert cfg == {"provider": "serper", "api_key": "abc"}

    def test_build_site_query(self):
        q = build_site_query("OpenAI News", "https://openai.com/news", "2026-07-18", "2026-07-24")
        assert "site:openai.com" in q
        assert "after:2026-07-18" in q
        assert "before:2026-07-24" in q

    def test_restricted_search_raises_without_key(self):
        with pytest.raises(SearchSkipped, match="not configured"):
            restricted_search(
                source_name="X",
                list_url="https://example.com/",
                start_date=START_DATE,
                end_date=END_DATE,
                search_cfg=None,
            )


class TestRunWithRss:
    def test_run_uses_rss_and_fetches_detail(self, week_env):
        weekly_root, ai_trends, sources_path = week_env(
            sources=[
                {
                    "name": "Fixture Blog",
                    "url": "https://example.com/blog",
                    "rss_url": "https://example.com/feed.xml",
                    "use_proxy": False,
                    "fallback": "skip",
                    # example.com has no builtin pattern; allow deep paths via include
                    "url_include": [r"/posts/"],
                }
            ]
        )
        pages = {
            "https://example.com/feed.xml": RSS_XML,
            "https://example.com/posts/in-range": DETAIL_HTML,
        }
        counts = run(
            START_DATE,
            END_DATE,
            weekly_root=weekly_root,
            sources_path=sources_path,
            fetch_fn=make_fetch(pages),
            save_raw=False,
        )
        pending = json.loads((ai_trends / "pending.json").read_text(encoding="utf-8"))
        assert counts["pending"] == 1
        assert pending[0]["url"] == "https://example.com/posts/in-range"
        assert pending[0]["publish_date"] == "2026-07-20"

    def test_run_search_fallback_without_key_counts_error(self, week_env):
        weekly_root, ai_trends, sources_path = week_env(
            sources=[
                {
                    "name": "Fixture Blog",
                    "url": "https://example.com/blog",
                    "use_proxy": False,
                    "fallback": "search",
                }
            ]
        )

        def fetch(url: str, *, proxy=None, use_proxy_flag: bool = False, timeout: int = 30):
            raise FetchError(url, "curl(direct)", "HTTP 403")

        counts = run(
            START_DATE,
            END_DATE,
            weekly_root=weekly_root,
            sources_path=sources_path,
            fetch_fn=fetch,
            save_raw=False,
            search_cfg=None,
        )
        assert counts["pending"] == 0
        assert counts["errors"] == 1
        log = (ai_trends / "error.log").read_text(encoding="utf-8")
        assert "search API key not configured" in log
