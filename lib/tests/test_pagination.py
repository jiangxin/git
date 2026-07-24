"""Tests for lib/pagination.py — next-page URL detection."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pagination import discover_next_page_url


class TestLinkRelNext:
    def test_link_tag(self):
        html = """
        <html><head>
        <link rel="next" href="/blog/page/2/">
        </head><body></body></html>
        """
        result = discover_next_page_url(html, "https://example.com/blog/")
        assert result == "https://example.com/blog/page/2/"

    def test_link_tag_absolute(self):
        html = '<link rel="next" href="https://example.com/blog/page/2/">'
        result = discover_next_page_url(html, "https://example.com/blog/")
        assert result == "https://example.com/blog/page/2/"

    def test_a_rel_next(self):
        html = """
        <html><body>
        <a rel="next" href="/articles?page=2">Next</a>
        </body></html>
        """
        result = discover_next_page_url(html, "https://example.com/articles")
        assert result == "https://example.com/articles?page=2"

    def test_link_takes_priority_over_a(self):
        html = """
        <html><head>
        <link rel="next" href="/page/2/">
        </head><body>
        <a rel="next" href="/page/99/">Next</a>
        </body></html>
        """
        result = discover_next_page_url(html, "https://example.com/")
        assert result == "https://example.com/page/2/"

    def test_no_next_returns_none(self):
        html = '<html><body><a href="/about">About</a></body></html>'
        result = discover_next_page_url(html, "https://example.com/")
        assert result is None

    def test_rel_multiple_values(self):
        html = '<link rel="prev next" href="/page/2/">'
        result = discover_next_page_url(html, "https://example.com/")
        assert result == "https://example.com/page/2/"


class TestURLPatternFallback:
    def test_query_page_param(self):
        html = """
        <html><body>
        <a href="/blog">1</a>
        <a href="/blog?page=2">2</a>
        <a href="/blog?page=3">3</a>
        </body></html>
        """
        result = discover_next_page_url(html, "https://example.com/blog?page=1")
        assert result == "https://example.com/blog?page=2"

    def test_query_paged_param(self):
        html = """
        <html><body>
        <a href="/feed?paged=2">next</a>
        </body></html>
        """
        result = discover_next_page_url(html, "https://example.com/feed?paged=1")
        assert result == "https://example.com/feed?paged=2"

    def test_path_page_pattern(self):
        html = """
        <html><body>
        <a href="/blog/page/2/">next</a>
        </body></html>
        """
        result = discover_next_page_url(html, "https://example.com/blog/page/1/")
        assert result == "https://example.com/blog/page/2/"

    def test_no_matching_pattern_returns_none(self):
        html = """
        <html><body>
        <a href="/other">other</a>
        </body></html>
        """
        result = discover_next_page_url(html, "https://example.com/blog?page=1")
        assert result is None

    def test_preserves_other_query_params(self):
        html = """
        <html><body>
        <a href="/search?q=ai&page=2">next</a>
        </body></html>
        """
        result = discover_next_page_url(html, "https://example.com/search?q=ai&page=1")
        assert result is not None
        assert "q=ai" in result
        assert "page=2" in result


class TestEdgeCases:
    def test_empty_html(self):
        assert discover_next_page_url("", "https://example.com/") is None

    def test_malformed_html(self):
        html = '<link rel="next" href="/page/2"'  # unclosed
        result = discover_next_page_url(html, "https://example.com/")
        # HTMLParser is strict about well-formed tags; unclosed tags are not emitted
        assert result is None

    def test_relative_url_resolution(self):
        html = '<a rel="next" href="../page/2/">Next</a>'
        # base is a directory (/blog/page/1/), so ../ goes up to /blog/page/
        # then page/2/ appends → /blog/page/page/2/
        result = discover_next_page_url(html, "https://example.com/blog/page/1/")
        assert result == "https://example.com/blog/page/page/2/"

    def test_case_insensitive_rel(self):
        html = '<link REL="Next" href="/page/2/">'
        result = discover_next_page_url(html, "https://example.com/")
        assert result == "https://example.com/page/2/"
