"""Tests for lib/pagination.py — HTML pagination loop with date early-stop."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pagination import paginate_html_discovery  # noqa: E402


def make_pages(pages: dict[str, str]) -> dict[str, str]:
    """Helper: page URL -> HTML mapping."""
    return pages


def make_fetcher(pages: dict[str, str]):
    """Return a fetch function that serves pages from a dict."""
    def fetch(url: str) -> str:
        if url in pages:
            return pages[url]
        raise RuntimeError(f"404: {url}")
    return fetch


def make_extractor(items_by_url: dict[str, list[dict]]):
    """Return an extract function that returns items keyed by URL."""
    def extract(html: str, url: str) -> list[dict]:
        return items_by_url.get(url, [])
    return extract


class TestBasicPagination:
    def test_single_page_no_next(self):
        pages = {
            "https://example.com/blog": "<html><body>page 1</body></html>",
        }
        items = {
            "https://example.com/blog": [
                {"url": "https://example.com/a1", "publish_date": "2026-07-15"},
            ],
        }
        result, errors = paginate_html_discovery(
            "https://example.com/blog",
            fetch_page_fn=make_fetcher(pages),
            extract_links_fn=make_extractor(items),
            max_pages=5,
            start_date="2026-07-11",
        )
        assert len(result) == 1
        assert len(errors) == 0

    def test_two_pages_with_next_link(self):
        pages = {
            "https://example.com/blog": """
                <html><body>
                <a rel="next" href="/blog?page=2">Next</a>
                </body></html>
            """,
            "https://example.com/blog?page=2": "<html><body>page 2</body></html>",
        }
        items = {
            "https://example.com/blog": [
                {"url": "https://example.com/a1", "publish_date": "2026-07-15"},
            ],
            "https://example.com/blog?page=2": [
                {"url": "https://example.com/a2", "publish_date": "2026-07-14"},
            ],
        }
        result, errors = paginate_html_discovery(
            "https://example.com/blog",
            fetch_page_fn=make_fetcher(pages),
            extract_links_fn=make_extractor(items),
            max_pages=5,
            start_date="2026-07-11",
        )
        assert len(result) == 2
        assert errors == []

    def test_max_pages_limit(self):
        # All pages have next links, but max_pages=2 should stop after page 2
        pages = {
            "https://example.com/blog": '<a rel="next" href="/blog?page=2">Next</a>',
            "https://example.com/blog?page=2": '<a rel="next" href="/blog?page=3">Next</a>',
            "https://example.com/blog?page=3": "<html>page 3</html>",
        }
        items = {
            "https://example.com/blog": [{"url": "https://example.com/a1", "publish_date": "2026-07-15"}],
            "https://example.com/blog?page=2": [{"url": "https://example.com/a2", "publish_date": "2026-07-14"}],
            "https://example.com/blog?page=3": [{"url": "https://example.com/a3", "publish_date": "2026-07-13"}],
        }
        result, _ = paginate_html_discovery(
            "https://example.com/blog",
            fetch_page_fn=make_fetcher(pages),
            extract_links_fn=make_extractor(items),
            max_pages=2,
            start_date="2026-07-11",
        )
        assert len(result) == 2  # Only page 1 and 2


class TestDateEarlyStop:
    def test_all_items_older_stops_pagination(self):
        pages = {
            "https://example.com/blog": '<a rel="next" href="/blog?page=2">Next</a>',
            "https://example.com/blog?page=2": "<html>page 2</html>",
        }
        items = {
            "https://example.com/blog": [
                {"url": "https://example.com/a1", "publish_date": "2026-07-05"},
            ],
            "https://example.com/blog?page=2": [
                {"url": "https://example.com/a2", "publish_date": "2026-07-04"},
            ],
        }
        result, _ = paginate_html_discovery(
            "https://example.com/blog",
            fetch_page_fn=make_fetcher(pages),
            extract_links_fn=make_extractor(items),
            max_pages=5,
            start_date="2026-07-11",
        )
        # Early stop: page 1 items all older than start_date, don't fetch page 2
        assert len(result) == 1

    def test_mixed_dates_does_not_early_stop(self):
        # Page has items both in-range and out-of-range — should continue
        pages = {
            "https://example.com/blog": '<a rel="next" href="/blog?page=2">Next</a>',
            "https://example.com/blog?page=2": "<html>page 2</html>",
        }
        items = {
            "https://example.com/blog": [
                {"url": "https://example.com/a1", "publish_date": "2026-07-15"},
                {"url": "https://example.com/a2", "publish_date": "2026-07-05"},
            ],
            "https://example.com/blog?page=2": [
                {"url": "https://example.com/a3", "publish_date": "2026-07-14"},
            ],
        }
        result, _ = paginate_html_discovery(
            "https://example.com/blog",
            fetch_page_fn=make_fetcher(pages),
            extract_links_fn=make_extractor(items),
            max_pages=5,
            start_date="2026-07-11",
        )
        assert len(result) == 3  # All 3 items from both pages

    def test_undated_items_do_not_trigger_early_stop(self):
        pages = {
            "https://example.com/blog": '<a rel="next" href="/blog?page=2">Next</a>',
            "https://example.com/blog?page=2": "<html>page 2</html>",
        }
        items = {
            "https://example.com/blog": [
                {"url": "https://example.com/a1"},  # no publish_date
            ],
            "https://example.com/blog?page=2": [
                {"url": "https://example.com/a2", "publish_date": "2026-07-15"},
            ],
        }
        result, _ = paginate_html_discovery(
            "https://example.com/blog",
            fetch_page_fn=make_fetcher(pages),
            extract_links_fn=make_extractor(items),
            max_pages=5,
            start_date="2026-07-11",
        )
        assert len(result) == 2


class TestErrorHandling:
    def test_fetch_failure_returns_collected_items(self):
        pages = {
            "https://example.com/blog": '<a rel="next" href="/blog?page=2">Next</a>',
            # page 2 will 404
        }
        items = {
            "https://example.com/blog": [
                {"url": "https://example.com/a1", "publish_date": "2026-07-15"},
            ],
        }
        result, errors = paginate_html_discovery(
            "https://example.com/blog",
            fetch_page_fn=make_fetcher(pages),
            extract_links_fn=make_extractor(items),
            max_pages=5,
            start_date="2026-07-11",
        )
        assert len(result) == 1  # Got page 1 items
        assert len(errors) == 1  # page 2 failed
        assert errors[0][0] == "pagination"

    def test_first_page_failure_returns_empty(self):
        result, errors = paginate_html_discovery(
            "https://example.com/blog",
            fetch_page_fn=make_fetcher({}),  # all 404
            extract_links_fn=make_extractor({}),
            max_pages=5,
            start_date="2026-07-11",
        )
        assert result == []
        assert len(errors) == 1


class TestDeduplication:
    def test_duplicate_urls_across_pages(self):
        pages = {
            "https://example.com/blog": '<a rel="next" href="/blog?page=2">Next</a>',
            "https://example.com/blog?page=2": "<html>page 2</html>",
        }
        items = {
            "https://example.com/blog": [
                {"url": "https://example.com/a1", "publish_date": "2026-07-15"},
            ],
            "https://example.com/blog?page=2": [
                {"url": "https://example.com/a1", "publish_date": "2026-07-15"},  # duplicate
                {"url": "https://example.com/a2", "publish_date": "2026-07-14"},
            ],
        }
        result, _ = paginate_html_discovery(
            "https://example.com/blog",
            fetch_page_fn=make_fetcher(pages),
            extract_links_fn=make_extractor(items),
            max_pages=5,
            start_date="2026-07-11",
        )
        assert len(result) == 2  # a1 deduped, a2 added
        urls = [item["url"] for item in result]
        assert urls.count("https://example.com/a1") == 1


class TestKnownUrlEarlyStop:
    def test_stops_when_entire_page_known(self):
        fetched: list[str] = []

        def tracking_fetch(url: str) -> str:
            fetched.append(url)
            pages = {
                "https://example.com/blog": '<a rel="next" href="/blog?page=2">Next</a>',
                "https://example.com/blog?page=2": "<html>page 2</html>",
            }
            if url not in pages:
                raise RuntimeError(f"404: {url}")
            return pages[url]

        items = {
            "https://example.com/blog": [
                {"url": "https://example.com/a1", "publish_date": "2026-07-20"},
                {"url": "https://example.com/a2", "publish_date": "2026-07-19"},
            ],
            "https://example.com/blog?page=2": [
                {"url": "https://example.com/a3", "publish_date": "2026-07-10"},
            ],
        }
        known = {"https://example.com/a1", "https://example.com/a2"}
        result, errors = paginate_html_discovery(
            "https://example.com/blog",
            fetch_page_fn=tracking_fetch,
            extract_links_fn=make_extractor(items),
            max_pages=5,
            start_date="2026-07-11",
            known_urls=known,
        )
        assert errors == []
        assert len(result) == 2
        assert "https://example.com/blog?page=2" not in fetched
