"""Tests for discover_and_fetch.py — local HTML fixtures, no network."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from discover_and_fetch import (  # noqa: E402
    CONTENT_MIN,
    FetchError,
    date_allows,
    dedupe_pending_events,
    extract_date_from_html,
    extract_links,
    extract_text,
    extract_title,
    format_summary,
    is_bad_title,
    lookup_body_cache,
    normalize_event_key,
    passes_article_gate,
    run,
    url_hash,
)
from check_cloudflare import is_cloudflare  # noqa: E402
from site_store import (  # noqa: E402
    articles_dir,
    load_site_index,
    load_url_index,
    site_index_path,
    url_index_path,
)

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

DETAIL_HTML = f"""<!DOCTYPE html>
<html><head>
  <title>Detail Page Title</title>
  <meta property="og:title" content="OG Detail Title" />
</head>
<body>
  <nav>Skip nav chrome</nav>
  <script>var x = 1;</script>
  <style>.x{{color:red}}</style>
  <article>
    <h1>Article Body</h1>
    <p>{_DETAIL_BODY}</p>
  </article>
  <footer>Skip footer chrome</footer>
</body></html>
"""

SHORT_DETAIL_HTML = """<!DOCTYPE html>
<html><head><title>https://example.com/posts/short</title></head>
<body>
  <article><p>Too short.</p></article>
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
    def _make(sources=None, end_date=END_DATE):
        weekly_root = tmp_path / "weekly"
        ai_trends = weekly_root / end_date / "ai-trends"
        ai_trends.mkdir(parents=True)
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


class TestDateAllows:
    def test_unknown_denied_by_default(self):
        assert date_allows(None, START_DATE, END_DATE) is False

    def test_unknown_allowed_when_opt_in(self):
        assert date_allows(None, START_DATE, END_DATE, allow_undated=True) is True

    def test_out_of_range_excluded(self):
        assert date_allows("2026-06-01", START_DATE, END_DATE) is False

    def test_in_range_included(self):
        assert date_allows("2026-07-20", START_DATE, END_DATE) is True


class TestCloudflare:
    def test_fixture_detected(self):
        assert is_cloudflare(CF_HTML) is True
        assert is_cloudflare(LIST_HTML) is False


class TestArticleGateAndTitle:
    def test_passes_with_long_body_and_title(self):
        assert passes_article_gate(
            title="In Range Article", content=_DETAIL_BODY,
            url="https://example.com/posts/in-range",
        )

    def test_rejects_short_content(self):
        assert not passes_article_gate(title="Short", content="Too short.", url="x")

    def test_rejects_url_title(self):
        url = "https://example.com/posts/x"
        assert is_bad_title(url, url)
        assert not passes_article_gate(title=url, content=_DETAIL_BODY, url=url)

    def test_extract_title_prefers_og(self):
        assert extract_title(DETAIL_HTML) == "OG Detail Title"

    def test_extract_text_skips_nav_and_prefers_article(self):
        text = extract_text(DETAIL_HTML)
        assert "Hello world content" in text
        assert "Skip nav chrome" not in text
        assert "var x" not in text


