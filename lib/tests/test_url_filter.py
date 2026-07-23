"""Unit tests for url_filter heuristics and include/exclude rules."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from url_filter import (  # noqa: E402
    builtin_path_ok,
    has_junk_path,
    path_depth,
    url_allowed,
)

LIST_TC = "https://techcrunch.com/category/artificial-intelligence"
LIST_VERGE = "https://www.theverge.com/ai-artificial-intelligence"
LIST_UNKNOWN = "https://example.com/blog"


class TestPathHelpers:
    def test_path_depth_and_junk(self):
        assert path_depth("/posts/in-range") == 2
        assert path_depth("/about") == 1
        assert has_junk_path("/category/ai") is True
        assert has_junk_path("/tag/llm/") is True
        assert has_junk_path("/author/jane") is True
        assert has_junk_path("/page/2") is True
        assert has_junk_path("/posts/in-range") is False


class TestBuiltinHeuristics:
    def test_techcrunch_date_path(self):
        ok = "https://techcrunch.com/2026/07/20/openai-ships-widget/"
        bad = "https://techcrunch.com/category/artificial-intelligence"
        assert builtin_path_ok(ok, LIST_TC) is True
        assert builtin_path_ok(bad, LIST_TC) is False

    def test_verge_ai_id_path(self):
        ok = "https://www.theverge.com/ai-artificial-intelligence/12345/model-news"
        bad = "https://www.theverge.com/ai-artificial-intelligence"
        assert builtin_path_ok(ok, LIST_VERGE) is True
        assert builtin_path_ok(bad, LIST_VERGE) is False

    def test_unknown_same_site_depth(self):
        assert (
            builtin_path_ok("https://example.com/posts/in-range", LIST_UNKNOWN) is True
        )
        assert builtin_path_ok("https://example.com/about", LIST_UNKNOWN) is False
        assert (
            builtin_path_ok("https://other.com/posts/in-range", LIST_UNKNOWN) is False
        )
        assert (
            builtin_path_ok("https://example.com/tag/ai/posts", LIST_UNKNOWN) is False
        )


class TestUrlAllowed:
    def test_exclude_wins(self):
        url = "https://example.com/posts/keep-me"
        assert (
            url_allowed(
                url,
                list_url=LIST_UNKNOWN,
                url_include=[r"/posts/"],
                url_exclude=[r"keep-me"],
            )
            is False
        )

    def test_include_required_when_set(self):
        assert (
            url_allowed(
                "https://example.com/posts/a",
                list_url=LIST_UNKNOWN,
                url_include=[r"/articles/"],
            )
            is False
        )
        assert (
            url_allowed(
                "https://example.com/articles/a",
                list_url=LIST_UNKNOWN,
                url_include=[r"/articles/"],
            )
            is True
        )

    def test_falls_back_to_heuristic_without_include(self):
        assert (
            url_allowed(
                "https://example.com/posts/in-range",
                list_url=LIST_UNKNOWN,
            )
            is True
        )
        assert (
            url_allowed(
                "https://example.com/category/ai",
                list_url=LIST_UNKNOWN,
            )
            is False
        )
