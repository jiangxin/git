"""Tests for lib/list_fetch_cache.py."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from list_fetch_cache import (  # noqa: E402
    ListFetchCache,
    parse_known_url_streak_stop,
    parse_list_cache_ttl_seconds,
)


class TestListFetchCache:
    def test_store_lookup_roundtrip(self, tmp_path):
        cache = ListFetchCache(cache_dir=tmp_path)
        cache.store(
            "https://example.com/feed",
            "<rss/>",
            etag='"abc"',
            last_modified="Wed, 01 Jan 2026 00:00:00 GMT",
        )
        hit = cache.lookup("https://example.com/feed")
        assert hit is not None
        assert hit.body == "<rss/>"
        assert hit.etag == '"abc"'
        assert hit.is_fresh(1800)

    def test_ttl_expiry(self, tmp_path):
        cache = ListFetchCache(cache_dir=tmp_path)
        cache.store("https://example.com/feed", "body", fetched_at=time.time() - 100)
        hit = cache.lookup("https://example.com/feed")
        assert hit is not None
        assert hit.is_fresh(30) is False
        assert hit.is_fresh(200) is True

    def test_touch_refreshes_timestamp(self, tmp_path):
        cache = ListFetchCache(cache_dir=tmp_path)
        cache.store(
            "https://example.com/feed",
            "body",
            etag='"x"',
            fetched_at=time.time() - 1000,
        )
        touched = cache.touch("https://example.com/feed")
        assert touched is not None
        assert touched.is_fresh(60)
        assert touched.body == "body"
        assert touched.etag == '"x"'

    def test_parse_config(self):
        assert parse_list_cache_ttl_seconds({"list_cache_ttl_seconds": 60}) == 60
        assert parse_list_cache_ttl_seconds({"list_cache_ttl_seconds": 0}) == 0
        assert parse_list_cache_ttl_seconds(None) == 1800
        assert parse_known_url_streak_stop({"known_url_streak_stop": 8}) == 8
        assert parse_known_url_streak_stop({"known_url_streak_stop": 0}) == 0