class TestDiscoverAndFetchRun:
    def test_url_index_and_site_articles(self, week_env):
        weekly_root, ai_trends, sources_path = week_env()
        pages = {
            "https://example.com/blog": LIST_HTML,
            "https://example.com/posts/in-range": DETAIL_HTML,
            "https://example.com/posts/already-archived": DETAIL_HTML,
        }
        counts = run(
            START_DATE, END_DATE,
            weekly_root=weekly_root, sources_path=sources_path,
            proxy=None, fetch_fn=make_fetch(pages),
        )
        url_idx = load_url_index(url_index_path(ai_trends))
        assert "https://example.com/posts/in-range" in url_idx
        assert "https://example.com/posts/already-archived" in url_idx
        assert "https://example.com/posts/out-of-range" not in url_idx
        assert "https://example.com/posts/unknown-date" not in url_idx

        slug = url_idx["https://example.com/posts/in-range"]["site"]
        a_dir = articles_dir(ai_trends, slug)
        meta_files = list(a_dir.glob("*.meta.json"))
        assert len(meta_files) == 2
        metas = {json.loads(f.read_text())["url"]: json.loads(f.read_text()) for f in meta_files}
        assert "https://example.com/posts/in-range" in metas
        assert metas["https://example.com/posts/in-range"]["original_title"] == "In Range Article"
        assert metas["https://example.com/posts/in-range"]["publish_date"] == "2026-07-20"

        assert counts["sources"] == 1
        assert counts["fetched"] == 2
        assert counts["skipped"] >= 2
        assert counts["errors"] == 0
        assert format_summary(counts).startswith("sources=1 fetched=2")

    def test_allow_undated_respects_quota(self, week_env):
        weekly_root, ai_trends, sources_path = week_env(
            sources=[{
                "name": "Fixture Blog",
                "url": "https://example.com/blog",
                "use_proxy": False, "fallback": "skip",
                "allow_undated": True, "undated_quota": 1,
            }]
        )
        pages = {
            "https://example.com/blog": LIST_HTML,
            "https://example.com/posts/in-range": DETAIL_HTML,
            "https://example.com/posts/unknown-date": DETAIL_HTML,
        }
        counts = run(
            START_DATE, END_DATE,
            weekly_root=weekly_root, sources_path=sources_path,
            fetch_fn=make_fetch(pages),
        )
        url_idx = load_url_index(url_index_path(ai_trends))
        assert "https://example.com/posts/in-range" in url_idx
        assert "https://example.com/posts/unknown-date" in url_idx
        assert counts["fetched"] == 2

    def test_url_exclude_skips_before_fetch(self, week_env):
        weekly_root, ai_trends, sources_path = week_env(
            sources=[{
                "name": "Fixture Blog",
                "url": "https://example.com/blog",
                "use_proxy": False, "fallback": "skip",
                "url_exclude": [r"/in-range"],
            }]
        )
        pages = {"https://example.com/blog": LIST_HTML}
        counts = run(
            START_DATE, END_DATE,
            weekly_root=weekly_root, sources_path=sources_path,
            fetch_fn=make_fetch(pages),
        )
        url_idx = load_url_index(url_index_path(ai_trends))
        assert "https://example.com/posts/in-range" not in url_idx
        assert counts["fetched"] == 0

    def test_resume_skips_terminal_status(self, week_env):
        weekly_root, ai_trends, sources_path = week_env()
        pages = {
            "https://example.com/blog": LIST_HTML,
            "https://example.com/posts/in-range": DETAIL_HTML,
        }
        counts1 = run(
            START_DATE, END_DATE,
            weekly_root=weekly_root, sources_path=sources_path,
            fetch_fn=make_fetch(pages), resume=False,
        )
        assert counts1["fetched"] == 1

        fetch_log: list[str] = []
        def tracking_fetch(url, **kw):
            fetch_log.append(url)
            if url not in pages:
                raise FetchError(url, "curl(direct)", f"unexpected: {url}")
            return pages[url]
        counts2 = run(
            START_DATE, END_DATE,
            weekly_root=weekly_root, sources_path=sources_path,
            fetch_fn=tracking_fetch, resume=True,
        )
        assert "https://example.com/posts/in-range" not in fetch_log
        assert counts2["fetched"] == 0

    def test_fresh_clears_sites_and_url_index(self, week_env):
        weekly_root, ai_trends, sources_path = week_env()
        old_site = ai_trends / "sites" / "old-slug"
        old_site.mkdir(parents=True)
        (old_site / "articles").mkdir()
        (url_index_path(ai_trends)).write_text('{"url":"x","site":"old","hash":"h"}\n')
        pages = {
            "https://example.com/blog": LIST_HTML,
            "https://example.com/posts/in-range": DETAIL_HTML,
        }
        run(
            START_DATE, END_DATE,
            weekly_root=weekly_root, sources_path=sources_path,
            fetch_fn=make_fetch(pages), fresh=True,
        )
        assert not (ai_trends / "sites" / "old-slug").exists()
        url_idx = load_url_index(url_index_path(ai_trends))
        assert "x" not in url_idx
        assert "https://example.com/posts/in-range" in url_idx

    def test_retry_errors_refetches(self, week_env):
        list_html = """<!DOCTYPE html><html><body>
          <a href="/posts/in-range" data-date="2026-07-20">In Range Article</a>
        </body></html>"""
        weekly_root, ai_trends, sources_path = week_env()

        def fail_fetch(url, **kw):
            if url.endswith("/posts/in-range"):
                raise FetchError(url, "curl(direct)", "HTTP 500")
            if url == "https://example.com/blog":
                return list_html
            raise FetchError(url, "curl(direct)", f"unexpected: {url}")

        run(
            START_DATE, END_DATE,
            weekly_root=weekly_root, sources_path=sources_path,
            fetch_fn=fail_fetch, resume=False,
        )
        sites_root = ai_trends / "sites"
        slug = next(d.name for d in sites_root.iterdir() if d.is_dir())
        s_idx = load_site_index(site_index_path(ai_trends, slug))
        assert s_idx.get("https://example.com/posts/in-range", {}).get("status") == "error"

        pages = {
            "https://example.com/blog": list_html,
            "https://example.com/posts/in-range": DETAIL_HTML,
        }
        counts_skip = run(
            START_DATE, END_DATE,
            weekly_root=weekly_root, sources_path=sources_path,
            fetch_fn=make_fetch(pages),
            resume=True, retry_errors=False,
        )
        assert counts_skip["fetched"] == 0

        counts = run(
            START_DATE, END_DATE,
            weekly_root=weekly_root, sources_path=sources_path,
            fetch_fn=make_fetch(pages),
            resume=True, retry_errors=True,
        )
        url_idx = load_url_index(url_index_path(ai_trends))
        assert "https://example.com/posts/in-range" in url_idx
        assert counts["fetched"] == 1

    def test_short_content_skipped_filter(self, week_env):
        list_html = """<!DOCTYPE html><html><body>
          <a href="/posts/short" data-date="2026-07-20">Short Piece</a>
        </body></html>"""
        weekly_root, ai_trends, sources_path = week_env()
        pages = {
            "https://example.com/blog": list_html,
            "https://example.com/posts/short": SHORT_DETAIL_HTML,
        }
        counts = run(
            START_DATE, END_DATE,
            weekly_root=weekly_root, sources_path=sources_path,
            fetch_fn=make_fetch(pages),
        )
        url_idx = load_url_index(url_index_path(ai_trends))
        assert len(url_idx) == 0
        assert counts["fetched"] == 0
        assert counts["skipped"] >= 1
        sites_root = ai_trends / "sites"
        slug = next(d.name for d in sites_root.iterdir() if d.is_dir())
        s_idx = load_site_index(site_index_path(ai_trends, slug))
        assert s_idx["https://example.com/posts/short"]["status"] == "skipped_filter"

    def test_cross_source_same_url_only_one_wins(self, tmp_path):
        weekly_root = tmp_path / "weekly"
        ai_trends = weekly_root / END_DATE / "ai-trends"
        ai_trends.mkdir(parents=True)
        sources_path = tmp_path / "sources.json"
        sources = [
            {"name": "Source A", "url": "https://a.com/blog", "use_proxy": False, "fallback": "skip", "url_include": [r"shared\.example\.com"]},
            {"name": "Source B", "url": "https://b.com/blog", "use_proxy": False, "fallback": "skip", "url_include": [r"shared\.example\.com"]},
        ]
        sources_path.write_text(json.dumps(sources, indent=2) + "\n")
        shared_url = "https://shared.example.com/article"
        list_a = f'<a href="{shared_url}" data-date="2026-07-20">Shared</a>'
        list_b = f'<a href="{shared_url}" data-date="2026-07-20">Shared</a>'
        pages = {
            "https://a.com/blog": list_a,
            "https://b.com/blog": list_b,
            shared_url: DETAIL_HTML,
        }
        counts = run(
            START_DATE, END_DATE,
            weekly_root=weekly_root, sources_path=sources_path,
            fetch_fn=make_fetch(pages),
        )
        url_idx = load_url_index(url_index_path(ai_trends))
        assert shared_url in url_idx
        winner_site = url_idx[shared_url]["site"]
        sites_root = ai_trends / "sites"
        found_in = []
        for sd in sites_root.iterdir():
            if sd.is_dir():
                a_dir = articles_dir(ai_trends, sd.name)
                if a_dir.is_dir() and any(a_dir.glob("*.meta.json")):
                    found_in.append(sd.name)
        assert winner_site in found_in
        assert counts["fetched"] == 1
        assert counts["skipped"] >= 1

    def test_cross_source_parallel_smoke(self, tmp_path):
        weekly_root = tmp_path / "weekly"
        ai_trends = weekly_root / END_DATE / "ai-trends"
        ai_trends.mkdir(parents=True)
        sources_path = tmp_path / "sources.json"
        sources = [
            {"name": "Source A", "url": "https://a.com/blog", "use_proxy": False, "fallback": "skip", "url_include": [r"/posts/"]},
            {"name": "Source B", "url": "https://b.com/blog", "use_proxy": False, "fallback": "skip", "url_include": [r"/posts/"]},
            {"name": "Source C", "url": "https://c.com/blog", "use_proxy": False, "fallback": "skip", "url_include": [r"/posts/"]},
        ]
        sources_path.write_text(json.dumps(sources, indent=2) + "\n")
        import threading
        fetch_lock = threading.Lock()
        fetch_starts: list[float] = []

        def slow_fetch(url, **kw):
            import time
            with fetch_lock:
                fetch_starts.append(time.monotonic())
            if url.endswith("/blog"):
                return f'<a href="/posts/art-{url.split("//")[1].split(".")[0]}" data-date="2026-07-20">Art</a>'
            if "/posts/" in url:
                return DETAIL_HTML
            raise FetchError(url, "curl(direct)", f"unexpected: {url}")

        import time
        time.monotonic()
        counts = run(
            START_DATE, END_DATE,
            weekly_root=weekly_root, sources_path=sources_path,
            fetch_fn=slow_fetch,
            source_concurrency=3,
            fetch_concurrency=3,
            fetch_concurrency_per_source=1,
        )
        url_idx = load_url_index(url_index_path(ai_trends))
        assert counts["fetched"] == 3
        assert len(url_idx) == 3
        assert counts["errors"] == 0


