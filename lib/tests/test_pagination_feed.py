"""Tests for lib/pagination.py — RSS/Atom feed pagination."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pagination import (  # noqa: E402
    _build_paged_url,
    _detect_feed_next_url,
    paginate_feed_discovery,
)


ATOM_FEED_TEMPLATE = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Test Feed</title>
  {next_link}
  {entries}
</feed>
"""

ATOM_ENTRY = """
  <entry>
    <title>{title}</title>
    <link href="{url}"/>
    <updated>{date}T00:00:00Z</updated>
  </entry>
"""

RSS_FEED_TEMPLATE = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    {items}
  </channel>
</rss>
"""

RSS_ITEM = """
    <item>
      <title>{title}</title>
      <link>{url}</link>
      <pubDate>{date}</pubDate>
    </item>
"""


def make_atom(entries: list[dict], next_url: str | None = None) -> str:
    next_link = f'<link rel="next" href="{next_url}"/>' if next_url else ""
    entry_xml = "\n".join(
        ATOM_ENTRY.format(title=e["title"], url=e["url"], date=e["date"])
        for e in entries
    )
    return ATOM_FEED_TEMPLATE.format(next_link=next_link, entries=entry_xml)


def make_rss(items: list[dict]) -> str:
    items_xml = "\n".join(
        RSS_ITEM.format(title=i["title"], url=i["url"], date=i["date"])
        for i in items
    )
    return RSS_FEED_TEMPLATE.format(items=items_xml)


def make_feed_fetcher(feeds: dict[str, str]):
    def fetch(url: str) -> str:
        if url in feeds:
            return feeds[url]
        raise RuntimeError(f"404: {url}")
    return fetch


def make_feed_parser():
    """A simple mock parser that returns items based on URL."""
    items_by_url: dict[str, list[dict]] = {}

    def register(url: str, items: list[dict]) -> None:
        items_by_url[url] = items

    def parse(xml_text: str, base_url: str) -> list[dict]:
        return items_by_url.get(base_url, [])

    return parse, register


class TestDetectFeedNextUrl:
    def test_atom_next_link(self):
        xml = make_atom([], next_url="https://example.com/feed?page=2")
        result = _detect_feed_next_url(xml, "https://example.com/feed")
        assert result == "https://example.com/feed?page=2"

    def test_atom_no_next_link(self):
        xml = make_atom([])
        result = _detect_feed_next_url(xml, "https://example.com/feed")
        assert result is None

    def test_rss_returns_none(self):
        xml = make_rss([])
        result = _detect_feed_next_url(xml, "https://example.com/feed")
        assert result is None

    def test_malformed_xml(self):
        result = _detect_feed_next_url("<broken", "https://example.com/feed")
        assert result is None


class TestBuildPagedUrl:
    def test_simple_url(self):
        result = _build_paged_url("https://example.com/feed", 2)
        assert result == "https://example.com/feed?paged=2"

    def test_existing_params(self):
        result = _build_paged_url("https://example.com/feed?cat=ai", 3)
        assert "paged=3" in result
        assert "cat=ai" in result

    def test_replace_existing_paged(self):
        result = _build_paged_url("https://example.com/feed?paged=1", 2)
        assert "paged=2" in result
        assert "paged=1" not in result


class TestPaginateFeedDiscovery:
    def test_atom_pagination_via_next_link(self):
        feeds = {
            "https://example.com/feed": make_atom(
                [{"title": "A1", "url": "https://example.com/a1", "date": "2026-07-15"}],
                next_url="https://example.com/feed?page=2",
            ),
            "https://example.com/feed?page=2": make_atom(
                [{"title": "A2", "url": "https://example.com/a2", "date": "2026-07-14"}],
            ),
        }
        parser, register = make_feed_parser()
        register("https://example.com/feed", [{"url": "https://example.com/a1", "publish_date": "2026-07-15"}])
        register("https://example.com/feed?page=2", [{"url": "https://example.com/a2", "publish_date": "2026-07-14"}])

        result, errors = paginate_feed_discovery(
            "https://example.com/feed",
            fetch_feed_fn=make_feed_fetcher(feeds),
            parse_feed_fn=parser,
            max_pages=5,
            start_date="2026-07-11",
        )
        assert len(result) == 2
        assert errors == []

    def test_wordpress_paged_fallback(self):
        # RSS feed without Atom next link — should try ?paged=N
        feeds = {
            "https://example.com/feed": make_rss(
                [{"title": "A1", "url": "https://example.com/a1", "date": "2026-07-15"}],
            ),
            "https://example.com/feed?paged=2": make_rss(
                [{"title": "A2", "url": "https://example.com/a2", "date": "2026-07-14"}],
            ),
        }
        parser, register = make_feed_parser()
        register("https://example.com/feed", [{"url": "https://example.com/a1", "publish_date": "2026-07-15"}])
        register("https://example.com/feed?paged=2", [{"url": "https://example.com/a2", "publish_date": "2026-07-14"}])

        result, errors = paginate_feed_discovery(
            "https://example.com/feed",
            fetch_feed_fn=make_feed_fetcher(feeds),
            parse_feed_fn=parser,
            max_pages=5,
            start_date="2026-07-11",
        )
        assert len(result) == 2

    def test_date_early_stop(self):
        feeds = {
            "https://example.com/feed": make_atom(
                [{"title": "A1", "url": "https://example.com/a1", "date": "2026-07-05"}],
                next_url="https://example.com/feed?page=2",
            ),
            "https://example.com/feed?page=2": make_atom(
                [{"title": "A2", "url": "https://example.com/a2", "date": "2026-07-04"}],
            ),
        }
        parser, register = make_feed_parser()
        register("https://example.com/feed", [{"url": "https://example.com/a1", "publish_date": "2026-07-05"}])
        register("https://example.com/feed?page=2", [{"url": "https://example.com/a2", "publish_date": "2026-07-04"}])

        result, _ = paginate_feed_discovery(
            "https://example.com/feed",
            fetch_feed_fn=make_feed_fetcher(feeds),
            parse_feed_fn=parser,
            max_pages=5,
            start_date="2026-07-11",
        )
        assert len(result) == 1  # Early stop, didn't fetch page 2

    def test_single_page_no_pagination(self):
        feeds = {
            "https://example.com/feed": make_rss(
                [{"title": "A1", "url": "https://example.com/a1", "date": "2026-07-15"}],
            ),
        }
        parser, register = make_feed_parser()
        register("https://example.com/feed", [{"url": "https://example.com/a1", "publish_date": "2026-07-15"}])

        result, errors = paginate_feed_discovery(
            "https://example.com/feed",
            fetch_feed_fn=make_feed_fetcher(feeds),
            parse_feed_fn=parser,
            max_pages=5,
            start_date="2026-07-11",
        )
        assert len(result) == 1
        assert errors == []

    def test_fetch_error_returns_collected(self):
        feeds = {
            "https://example.com/feed": make_atom(
                [{"title": "A1", "url": "https://example.com/a1", "date": "2026-07-15"}],
                next_url="https://example.com/feed?page=2",
            ),
        }
        parser, register = make_feed_parser()
        register("https://example.com/feed", [{"url": "https://example.com/a1", "publish_date": "2026-07-15"}])

        result, errors = paginate_feed_discovery(
            "https://example.com/feed",
            fetch_feed_fn=make_feed_fetcher(feeds),  # page 2 will 404
            parse_feed_fn=parser,
            max_pages=5,
            start_date="2026-07-11",
        )
        assert len(result) == 1
        assert len(errors) == 1

    def test_max_pages_limit(self):
        feeds = {
            "https://example.com/feed": make_atom([], next_url="https://example.com/feed?p=2"),
            "https://example.com/feed?p=2": make_atom([], next_url="https://example.com/feed?p=3"),
            "https://example.com/feed?p=3": make_atom([]),
        }
        parser, register = make_feed_parser()
        register("https://example.com/feed", [{"url": "https://example.com/a1", "publish_date": "2026-07-15"}])
        register("https://example.com/feed?p=2", [{"url": "https://example.com/a2", "publish_date": "2026-07-14"}])
        register("https://example.com/feed?p=3", [{"url": "https://example.com/a3", "publish_date": "2026-07-13"}])

        result, _ = paginate_feed_discovery(
            "https://example.com/feed",
            fetch_feed_fn=make_feed_fetcher(feeds),
            parse_feed_fn=parser,
            max_pages=2,
            start_date="2026-07-11",
        )
        assert len(result) == 2
