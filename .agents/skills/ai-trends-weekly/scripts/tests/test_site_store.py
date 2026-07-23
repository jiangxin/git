"""Tests for site_store.py — slug, claim race, index semantics."""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from site_store import (  # noqa: E402
    append_site_index,
    append_url_index,
    articles_dir,
    body_path,
    claim_url,
    iter_articles,
    load_site_index,
    load_url_index,
    meta_path,
    resolve_unique_slug,
    site_dir,
    site_index_path,
    slugify,
    url_hash,
    url_index_path,
)


class TestSlugify:
    def test_ascii_simple(self):
        assert slugify("Anthropic News") == "anthropic-news"

    def test_ascii_multiple_spaces(self):
        assert slugify("Google   AI   Blog") == "google-ai-blog"

    def test_ascii_punctuation(self):
        assert slugify("TechCrunch: AI & ML") == "techcrunch-ai-ml"

    def test_chinese_keeps_unicode_letters(self):
        slug = slugify("通义千问 Qwen Blog")
        assert "通义千问" in slug
        assert "qwen" in slug
        assert slug.islower() or any(c >= "\u4e00" for c in slug)

    def test_empty_fallback_to_sha_prefix(self):
        slug = slugify("!!!")
        assert slug.startswith("s")
        assert len(slug) == 11

    def test_explicit_slug_takes_priority(self):
        assert slugify("Some Long Name", explicit_slug="my-src") == "my-src"

    def test_invalid_explicit_slug_ignored(self):
        slug = slugify("Hello World", explicit_slug="BAD SLUG!")
        assert slug == "hello-world"

    def test_leading_trailing_dashes_stripped(self):
        assert slugify("--foo--") == "foo"

    def test_dash_runs_collapsed(self):
        assert slugify("a---b") == "a-b"


class TestUrlHash:
    def test_stable(self):
        url = "https://example.com/article"
        assert url_hash(url) == url_hash(url)

    def test_different_urls_differ(self):
        assert url_hash("https://a.com/1") != url_hash("https://a.com/2")

    def test_matches_sha1_length(self):
        assert len(url_hash("https://example.com")) == 40


class TestPathHelpers:
    def test_articles_dir_layout(self, tmp_path):
        ai = tmp_path / "ai-trends"
        assert articles_dir(ai, "anthropic-news") == ai / "sites" / "anthropic-news" / "articles"

    def test_meta_and_body_paths(self, tmp_path):
        ai = tmp_path / "ai-trends"
        h = url_hash("https://example.com/a")
        assert meta_path(ai, "src", h) == ai / "sites" / "src" / "articles" / f"{h}.meta.json"
        assert body_path(ai, "src", h) == ai / "sites" / "src" / "articles" / f"{h}.body.txt"


class TestSiteIndex:
    def test_later_line_wins(self, tmp_path):
        ai = tmp_path / "ai-trends"
        slug = "src"
        p = site_index_path(ai, slug)
        url = "https://example.com/a"
        append_site_index(p, url=url, status="error", hash="abc")
        append_site_index(p, url=url, status="fetched", hash="abc")
        idx = load_site_index(p)
        assert idx[url]["status"] == "fetched"

    def test_empty_when_missing(self, tmp_path):
        assert load_site_index(tmp_path / "missing.jsonl") == {}


class TestUrlIndex:
    def test_first_writer_wins(self, tmp_path):
        ai = tmp_path / "ai-trends"
        ai.mkdir()
        p = url_index_path(ai)
        url = "https://example.com/a"
        wrote_first = append_url_index(p, url=url, site="first", hash="abc")
        wrote_second = append_url_index(p, url=url, site="second", hash="abc")
        assert wrote_first is True
        assert wrote_second is False
        idx = load_url_index(p)
        assert idx[url]["site"] == "first"

    def test_empty_when_missing(self, tmp_path):
        assert load_url_index(tmp_path / "missing.jsonl") == {}

    def test_concurrent_appends_preserve_rows(self, tmp_path):
        ai = tmp_path / "ai-trends"
        ai.mkdir()
        p = url_index_path(ai)
        n = 20

        def writer(i):
            append_url_index(p, url=f"https://e.com/{i}", site="s", hash="h")

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(writer, range(n)))

        idx = load_url_index(p)
        assert len(idx) == n
        lines = [line for line in p.read_text().splitlines() if line.strip()]
        assert len(lines) == n