class TestExtractText:
    def test_strips_script_style_and_truncates(self):
        full = extract_text(DETAIL_HTML)
        assert "Hello world content" in full
        assert "var x" not in full
        truncated = extract_text(DETAIL_HTML, max_chars=20)
        assert len(truncated) <= 20
        assert truncated == full[:20]

    def test_body_cache_hit_and_miss(self, tmp_path):
        ai_trends = tmp_path / "ai-trends"
        slug = "s"
        url = "https://example.com/a"
        digest = url_hash(url)
        a_dir = articles_dir(ai_trends, slug)
        a_dir.mkdir(parents=True)
        (a_dir / f"{digest}.body.txt").write_text("body text", encoding="utf-8")
        now = datetime.now(timezone.utc)
        fresh = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        (a_dir / f"{digest}.meta.json").write_text(json.dumps({
            "url": url, "original_title": "T", "source": "S",
            "fetched_at": fresh, "publish_date": "2026-07-20",
            "status": "fetched",
        }))
        site_index = {url: {"url": url, "status": "fetched", "hash": digest}}
        hit = lookup_body_cache(ai_trends, slug, url, site_index, ttl_days=7, now=now)
        assert hit is not None
        assert hit["content"] == "body text"
        expired_idx = {url: {**site_index[url], "hash": digest}}
        old = (now - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        (a_dir / f"{digest}.meta.json").write_text(json.dumps({
            **json.loads((a_dir / f"{digest}.meta.json").read_text()),
            "fetched_at": old,
        }))
        assert lookup_body_cache(ai_trends, slug, url, expired_idx, ttl_days=7, now=now) is None


class TestEventDedupe:
    def test_normalize_title_strips_punct_case(self):
        assert normalize_event_key("Hello, World!") == normalize_event_key("hello world")
        assert normalize_event_key("A") != normalize_event_key("B")

    def test_dedupe_keeps_best_rank_and_related_urls(self):
        long = "x" * 500
        short = "y" * 100
        entries = [
            {"url": "https://a.example/1", "original_title": "OpenAI Ships GPT!", "content": short, "rank_hint": 5},
            {"url": "https://b.example/2", "original_title": "openai ships gpt", "content": long, "rank_hint": 1},
            {"url": "https://c.example/other", "original_title": "Unrelated Story", "content": long},
        ]
        out = dedupe_pending_events(entries)
        assert len(out) == 2
        primary = next(e for e in out if "openai" in e["original_title"].lower())
        assert primary["url"] == "https://b.example/2"
        assert primary["related_urls"] == ["https://a.example/1"]


class TestExtractDateFromHtml:
    def test_jsonld_datepublished(self):
        html = '<script type="application/ld+json">{"@context":"https://schema.org","datePublished":"2026-07-14T10:00:00Z"}</script>'
        assert extract_date_from_html(html) == "2026-07-14"

    def test_meta_article_published_time(self):
        html = '<meta property="article:published_time" content="2026-06-09T15:30:00Z">'
        assert extract_date_from_html(html) == "2026-06-09"

    def test_time_datetime(self):
        html = '<time datetime="2026-05-20T00:00:00">May 20</time>'
        assert extract_date_from_html(html) == "2026-05-20"

    def test_meta_name_publish_date(self):
        html = '<meta name="publish_date" content="2026-03-15">'
        assert extract_date_from_html(html) == "2026-03-15"

    def test_anthropic_agate(self):
        html = '<div class="body-3 agate">Jul 14, 2026</div>'
        assert extract_date_from_html(html) == "2026-07-14"

    def test_meta_amum(self):
        html = '<span class="_amum">March 27, 2026</span>'
        assert extract_date_from_html(html) == "2026-03-27"

    def test_full_month_text(self):
        html = '<div>January 5, 2026</div>'
        assert extract_date_from_html(html) == "2026-01-05"

    def test_abbreviated_month(self):
        html = '<div>Feb 3, 2026</div>'
        assert extract_date_from_html(html) == "2026-02-03"

    def test_no_date_returns_none(self):
        html = '<div>Hello world</div>'
        assert extract_date_from_html(html) is None

    def test_empty_html_returns_none(self):
        assert extract_date_from_html("") is None
