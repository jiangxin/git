"""Tests for discover_and_fetch.py — local HTML fixtures, no network."""

from __future__ import annotations

import hashlib
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
    extract_links,
    extract_text,
    extract_title,
    format_summary,
    is_bad_title,
    is_undated,
    lookup_raw_cache,
    parse_undated_quota,
    passes_article_gate,
    raw_cache_fresh,
    raw_index_path,
    run,
    url_sha1,
    write_raw,
)
from check_cloudflare import is_cloudflare  # noqa: E402

END_DATE = "2026-07-24"
START_DATE = "2026-07-18"

# Body long enough to pass CONTENT_MIN gate (≥400 chars).
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
    def test_unknown_denied_by_default(self):
        assert date_allows(None, START_DATE, END_DATE) is False
        assert date_allows(None, START_DATE, END_DATE, allow_undated=False) is False

    def test_unknown_allowed_when_opt_in(self):
        assert date_allows(None, START_DATE, END_DATE, allow_undated=True) is True
        assert date_allows("not-a-date", START_DATE, END_DATE, allow_undated=True) is True

    def test_out_of_range_excluded(self):
        assert date_allows("2026-06-01", START_DATE, END_DATE) is False

    def test_in_range_included(self):
        assert date_allows("2026-07-20", START_DATE, END_DATE) is True

    def test_is_undated_matrix(self):
        assert is_undated(None) is True
        assert is_undated("") is True
        assert is_undated("not-a-date") is True
        assert is_undated("2026-07-20") is False
        assert is_undated("2026-07-20T12:00:00") is False

    def test_undated_quota_parsing(self):
        assert parse_undated_quota({}, allow_undated=False) == 0
        assert parse_undated_quota({"undated_quota": 5}, allow_undated=False) == 0
        assert parse_undated_quota({"undated_quota": 3}, allow_undated=True) == 3
        assert parse_undated_quota({"undated_quota": "2"}, allow_undated=True) == 2
        assert parse_undated_quota({"undated_quota": "x"}, allow_undated=True) == 0
        assert parse_undated_quota({}, allow_undated=True) == 0


class TestCloudflare:
    def test_fixture_detected(self):
        assert is_cloudflare(CF_HTML) is True
        assert is_cloudflare(LIST_HTML) is False