class TestClaimUrl:
    def test_first_claim_writes_files(self, tmp_path):
        ai = tmp_path / "ai-trends"
        url = "https://example.com/article-1"
        body = "x" * 500
        result = claim_url(
            ai,
            url=url,
            slug="src-a",
            meta={
                "original_title": "Hello",
                "publish_date": "2026-07-20",
                "source": "Source A",
                "status": "fetched",
            },
            body=body,
        )
        assert result.won is True
        assert result.meta_file.is_file()
        assert result.body_file.is_file()
        assert result.body_file.read_text() == body

        meta = json.loads(result.meta_file.read_text())
        assert meta["url"] == url
        assert meta["hash"] == result.hash
        assert meta["site"] == "src-a"

        s_idx = load_site_index(site_index_path(ai, "src-a"))
        assert url in s_idx
        assert s_idx[url]["status"] == "fetched"

        u_idx = load_url_index(url_index_path(ai))
        assert url in u_idx
        assert u_idx[url]["site"] == "src-a"

    def test_parallel_same_site_claim_only_one_wins(self, tmp_path):
        ai = tmp_path / "ai-trends"
        url = "https://example.com/same-article"
        slug = "shared-site"
        bodies = ["A" * 500, "B" * 500, "C" * 500, "D" * 500]
        results = {}

        def worker(i, body):
            r = claim_url(
                ai,
                url=url,
                slug=slug,
                meta={
                    "original_title": f"T-{i}",
                    "source": f"src-{i}",
                    "status": "fetched",
                },
                body=body,
            )
            results[i] = r

        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = [pool.submit(worker, i, b) for i, b in enumerate(bodies)]
            for f in futs:
                f.result()

        winners = [i for i, r in results.items() if r.won]
        losers = [i for i, r in results.items() if not r.won]
        assert len(winners) == 1
        assert len(losers) == 3

        meta_file = meta_path(ai, slug, url_hash(url))
        assert meta_file.is_file()

        s_idx = load_site_index(site_index_path(ai, slug))
        assert url in s_idx
        assert s_idx[url]["status"] == "fetched"

        u_idx = load_url_index(url_index_path(ai))
        assert url in u_idx
        assert u_idx[url]["site"] == slug

    def test_cross_site_claims_both_succeed_but_url_index_first_wins(self, tmp_path):
        ai = tmp_path / "ai-trends"
        url = "https://example.com/same-article"
        r_a = claim_url(
            ai,
            url=url,
            slug="site-a",
            meta={"original_title": "A", "source": "A", "status": "fetched"},
            body="A" * 500,
        )
        r_b = claim_url(
            ai,
            url=url,
            slug="site-b",
            meta={"original_title": "B", "source": "B", "status": "fetched"},
            body="B" * 500,
        )
        assert r_a.won and r_b.won
        u_idx = load_url_index(url_index_path(ai))
        assert u_idx[url]["site"] == "site-a"

    def test_claim_creates_site_directories(self, tmp_path):
        ai = tmp_path / "ai-trends"
        result = claim_url(
            ai,
            url="https://e.com/new",
            slug="brand-new",
            meta={"original_title": "X", "source": "x", "status": "fetched"},
            body="c" * 500,
        )
        assert result.won
        assert site_dir(ai, "brand-new").is_dir()
        assert articles_dir(ai, "brand-new").is_dir()


class TestIterArticles:
    def test_iter_yields_records(self, tmp_path):
        ai = tmp_path / "ai-trends"
        claim_url(
            ai,
            url="https://e.com/one",
            slug="s",
            meta={"original_title": "One", "source": "s", "status": "fetched"},
            body="1" * 500,
        )
        claim_url(
            ai,
            url="https://e.com/two",
            slug="s",
            meta={"original_title": "Two", "source": "s", "status": "fetched"},
            body="2" * 500,
        )
        records = list(iter_articles(ai, "s"))
        assert len(records) == 2
        urls = sorted(r.url for r in records)
        assert urls == ["https://e.com/one", "https://e.com/two"]
        for r in records:
            assert r.site == "s"
            assert r.hash == r.meta["hash"]
            assert len(r.body) == 500

    def test_iter_missing_site_returns_empty(self, tmp_path):
        ai = tmp_path / "ai-trends"
        assert list(iter_articles(ai, "nope")) == []


class TestResolveUniqueSlug:
    def test_no_collision(self, tmp_path):
        ai = tmp_path / "ai-trends"
        result = resolve_unique_slug(ai, {"name": "Anthropic News"})
        assert result.slug == "anthropic-news"
        assert result.collision is False

    def test_explicit_slug_field(self, tmp_path):
        ai = tmp_path / "ai-trends"
        result = resolve_unique_slug(ai, {"name": "Foo", "slug": "custom-slug"})
        assert result.slug == "custom-slug"

    def test_collision_appends_suffix(self, tmp_path):
        ai = tmp_path / "ai-trends"
        sites_root = ai / "sites"
        sites_root.mkdir(parents=True)
        (sites_root / "anthropic-news").mkdir()
        result = resolve_unique_slug(
            ai,
            {"name": "Anthropic News"},
            taken={"anthropic-news"},
        )
        assert result.slug == "anthropic-news-2"
        assert result.collision is True
        assert result.warning is not None

    def test_collision_with_multiple_existing(self, tmp_path):
        ai = tmp_path / "ai-trends"
        taken = {"src", "src-2", "src-3"}
        result = resolve_unique_slug(ai, {"name": "Src"}, taken=taken)
        assert result.slug == "src-4"
        assert result.collision is True