class TestArticleGateAndTitle:
    def test_passes_with_long_body_and_title(self):
        url = "https://example.com/posts/in-range"
        assert passes_article_gate(
            title="In Range Article",
            content=_DETAIL_BODY,
            url=url,
        )

    def test_rejects_short_content(self):
        url = "https://example.com/posts/short"
        assert not passes_article_gate(
            title="Short",
            content="Too short.",
            url=url,
        )

    def test_rejects_url_title(self):
        url = "https://example.com/posts/x"
        assert is_bad_title(url, url)
        assert is_bad_title(None, url)
        assert is_bad_title("  ", url)
        assert not passes_article_gate(
            title=url,
            content=_DETAIL_BODY,
            url=url,
        )

    def test_extract_title_prefers_og(self):
        assert extract_title(DETAIL_HTML) == "OG Detail Title"

    def test_extract_text_skips_nav_and_prefers_article(self):
        text = extract_text(DETAIL_HTML)
        assert "Hello world content" in text
        assert "Skip nav chrome" not in text
        assert "Skip footer chrome" not in text
        assert "var x" not in text


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
            # undated must not be fetched by default — omit from map so a fetch would fail
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
        assert "https://example.com/posts/unknown-date" not in pending_urls
        assert "https://example.com/posts/in-range" in pending_urls

        in_range = next(e for e in pending if e["url"].endswith("/in-range"))
        assert in_range["original_title"] == "In Range Article"
        assert in_range["publish_date"] == "2026-07-20"
        assert in_range["source"] == "Fixture Blog"
        assert "Hello world content" in in_range["content"]
        assert "var x" not in in_range["content"]
        assert in_range["fetched_at"]

        raw_files = list((ai_trends / "raw").glob("*.txt"))
        assert len(raw_files) >= 1
        index_path = raw_index_path(ai_trends)
        assert index_path.is_file()
        index_line = json.loads(index_path.read_text(encoding="utf-8").strip().splitlines()[-1])
        assert index_line["url"] == "https://example.com/posts/in-range"
        assert index_line["sha1"] == url_sha1("https://example.com/posts/in-range")

        assert counts["sources"] == 1
        assert counts["pending"] == 1
        assert counts["skipped"] >= 3
        assert counts["errors"] == 0
        assert format_summary(counts).startswith("sources=1 pending=1")

    def test_allow_undated_respects_quota(self, week_env):
        weekly_root, ai_trends, sources_path = week_env(
            archives=[
                {
                    "url": "https://example.com/posts/already-archived",
                    "original_title": "Old",
                    "publish_date": "2026-07-19",
                    "source": "Fixture Blog",
                }
            ],
            sources=[
                {
                    "name": "Fixture Blog",
                    "url": "https://example.com/blog",
                    "use_proxy": False,
                    "fallback": "skip",
                    "allow_undated": True,
                    "undated_quota": 1,
                }
            ],
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
            fetch_fn=make_fetch(pages),
            save_raw=False,
        )
        pending = json.loads((ai_trends / "pending.json").read_text(encoding="utf-8"))
        pending_urls = {e["url"] for e in pending}
        assert "https://example.com/posts/in-range" in pending_urls
        assert "https://example.com/posts/unknown-date" in pending_urls
        assert counts["pending"] == 2
        assert counts["errors"] == 0

    def test_undated_quota_exhausted_skips_extra(self, week_env):
        list_html = """<!DOCTYPE html><html><body>
          <a href="/posts/u1">U1</a>
          <a href="/posts/u2">U2</a>
        </body></html>"""
        weekly_root, ai_trends, sources_path = week_env(
            archives=[],
            sources=[
                {
                    "name": "Fixture Blog",
                    "url": "https://example.com/blog",
                    "use_proxy": False,
                    "fallback": "skip",
                    "allow_undated": True,
                    "undated_quota": 1,
                }
            ],
        )
        pages = {
            "https://example.com/blog": list_html,
            "https://example.com/posts/u1": DETAIL_HTML,
            "https://example.com/posts/u2": DETAIL_HTML,
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
        assert len(pending) == 1
        assert pending[0]["url"] == "https://example.com/posts/u1"
        assert counts["skipped"] >= 1
        assert counts["errors"] == 0

    def test_url_exclude_skips_before_fetch(self, week_env):
        weekly_root, ai_trends, sources_path = week_env(
            archives=[
                {
                    "url": "https://example.com/posts/already-archived",
                    "original_title": "Old",
                    "publish_date": "2026-07-19",
                    "source": "Fixture Blog",
                }
            ],
            sources=[
                {
                    "name": "Fixture Blog",
                    "url": "https://example.com/blog",
                    "use_proxy": False,
                    "fallback": "skip",
                    "url_exclude": [r"/in-range"],
                }
            ],
        )
        pages = {
            "https://example.com/blog": LIST_HTML,
            # in-range excluded — must not be fetched
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
        assert pending == []
        assert counts["pending"] == 0
        assert counts["errors"] == 0

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

    def test_resume_merges_pending_and_skips_refetch(self, week_env):
        weekly_root, ai_trends, sources_path = week_env(archives=[])
        (ai_trends / "pending.json").write_text(
            json.dumps(
                [
                    {
                        "url": "https://stale.example/old",
                        "original_title": "Stale",
                        "publish_date": "2026-07-19",
                        "source": "Other",
                        "content": "kept",
                        "fetched_at": "2026-07-19T00:00:00",
                    }
                ],
                indent=2,
            )
            + "\n"
        )
        pages = {
            "https://example.com/blog": LIST_HTML,
            "https://example.com/posts/in-range": DETAIL_HTML,
        }
        run(
            START_DATE,
            END_DATE,
            weekly_root=weekly_root,
            sources_path=sources_path,
            fetch_fn=make_fetch(pages),
            save_raw=False,
            resume=True,
        )
        pending = json.loads((ai_trends / "pending.json").read_text(encoding="utf-8"))
        urls = {e["url"] for e in pending}
        assert "https://stale.example/old" in urls
        assert "https://example.com/posts/in-range" in urls
        assert len(pending) == 2

        state_path = ai_trends / "fetch_state.jsonl"
        assert state_path.is_file()
        state_text = state_path.read_text(encoding="utf-8")
        assert '"status": "fetched"' in state_text
        assert "https://example.com/posts/in-range" in state_text

        # Second run: detail URL must not be fetched again (omit from map)
        pages2 = {"https://example.com/blog": LIST_HTML}
        fetch_log: list[str] = []

        def tracking_fetch(url: str, *, proxy=None, use_proxy_flag: bool = False, timeout: int = 30):
            fetch_log.append(url)
            if url not in pages2:
                raise FetchError(url, "curl(direct)", f"unexpected refetch: {url}")
            return pages2[url]

        counts = run(
            START_DATE,
            END_DATE,
            weekly_root=weekly_root,
            sources_path=sources_path,
            fetch_fn=tracking_fetch,
            save_raw=False,
            resume=True,
        )
        assert "https://example.com/posts/in-range" not in fetch_log
        assert counts["errors"] == 0
        pending2 = json.loads((ai_trends / "pending.json").read_text(encoding="utf-8"))
        assert {e["url"] for e in pending2} == urls

    def test_fresh_clears_state_and_pending(self, week_env):
        weekly_root, ai_trends, sources_path = week_env(archives=[])
        (ai_trends / "pending.json").write_text(
            json.dumps([{"url": "https://stale.example/old", "content": "x"}], indent=2) + "\n"
        )
        (ai_trends / "fetch_state.jsonl").write_text(
            json.dumps(
                {
                    "url": "https://example.com/posts/in-range",
                    "status": "fetched",
                    "source": "Fixture Blog",
                    "at": "2026-07-20T00:00:00Z",
                }
            )
            + "\n"
        )
        pages = {
            "https://example.com/blog": LIST_HTML,
            "https://example.com/posts/in-range": DETAIL_HTML,
        }
        run(
            START_DATE,
            END_DATE,
            weekly_root=weekly_root,
            sources_path=sources_path,
            fetch_fn=make_fetch(pages),
            save_raw=False,
            fresh=True,
        )
        pending = json.loads((ai_trends / "pending.json").read_text(encoding="utf-8"))
        assert all(e["url"] != "https://stale.example/old" for e in pending)
        assert len(pending) == 1
        assert pending[0]["url"] == "https://example.com/posts/in-range"
        # State rewritten for this run (fetched again despite prior state)
        statuses = {
            json.loads(ln)["url"]: json.loads(ln)["status"]
            for ln in (ai_trends / "fetch_state.jsonl").read_text(encoding="utf-8").splitlines()
            if ln.strip()
        }
        assert statuses.get("https://example.com/posts/in-range") == "fetched"

    def test_resume_skips_preset_fetched_without_network(self, week_env):
        """Pre-seeded fetch_state prevents detail fetch on first run."""
        list_html = """<!DOCTYPE html><html><body>
          <a href="/posts/in-range" data-date="2026-07-20">In Range Article</a>
        </body></html>"""
        weekly_root, ai_trends, sources_path = week_env(archives=[])
        (ai_trends / "fetch_state.jsonl").write_text(
            json.dumps(
                {
                    "url": "https://example.com/posts/in-range",
                    "status": "fetched",
                    "source": "Fixture Blog",
                    "at": "2026-07-20T00:00:00Z",
                }
            )
            + "\n"
        )
        (ai_trends / "pending.json").write_text(
            json.dumps(
                [
                    {
                        "url": "https://example.com/posts/in-range",
                        "original_title": "In Range Article",
                        "publish_date": "2026-07-20",
                        "source": "Fixture Blog",
                        "content": "cached body",
                        "fetched_at": "2026-07-20T00:00:00",
                    }
                ],
                indent=2,
            )
            + "\n"
        )
        pages = {"https://example.com/blog": list_html}
        fetch_log: list[str] = []

        def tracking_fetch(url: str, *, proxy=None, use_proxy_flag: bool = False, timeout: int = 30):
            fetch_log.append(url)
            if url not in pages:
                raise FetchError(url, "curl(direct)", f"unexpected refetch: {url}")
            return pages[url]

        counts = run(
            START_DATE,
            END_DATE,
            weekly_root=weekly_root,
            sources_path=sources_path,
            fetch_fn=tracking_fetch,
            save_raw=False,
            resume=True,
        )
        assert fetch_log == ["https://example.com/blog"]
        assert counts["pending"] == 1
        assert counts["errors"] == 0
        pending = json.loads((ai_trends / "pending.json").read_text(encoding="utf-8"))
        assert pending[0]["content"] == "cached body"

    def test_retry_errors_refetches_error_urls(self, week_env):
        list_html = """<!DOCTYPE html><html><body>
          <a href="/posts/in-range" data-date="2026-07-20">In Range Article</a>
        </body></html>"""
        weekly_root, ai_trends, sources_path = week_env(archives=[])
        (ai_trends / "fetch_state.jsonl").write_text(
            json.dumps(
                {
                    "url": "https://example.com/posts/in-range",
                    "status": "error",
                    "source": "Fixture Blog",
                    "at": "2026-07-20T00:00:00Z",
                }
            )
            + "\n"
        )
        pages = {
            "https://example.com/blog": list_html,
            "https://example.com/posts/in-range": DETAIL_HTML,
        }
        # Default resume skips error URLs
        counts_skip = run(
            START_DATE,
            END_DATE,
            weekly_root=weekly_root,
            sources_path=sources_path,
            fetch_fn=make_fetch({"https://example.com/blog": list_html}),
            save_raw=False,
            resume=True,
            retry_errors=False,
        )
        assert counts_skip["pending"] == 0

        counts = run(
            START_DATE,
            END_DATE,
            weekly_root=weekly_root,
            sources_path=sources_path,
            fetch_fn=make_fetch(pages),
            save_raw=False,
            resume=True,
            retry_errors=True,
        )
        pending = json.loads((ai_trends / "pending.json").read_text(encoding="utf-8"))
        assert counts["pending"] == 1
        assert pending[0]["url"] == "https://example.com/posts/in-range"

    def test_raw_cache_hit_skips_http(self, week_env):
        list_html = """<!DOCTYPE html><html><body>
          <a href="/posts/in-range" data-date="2026-07-20">In Range Article</a>
        </body></html>"""
        weekly_root, ai_trends, sources_path = week_env(archives=[])
        url = "https://example.com/posts/in-range"
        digest = url_sha1(url)
        write_raw(ai_trends, url, _DETAIL_BODY)
        fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        index_path = raw_index_path(ai_trends)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps(
                {
                    "url": url,
                    "sha1": digest,
                    "source": "Fixture Blog",
                    "fetched_at": fetched_at,
                    "publish_date": "2026-07-20",
                    "title": "In Range Article",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        pages = {"https://example.com/blog": list_html}
        fetch_log: list[str] = []

        def tracking_fetch(
            url_arg: str, *, proxy=None, use_proxy_flag: bool = False, timeout: int = 30
        ):
            fetch_log.append(url_arg)
            if url_arg not in pages:
                raise FetchError(url_arg, "curl(direct)", f"unexpected refetch: {url_arg}")
            return pages[url_arg]

        counts = run(
            START_DATE,
            END_DATE,
            weekly_root=weekly_root,
            sources_path=sources_path,
            fetch_fn=tracking_fetch,
            save_raw=True,
            resume=True,
            raw_ttl_days=7,
        )
        assert url not in fetch_log
        assert fetch_log == ["https://example.com/blog"]
        pending = json.loads((ai_trends / "pending.json").read_text(encoding="utf-8"))
        assert len(pending) == 1
        assert pending[0]["url"] == url
        assert pending[0]["content"] == _DETAIL_BODY
        assert counts["pending"] == 1
        assert counts["errors"] == 0
        state_lines = [
            json.loads(ln)
            for ln in (ai_trends / "fetch_state.jsonl").read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        assert any(r["url"] == url and r["status"] == "cached" for r in state_lines)

    def test_short_content_skipped_filter_not_pending(self, week_env):
        list_html = """<!DOCTYPE html><html><body>
          <a href="/posts/short" data-date="2026-07-20">Short Piece</a>
        </body></html>"""
        weekly_root, ai_trends, sources_path = week_env(archives=[])
        pages = {
            "https://example.com/blog": list_html,
            "https://example.com/posts/short": SHORT_DETAIL_HTML,
        }
        counts = run(
            START_DATE,
            END_DATE,
            weekly_root=weekly_root,
            sources_path=sources_path,
            fetch_fn=make_fetch(pages),
            save_raw=True,
        )
        pending = json.loads((ai_trends / "pending.json").read_text(encoding="utf-8"))
        assert pending == []
        assert counts["pending"] == 0
        assert counts["skipped"] >= 1
        assert counts["errors"] == 0
        state_lines = [
            json.loads(ln)
            for ln in (ai_trends / "fetch_state.jsonl").read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        assert any(
            r["url"] == "https://example.com/posts/short" and r["status"] == "skipped_filter"
            for r in state_lines
        )
        # Junk must not be indexed for cache reuse
        index_path = raw_index_path(ai_trends)
        assert not index_path.is_file() or "posts/short" not in index_path.read_text(
            encoding="utf-8"
        )

    def test_expired_raw_cache_refetches(self, week_env):
        list_html = """<!DOCTYPE html><html><body>
          <a href="/posts/in-range" data-date="2026-07-20">In Range Article</a>
        </body></html>"""
        weekly_root, ai_trends, sources_path = week_env(archives=[])
        url = "https://example.com/posts/in-range"
        digest = url_sha1(url)
        write_raw(ai_trends, url, "stale cached body " + ("x" * 400))
        old = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        index_path = raw_index_path(ai_trends)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps(
                {
                    "url": url,
                    "sha1": digest,
                    "source": "Fixture Blog",
                    "fetched_at": old,
                    "publish_date": "2026-07-20",
                    "title": "In Range Article",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        assert not raw_cache_fresh(old, ttl_days=7)
        pages = {
            "https://example.com/blog": list_html,
            url: DETAIL_HTML,
        }
        counts = run(
            START_DATE,
            END_DATE,
            weekly_root=weekly_root,
            sources_path=sources_path,
            fetch_fn=make_fetch(pages),
            save_raw=True,
            raw_ttl_days=7,
        )
        pending = json.loads((ai_trends / "pending.json").read_text(encoding="utf-8"))
        assert counts["pending"] == 1
        assert "Hello world content" in pending[0]["content"]
        assert "stale cached body" not in pending[0]["content"]


class TestExtractText:
    def test_strips_script_style_and_truncates(self):
        full = extract_text(DETAIL_HTML)
        assert "Hello world content" in full
        assert "var x" not in full
        assert ".x{color" not in full
        truncated = extract_text(DETAIL_HTML, max_chars=20)
        assert len(truncated) <= 20
        assert truncated == full[:20]

    def test_lookup_raw_cache_hit_and_miss(self, tmp_path):
        ai_trends = tmp_path / "ai-trends"
        url = "https://example.com/a"
        digest = hashlib.sha1(url.encode()).hexdigest()
        write_raw(ai_trends, url, "body text")
        now = datetime.now(timezone.utc)
        fresh = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        index = {
            url: {
                "url": url,
                "sha1": digest,
                "source": "S",
                "fetched_at": fresh,
                "publish_date": "2026-07-20",
                "title": "T",
            }
        }
        hit = lookup_raw_cache(ai_trends, url, index, ttl_days=7, now=now)
        assert hit is not None
        assert hit["content"] == "body text"
        assert hit["original_title"] == "T"
        expired = {
            url: {
                **index[url],
                "fetched_at": (now - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        }
        assert lookup_raw_cache(ai_trends, url, expired, ttl_days=7, now=now) is None
        assert lookup_raw_cache(ai_trends, "https://missing", index, ttl_days=7, now=now) is None
