#!/usr/bin/env python3
"""Discover article URLs from sources.json and fetch bodies into pending.json.

Usage:
  python3 discover_and_fetch.py --start-date YYYY-MM-DD --end-date YYYY-MM-DD
  python3 discover_and_fetch.py ... --fresh          # clear state + pending
  python3 discover_and_fetch.py ... --retry-errors    # retry prior error URLs

Stdout summary: sources=N pending=M skipped=K errors=E
Default ``--resume`` loads ``fetch_state.jsonl`` and merges existing pending.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
# __file__ parents[2] == skills/  →  skills/_shared/scripts
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared" / "scripts"))

from fetch_backends import (  # noqa: E402
    FetchError,
    FetchFn,
    FetchMode,
    fetch_html,
    fetch_http,
    parse_browser_on_cloudflare,
    parse_fetch_mode,
)
from filter_by_date import extract_date  # noqa: E402
from json_archives import load_json_array, save_json_atomic  # noqa: E402
from repo_config import load_repo_config  # noqa: E402
from restricted_search import (  # noqa: E402
    SearchFn,
    SearchSkipped,
    resolve_search_config,
    restricted_search,
)
from rss_parse import parse_feed  # noqa: E402
from url_filter import url_allowed  # noqa: E402

CONTENT_MAX = 12000
CONTENT_MIN = 400
DEFAULT_RAW_TTL_DAYS = 7
PENDING_SAVE_EVERY = 20
FETCH_STATE_FILENAME = "fetch_state.jsonl"
RAW_INDEX_FILENAME = "index.jsonl"
# Limited same-origin feed probes for fallback=aggregate (avoid blind guessing).
COMMON_FEED_PATHS = ("/feed", "/rss", "/feed.xml", "/rss.xml", "/atom.xml")
TERMINAL_SKIP_STATUSES = frozenset(
    {"fetched", "skipped_date", "skipped_filter", "cached"}
)
_ARTICLE_BLOCK = re.compile(
    r"(?is)<(article|main)\b[^>]*>(.*?)</\1>"
)
_META_TITLE_PROP = re.compile(
    r"<meta\b[^>]*\b(?:property|name)=[\"'](og:title|twitter:title)[\"'][^>]*>",
    re.I,
)
_META_CONTENT_ATTR = re.compile(
    r"\bcontent=[\"']([^\"']+)[\"']",
    re.I,
)
_TITLE_TAG = re.compile(r"(?is)<title\b[^>]*>(.*?)</title>")
SKIP_EXTENSIONS = {
    ".css",
    ".js",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".ico",
    ".webp",
    ".pdf",
    ".zip",
    ".xml",
    ".json",
}
_URL_DATE = re.compile(r"/(20\d{2})[/-](\d{1,2})[/-](\d{1,2})(?:/|$)")

# Back-compat aliases for tests / callers
default_fetch = fetch_http


def default_sources_path() -> Path:
    return SCRIPT_DIR.parent / "references" / "sources.json"


def resolve_ai_trends_dir(end_date: str, weekly_root=None) -> Path:
    """Locate ``weekly/<end_date>/ai-trends/`` (same pattern as merge_archives)."""
    if not end_date:
        print("ERROR: end_date is required (YYYY-MM-DD)", file=sys.stderr)
        sys.exit(2)
    if weekly_root is None:
        repo_root = SCRIPT_DIR.parents[3]
        weekly_root = repo_root / "weekly"
    else:
        weekly_root = Path(weekly_root)

    ai_trends = Path(weekly_root) / end_date / "ai-trends"
    if not ai_trends.is_dir():
        print(f"ERROR: ai-trends directory not found: {ai_trends}", file=sys.stderr)
        print("Run setup_week.py first.", file=sys.stderr)
        sys.exit(2)
    return ai_trends


def load_sources(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: JSON parse failed in sources.json ({path}): {e}", file=sys.stderr)
        sys.exit(3)
    if not isinstance(data, list):
        print(f"ERROR: sources.json root is not an array: {path}", file=sys.stderr)
        sys.exit(3)
    return data


def append_error_log(ai_trends_dir: Path, method: str, url: str, reason: str) -> None:
    log_path = ai_trends_dir / "error.log"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] FAILED {method} {url} - {reason}\n"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)


def url_sha1(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def fetch_state_path(ai_trends_dir: Path) -> Path:
    return ai_trends_dir / FETCH_STATE_FILENAME


def load_fetch_state(path: Path) -> dict[str, str]:
    """Load url → last status from fetch_state.jsonl (later lines win)."""
    state: dict[str, str] = {}
    if not path.is_file():
        return state
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            url = row.get("url")
            status = row.get("status")
            if isinstance(url, str) and isinstance(status, str) and url:
                state[url] = status
    return state


def append_fetch_state(
    path: Path,
    *,
    url: str,
    status: str,
    source: str,
    sha1: str | None = None,
) -> None:
    """Append one JSONL record to fetch_state."""
    record: dict[str, Any] = {
        "url": url,
        "status": status,
        "source": source,
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if sha1:
        record["sha1"] = sha1
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def should_skip_from_state(
    url: str,
    state: dict[str, str],
    *,
    retry_errors: bool,
) -> bool:
    """True when resume should not re-process this URL."""
    status = state.get(url)
    if status is None:
        return False
    if status in TERMINAL_SKIP_STATUSES:
        return True
    if status == "error":
        return not retry_errors
    return False


def load_pending_entries(path: Path) -> list[dict[str, Any]]:
    """Load pending.json array; missing/invalid → empty list."""
    if not path.is_file():
        return []
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [e for e in data if isinstance(e, dict) and e.get("url")]


def merge_pending_by_url(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge by url: existing order first, incoming updates/overwrites."""
    by_url: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for entry in existing:
        url = entry.get("url")
        if not isinstance(url, str) or not url:
            continue
        if url not in by_url:
            order.append(url)
        by_url[url] = entry
    for entry in incoming:
        url = entry.get("url")
        if not isinstance(url, str) or not url:
            continue
        if url not in by_url:
            order.append(url)
        by_url[url] = entry
    return [by_url[u] for u in order]


def clear_fetch_artifacts(ai_trends_dir: Path) -> None:
    """``--fresh``: remove fetch_state and reset pending.json."""
    state_path = fetch_state_path(ai_trends_dir)
    if state_path.exists():
        state_path.unlink()
    save_json_atomic([], ai_trends_dir / "pending.json")


def fetch_with_policy(
    url: str,
    *,
    use_proxy: Any,
    proxy: str | None,
    fetch_fn: FetchFn,
    mode: FetchMode = "http",
    browser_on_cloudflare: bool = True,
    browser_fetch_fn: FetchFn | None = None,
) -> tuple[str, str]:
    """Fetch via http/browser backends; optional Cloudflare→browser downgrade."""
    return fetch_html(
        url,
        mode=mode,
        use_proxy=use_proxy,
        proxy=proxy,
        browser_on_cloudflare=browser_on_cloudflare,
        http_fetch_fn=fetch_fn,
        browser_fetch_fn=browser_fetch_fn,
    )


def date_from_url(url: str) -> str | None:
    m = _URL_DATE.search(urlparse(url).path)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except ValueError:
        return None


def normalize_href(href: str, base_url: str) -> str | None:
    href = (href or "").strip()
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
        return None
    abs_url = urljoin(base_url, href)
    parsed = urlparse(abs_url)
    if parsed.scheme not in ("http", "https"):
        return None
    path_lower = parsed.path.lower()
    for ext in SKIP_EXTENSIONS:
        if path_lower.endswith(ext):
            return None
    # Drop fragment for dedupe stability
    return abs_url.split("#", 1)[0]


class LinkCollector(HTMLParser):
    """Collect ``a[href]`` entries with optional nearby/attr dates."""

    def __init__(self, base_url: str, date_attr: str | None = None):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.date_attr = date_attr
        self.links: list[dict[str, Any]] = []
        self._in_a = False
        self._href: str | None = None
        self._parts: list[str] = []
        self._attr_date: str | None = None
        self._last_time: str | None = None
        self._seen: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k: (v or "") for k, v in attrs}
        if tag == "time":
            day = extract_date(ad.get("datetime") or ad.get("data-date") or "")
            if day:
                self._last_time = day
        if tag != "a":
            return
        href = ad.get("href")
        if not href:
            return
        self._in_a = True
        self._href = href
        self._parts = []
        self._attr_date = None
        for key in filter(None, [self.date_attr, "datetime", "data-date", "data-publish-date"]):
            if key in ad and ad[key]:
                day = extract_date(ad[key])
                if day:
                    self._attr_date = day
                    break

    def handle_data(self, data: str) -> None:
        if self._in_a:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._in_a:
            return
        self._in_a = False
        url = normalize_href(self._href or "", self.base_url)
        self._href = None
        if not url or url in self._seen:
            return
        # Skip the list page itself (ignore query/trailing slash differences lightly)
        base_norm = self.base_url.rstrip("/")
        if url.rstrip("/") == base_norm:
            return
        title = " ".join("".join(self._parts).split()).strip() or url
        pub = self._attr_date or self._last_time or date_from_url(url)
        self._seen.add(url)
        self.links.append({"url": url, "original_title": title, "publish_date": pub})


def extract_links(
    html: str,
    base_url: str,
    *,
    date_attr: str | None = None,
) -> list[dict[str, Any]]:
    """Extract article-like links from a list-page HTML fixture/string."""
    collector = LinkCollector(base_url, date_attr=date_attr)
    try:
        collector.feed(html)
        collector.close()
    except Exception:  # noqa: BLE001 — tolerate broken HTML
        pass
    return collector.links


def parse_max_links(source: dict[str, Any]) -> int | None:
    """Optional per-source candidate cap; None means unlimited."""
    raw = source.get("max_links")
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def apply_max_links(
    items: list[dict[str, Any]], max_links: int | None
) -> list[dict[str, Any]]:
    if max_links is None:
        return items
    return items[:max_links]


def feed_probe_urls(list_url: str) -> list[str]:
    """Same-origin common feed paths derived from the list page URL."""
    parsed = urlparse(list_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return []
    origin = f"{parsed.scheme}://{parsed.netloc}"
    urls: list[str] = []
    seen: set[str] = set()
    for path in COMMON_FEED_PATHS:
        candidate = origin + path
        if candidate not in seen:
            seen.add(candidate)
            urls.append(candidate)
    return urls


def fetch_feed_items(
    feed_url: str,
    *,
    use_proxy: Any,
    proxy: str | None,
    fetch_fn: FetchFn,
    mode: FetchMode = "http",
    browser_on_cloudflare: bool = True,
    browser_fetch_fn: FetchFn | None = None,
) -> list[dict[str, Any]]:
    """Fetch and parse one RSS/Atom URL; raises FetchError on transport failure."""
    body, _method = fetch_with_policy(
        feed_url,
        use_proxy=use_proxy,
        proxy=proxy,
        fetch_fn=fetch_fn,
        mode=mode,
        browser_on_cloudflare=browser_on_cloudflare,
        browser_fetch_fn=browser_fetch_fn,
    )
    items = parse_feed(body, base_url=feed_url)
    if not items:
        raise FetchError(feed_url, "rss", "empty or unparseable feed")
    return items


def discover_via_html(
    list_url: str,
    *,
    date_attr: str | None,
    use_proxy: Any,
    proxy: str | None,
    fetch_fn: FetchFn,
    mode: FetchMode = "http",
    browser_on_cloudflare: bool = True,
    browser_fetch_fn: FetchFn | None = None,
) -> list[dict[str, Any]]:
    """Fetch list HTML and extract links; raises FetchError on failure."""
    list_html, _method = fetch_with_policy(
        list_url,
        use_proxy=use_proxy,
        proxy=proxy,
        fetch_fn=fetch_fn,
        mode=mode,
        browser_on_cloudflare=browser_on_cloudflare,
        browser_fetch_fn=browser_fetch_fn,
    )
    return extract_links(list_html, list_url, date_attr=date_attr)


def discover_via_aggregate(
    source: dict[str, Any],
    *,
    list_url: str,
    use_proxy: Any,
    proxy: str | None,
    fetch_fn: FetchFn,
    mode: FetchMode = "http",
    browser_on_cloudflare: bool = True,
    browser_fetch_fn: FetchFn | None = None,
) -> list[dict[str, Any]]:
    """Try ``fallback_rss_url`` then a few same-origin feed probes."""
    candidates: list[str] = []
    fb = source.get("fallback_rss_url")
    if isinstance(fb, str) and fb.startswith(("http://", "https://")):
        candidates.append(fb)
    for url in feed_probe_urls(list_url):
        if url not in candidates:
            candidates.append(url)

    last_err: FetchError | None = None
    for feed_url in candidates:
        try:
            return fetch_feed_items(
                feed_url,
                use_proxy=use_proxy,
                proxy=proxy,
                fetch_fn=fetch_fn,
                mode=mode,
                browser_on_cloudflare=browser_on_cloudflare,
                browser_fetch_fn=browser_fetch_fn,
            )
        except FetchError as e:
            last_err = e
            continue
    if last_err is not None:
        raise last_err
    raise FetchError(list_url, "aggregate", "no fallback feed candidates")


def discover_source_items(
    source: dict[str, Any],
    *,
    start_date: str,
    end_date: str,
    use_proxy: Any,
    proxy: str | None,
    fetch_fn: FetchFn,
    search_cfg: dict[str, Any] | None = None,
    search_fn: SearchFn | None = None,
    mode: FetchMode | None = None,
    browser_on_cloudflare: bool | None = None,
    browser_fetch_fn: FetchFn | None = None,
) -> tuple[list[dict[str, Any]], list[tuple[str, str, str]]]:
    """RSS-first discovery with HTML + fallback. Returns (items, error_triples).

    error_triples are ``(method, url, reason)`` for ``error.log`` (non-fatal notes
    and terminal failures). Empty items with a terminal failure are signalled by
    a final triple whose method starts with ``discover``.
    """
    list_url = source.get("url")
    if not isinstance(list_url, str) or not list_url.startswith(("http://", "https://")):
        return [], [("config", str(list_url), "invalid source url")]

    date_attr = source.get("date_attr") if isinstance(source.get("date_attr"), str) else None
    fallback = source.get("fallback") or "skip"
    fetch_mode = mode if mode is not None else parse_fetch_mode(source)
    boc = (
        browser_on_cloudflare
        if browser_on_cloudflare is not None
        else parse_browser_on_cloudflare(source)
    )
    errors: list[tuple[str, str, str]] = []
    items: list[dict[str, Any]] = []

    rss_url = source.get("rss_url")
    if isinstance(rss_url, str) and rss_url.startswith(("http://", "https://")):
        try:
            items = fetch_feed_items(
                rss_url,
                use_proxy=use_proxy,
                proxy=proxy,
                fetch_fn=fetch_fn,
                mode=fetch_mode,
                browser_on_cloudflare=boc,
                browser_fetch_fn=browser_fetch_fn,
            )
        except FetchError as e:
            errors.append((e.method, e.url, e.reason))

    if not items:
        try:
            items = discover_via_html(
                list_url,
                date_attr=date_attr,
                use_proxy=use_proxy,
                proxy=proxy,
                fetch_fn=fetch_fn,
                mode=fetch_mode,
                browser_on_cloudflare=boc,
                browser_fetch_fn=browser_fetch_fn,
            )
        except FetchError as e:
            errors.append((e.method, e.url, e.reason))

    if items:
        return apply_max_links(items, parse_max_links(source)), errors

    # Zero items or list/RSS failure → fallback
    if fallback == "skip":
        errors.append(("discover", list_url, "list empty; fallback=skip"))
        return [], errors

    if fallback == "aggregate":
        try:
            items = discover_via_aggregate(
                source,
                list_url=list_url,
                use_proxy=use_proxy,
                proxy=proxy,
                fetch_fn=fetch_fn,
                mode=fetch_mode,
                browser_on_cloudflare=boc,
                browser_fetch_fn=browser_fetch_fn,
            )
        except FetchError as e:
            errors.append((e.method, e.url, e.reason))
            errors.append(("discover", list_url, "aggregate fallback failed"))
            return [], errors
        return apply_max_links(items, parse_max_links(source)), errors

    if fallback == "search":
        try:
            items = restricted_search(
                source_name=str(source.get("name") or "unknown"),
                list_url=list_url,
                start_date=start_date,
                end_date=end_date,
                search_cfg=search_cfg,
                search_fn=search_fn,
            )
        except SearchSkipped as e:
            errors.append(("search", list_url, e.reason))
            errors.append(("discover", list_url, "search fallback skipped"))
            return [], errors
        if not items:
            errors.append(("discover", list_url, "search fallback returned 0 results"))
            return [], errors
        return apply_max_links(items, parse_max_links(source)), errors

    errors.append(("discover", list_url, f"unknown fallback={fallback!r}"))
    return [], errors


_SKIP_TEXT_TAGS = frozenset(
    {
        "script",
        "style",
        "noscript",
        "svg",
        "nav",
        "footer",
        "header",
        "aside",
        "form",
        "iframe",
    }
)


class TextExtractor(HTMLParser):
    """Strip chrome tags and collect visible text (readability heuristic)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TEXT_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TEXT_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self._parts.append(data.strip())


def _html_to_text(html: str) -> str:
    parser = TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001
        pass
    return "\n".join(parser._parts)


def extract_text(html: str, max_chars: int = CONTENT_MAX) -> str:
    """Extract readable body text; prefer ``<article>`` / ``<main>`` blocks."""
    blocks = _ARTICLE_BLOCK.findall(html)
    if blocks:
        focused = "\n".join(body for _tag, body in blocks)
        text = _html_to_text(focused)
        if len(text.strip()) >= CONTENT_MIN // 4:
            if len(text) > max_chars:
                return text[:max_chars]
            return text
    text = _html_to_text(html)
    if len(text) > max_chars:
        return text[:max_chars]
    return text


def extract_title(html: str) -> str | None:
    """Prefer ``og:title`` / ``twitter:title``, then ``<title>``."""
    for match in _META_TITLE_PROP.finditer(html):
        tag = match.group(0)
        content_m = _META_CONTENT_ATTR.search(tag)
        if content_m:
            title = unescape(content_m.group(1)).strip()
            if title:
                return " ".join(title.split())
    title_m = _TITLE_TAG.search(html)
    if title_m:
        title = unescape(re.sub(r"<[^>]+>", "", title_m.group(1))).strip()
        if title:
            return " ".join(title.split())
    return None


def is_bad_title(title: str | None, url: str) -> bool:
    """True when title is empty, whitespace-only, or just the URL."""
    if title is None:
        return True
    cleaned = " ".join(title.split()).strip()
    if not cleaned:
        return True
    url_norm = url.rstrip("/")
    if cleaned == url or cleaned == url_norm:
        return True
    if cleaned.startswith(("http://", "https://")):
        return True
    return False


def resolve_title(html: str, *, list_title: str | None, url: str) -> str:
    """Pick best title from list link text vs page meta/title."""
    page_title = extract_title(html)
    if list_title and not is_bad_title(list_title, url):
        return " ".join(list_title.split()).strip()
    if page_title and not is_bad_title(page_title, url):
        return page_title
    if list_title and list_title.strip():
        return " ".join(list_title.split()).strip()
    return page_title or url


def passes_article_gate(
    *,
    title: str | None,
    content: str | None,
    url: str,
    min_chars: int = CONTENT_MIN,
) -> bool:
    """Content/title gate for new pending entries (short/junk → reject)."""
    body = (content or "").strip()
    if len(body) < min_chars:
        return False
    if is_bad_title(title, url):
        return False
    return True


def parse_raw_ttl_days(cfg: dict[str, Any] | None, override: int | None = None) -> int:
    if override is not None:
        return max(0, int(override))
    if cfg:
        raw = cfg.get("raw_ttl_days")
        if isinstance(raw, bool):
            pass
        elif isinstance(raw, (int, float)):
            return max(0, int(raw))
        elif isinstance(raw, str) and raw.strip().isdigit():
            return max(0, int(raw.strip()))
    return DEFAULT_RAW_TTL_DAYS


def parse_iso_timestamp(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        ts = datetime.fromisoformat(text)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def raw_cache_fresh(
    fetched_at: str,
    ttl_days: int,
    *,
    now: datetime | None = None,
) -> bool:
    """True when ``fetched_at`` is within ``ttl_days`` of now."""
    ts = parse_iso_timestamp(fetched_at)
    if ts is None:
        return False
    current = now or datetime.now(timezone.utc)
    return (current - ts).total_seconds() <= ttl_days * 86400


def raw_index_path(ai_trends_dir: Path) -> Path:
    return ai_trends_dir / "raw" / RAW_INDEX_FILENAME


def load_raw_index(path: Path) -> dict[str, dict[str, Any]]:
    """Load url → index record from raw/index.jsonl (later lines win)."""
    index: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return index
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            url = row.get("url")
            if isinstance(url, str) and url:
                index[url] = row
    return index


def append_raw_index(
    path: Path,
    *,
    url: str,
    sha1: str,
    source: str,
    fetched_at: str,
    publish_date: str | None,
    title: str,
) -> None:
    """Append one JSONL record to raw/index.jsonl."""
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "url": url,
        "sha1": sha1,
        "source": source,
        "fetched_at": fetched_at,
        "publish_date": publish_date,
        "title": title,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def lookup_raw_cache(
    ai_trends_dir: Path,
    url: str,
    index: dict[str, dict[str, Any]],
    *,
    ttl_days: int,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Return a pending-shaped entry from raw cache, or None on miss/expiry."""
    meta = index.get(url)
    if not meta:
        return None
    fetched_at = meta.get("fetched_at")
    if not isinstance(fetched_at, str) or not raw_cache_fresh(
        fetched_at, ttl_days, now=now
    ):
        return None
    digest = meta.get("sha1")
    if not isinstance(digest, str) or not digest:
        digest = url_sha1(url)
    raw_path = ai_trends_dir / "raw" / f"{digest}.txt"
    if not raw_path.is_file():
        return None
    content = raw_path.read_text(encoding="utf-8")
    title = meta.get("title")
    if not isinstance(title, str) or not title.strip():
        title = url
    pub = meta.get("publish_date")
    if pub is not None and not isinstance(pub, str):
        pub = None
    source = meta.get("source")
    return {
        "url": url,
        "original_title": title,
        "publish_date": pub,
        "source": source if isinstance(source, str) else "",
        "content": content,
        "fetched_at": fetched_at,
    }


def persist_raw_entry(
    ai_trends_dir: Path,
    entry: dict[str, Any],
    *,
    save_raw: bool,
    index: dict[str, dict[str, Any]],
) -> None:
    """Write raw/<sha1>.txt and append raw/index.jsonl when save_raw."""
    if not save_raw:
        return
    content = entry.get("content") or ""
    if not content:
        return
    url = entry["url"]
    digest = url_sha1(url)
    write_raw(ai_trends_dir, url, content)
    fetched_at = entry.get("fetched_at") or datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    title = entry.get("original_title") or url
    pub = entry.get("publish_date")
    source = entry.get("source") or ""
    record = {
        "url": url,
        "sha1": digest,
        "source": source,
        "fetched_at": fetched_at,
        "publish_date": pub if isinstance(pub, str) else None,
        "title": title,
    }
    append_raw_index(
        raw_index_path(ai_trends_dir),
        url=url,
        sha1=digest,
        source=source,
        fetched_at=fetched_at,
        publish_date=pub if isinstance(pub, str) else None,
        title=title,
    )
    index[url] = record


def is_undated(publish_date: str | None) -> bool:
    """True when publish_date is missing or not parseable to YYYY-MM-DD."""
    if publish_date is None:
        return True
    return extract_date(publish_date) is None


def date_allows(
    publish_date: str | None,
    start_date: str,
    end_date: str,
    *,
    allow_undated: bool = False,
) -> bool:
    """Apply week-window date policy.

    - Parseable in ``[start_date, end_date]`` → allow.
    - Parseable out of range → reject.
    - Unparseable / missing → allow only when ``allow_undated`` is True
      (caller enforces ``undated_quota`` separately).
    """
    day = None if publish_date is None else extract_date(publish_date)
    if day is not None:
        return start_date <= day <= end_date
    return allow_undated


def parse_undated_quota(source: dict[str, Any], *, allow_undated: bool) -> int:
    """Max undated detail fetches for this source; 0 when undated disallowed."""
    if not allow_undated:
        return 0
    raw = source.get("undated_quota", 0)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def archive_url_set(archives: list) -> set[str]:
    return {e.get("url") for e in archives if isinstance(e, dict) and e.get("url")}


def write_raw(ai_trends_dir: Path, url: str, content: str) -> Path:
    raw_dir = ai_trends_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    digest = url_sha1(url)
    path = raw_dir / f"{digest}.txt"
    path.write_text(content, encoding="utf-8")
    return path


def process_candidate(
    item: dict[str, Any],
    *,
    source_name: str,
    use_proxy: Any,
    proxy: str | None,
    fetch_fn: FetchFn,
    ai_trends_dir: Path,
    mode: FetchMode = "http",
    browser_on_cloudflare: bool = True,
    browser_fetch_fn: FetchFn | None = None,
) -> dict[str, Any] | None:
    """Fetch detail page and build a pending entry, or None on failure.

    Does not write raw cache; caller persists after article gate passes.
    """
    url = item["url"]
    try:
        html, _method = fetch_with_policy(
            url,
            use_proxy=use_proxy,
            proxy=proxy,
            fetch_fn=fetch_fn,
            mode=mode,
            browser_on_cloudflare=browser_on_cloudflare,
            browser_fetch_fn=browser_fetch_fn,
        )
    except FetchError as e:
        append_error_log(ai_trends_dir, e.method, e.url, e.reason)
        return None

    content = extract_text(html)

    pub = item.get("publish_date")
    if pub is None:
        pub = date_from_url(url)
        if pub is None:
            m = re.search(
                r'<time[^>]*\bdatetime=["\'](\d{4}-\d{2}-\d{2})',
                html,
                re.I,
            )
            if m:
                pub = m.group(1)

    title = resolve_title(html, list_title=item.get("original_title"), url=url)
    return {
        "url": url,
        "original_title": title,
        "publish_date": pub,
        "source": source_name,
        "content": content,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def run(
    start_date: str,
    end_date: str,
    *,
    weekly_root=None,
    sources_path: Path | None = None,
    proxy: str | None = None,
    fetch_fn: FetchFn | None = None,
    browser_fetch_fn: FetchFn | None = None,
    save_raw: bool = True,
    resume: bool = True,
    fresh: bool = False,
    retry_errors: bool = False,
    pending_save_every: int = PENDING_SAVE_EVERY,
    raw_ttl_days: int | None = None,
    content_min: int = CONTENT_MIN,
    search_fn: SearchFn | None = None,
    search_cfg: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Core pipeline. Returns counts dict for summary line."""
    for label, d in (("start_date", start_date), ("end_date", end_date)):
        try:
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            print(f"ERROR: invalid {label} (expected YYYY-MM-DD): {d!r}", file=sys.stderr)
            sys.exit(2)

    ai_trends_dir = resolve_ai_trends_dir(end_date, weekly_root)
    sources_path = Path(sources_path) if sources_path else default_sources_path()
    if not sources_path.is_file():
        print(f"ERROR: sources.json not found: {sources_path}", file=sys.stderr)
        sys.exit(2)

    cfg = load_repo_config(Path(__file__))
    if proxy is None:
        raw_proxy = cfg.get("proxy")
        proxy = raw_proxy.strip() if isinstance(raw_proxy, str) and raw_proxy.strip() else None
    ttl_days = parse_raw_ttl_days(cfg, raw_ttl_days)
    if search_cfg is None:
        search_cfg = resolve_search_config(cfg)

    fetch_fn = fetch_fn or default_fetch
    sources = load_sources(sources_path)

    if fresh:
        clear_fetch_artifacts(ai_trends_dir)
        resume = False

    state_path = fetch_state_path(ai_trends_dir)
    state = load_fetch_state(state_path) if resume else {}
    raw_index = load_raw_index(raw_index_path(ai_trends_dir))

    archives_path = ai_trends_dir / "archives.json"
    if archives_path.exists():
        archives = load_json_array(archives_path, "archives.json")
    else:
        archives_path.write_text("[]\n", encoding="utf-8")
        archives = []
    known_urls = archive_url_set(archives)

    pending_path = ai_trends_dir / "pending.json"
    if resume:
        pending = load_pending_entries(pending_path)
        for entry in pending:
            known_urls.add(entry["url"])
    else:
        pending = []

    skipped = 0
    errors = 0
    since_save = 0

    def persist_pending() -> None:
        nonlocal since_save
        save_json_atomic(pending, pending_path)
        since_save = 0

    def record_state(url: str, status: str, source: str, *, with_sha1: bool = False) -> None:
        sha = url_sha1(url) if with_sha1 else None
        append_fetch_state(state_path, url=url, status=status, source=source, sha1=sha)
        state[url] = status

    def accept_entry(entry: dict[str, Any], *, status: str, source: str) -> None:
        nonlocal pending, since_save, skipped
        url = entry["url"]
        if not date_allows(
            entry.get("publish_date"),
            start_date,
            end_date,
            allow_undated=allow_undated,
        ):
            record_state(url, "skipped_date", source, with_sha1=True)
            skipped += 1
            return
        if not passes_article_gate(
            title=entry.get("original_title"),
            content=entry.get("content"),
            url=url,
            min_chars=content_min,
        ):
            record_state(url, "skipped_filter", source, with_sha1=True)
            skipped += 1
            return
        persist_raw_entry(ai_trends_dir, entry, save_raw=save_raw, index=raw_index)
        record_state(url, status, source, with_sha1=True)
        pending = merge_pending_by_url(pending, [entry])
        known_urls.add(url)
        since_save += 1
        if since_save >= pending_save_every:
            persist_pending()

    for source in sources:
        if not isinstance(source, dict):
            errors += 1
            continue
        name = source.get("name") or "unknown"
        list_url = source.get("url")
        if not isinstance(list_url, str) or not list_url.startswith(("http://", "https://")):
            append_error_log(ai_trends_dir, "config", str(list_url), "invalid source url")
            errors += 1
            continue

        use_proxy = source.get("use_proxy", "auto")
        url_include = source.get("url_include")
        url_exclude = source.get("url_exclude")
        allow_undated = bool(source.get("allow_undated", False))
        undated_quota = parse_undated_quota(source, allow_undated=allow_undated)
        undated_used = 0
        fetch_mode = parse_fetch_mode(source)
        boc = parse_browser_on_cloudflare(source)

        items, discover_errors = discover_source_items(
            source,
            start_date=start_date,
            end_date=end_date,
            use_proxy=use_proxy,
            proxy=proxy,
            fetch_fn=fetch_fn,
            search_cfg=search_cfg,
            search_fn=search_fn,
            mode=fetch_mode,
            browser_on_cloudflare=boc,
            browser_fetch_fn=browser_fetch_fn,
        )
        for method, err_url, reason in discover_errors:
            append_error_log(ai_trends_dir, method, err_url, reason)
        if not items:
            # Terminal discovery failure (or empty after skip/search)
            if discover_errors:
                errors += 1
            persist_pending()
            continue

        for item in items:
            url = item["url"]
            if url in known_urls:
                skipped += 1
                continue
            if should_skip_from_state(url, state, retry_errors=retry_errors):
                skipped += 1
                continue
            # Filter before any detail request
            if not url_allowed(
                url,
                list_url=list_url,
                url_include=url_include,
                url_exclude=url_exclude,
            ):
                record_state(url, "skipped_filter", name)
                skipped += 1
                continue
            pub = item.get("publish_date")
            if not date_allows(
                pub, start_date, end_date, allow_undated=allow_undated
            ):
                record_state(url, "skipped_date", name)
                skipped += 1
                continue
            if is_undated(pub):
                if undated_used >= undated_quota:
                    record_state(url, "skipped_date", name)
                    skipped += 1
                    continue
                undated_used += 1

            cached = lookup_raw_cache(
                ai_trends_dir, url, raw_index, ttl_days=ttl_days
            )
            if cached is not None:
                list_title = item.get("original_title")
                title = (
                    list_title
                    if list_title and not is_bad_title(list_title, url)
                    else cached.get("original_title") or url
                )
                entry = {
                    "url": url,
                    "original_title": title,
                    "publish_date": item.get("publish_date") or cached.get("publish_date"),
                    "source": name,
                    "content": cached.get("content") or "",
                    "fetched_at": cached.get("fetched_at"),
                }
                accept_entry(entry, status="cached", source=name)
                continue

            entry = process_candidate(
                item,
                source_name=name,
                use_proxy=use_proxy,
                proxy=proxy,
                fetch_fn=fetch_fn,
                ai_trends_dir=ai_trends_dir,
                mode=fetch_mode,
                browser_on_cloudflare=boc,
                browser_fetch_fn=browser_fetch_fn,
            )
            if entry is None:
                record_state(url, "error", name)
                errors += 1
                continue
            accept_entry(entry, status="fetched", source=name)

        # Persist after each source
        persist_pending()

    persist_pending()
    return {
        "sources": len(sources),
        "pending": len(pending),
        "skipped": skipped,
        "errors": errors,
    }


def format_summary(counts: dict[str, int]) -> str:
    return (
        f"sources={counts['sources']} pending={counts['pending']} "
        f"skipped={counts['skipped']} errors={counts['errors']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover links from sources.json and fetch bodies into pending.json.",
        epilog=(
            "Example: python3 discover_and_fetch.py "
            "--start-date 2026-07-18 --end-date 2026-07-24\n"
            "Default resumes from fetch_state.jsonl; use --fresh for a clean run."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--start-date", required=True, help="Inclusive start YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="Week dir / inclusive end YYYY-MM-DD")
    parser.add_argument("--weekly-root", default=None, help="Override weekly/ directory path")
    parser.add_argument(
        "--sources",
        default=None,
        help="Override sources.json path (default: skill references/sources.json)",
    )
    parser.add_argument(
        "--no-raw",
        action="store_true",
        help="Do not write raw/<sha1>.txt caches",
    )
    resume_group = parser.add_mutually_exclusive_group()
    resume_group.add_argument(
        "--resume",
        dest="fresh",
        action="store_false",
        help="Resume from fetch_state.jsonl and merge pending (default)",
    )
    resume_group.add_argument(
        "--fresh",
        dest="fresh",
        action="store_true",
        help="Clear fetch_state.jsonl and pending.json, then full re-run",
    )
    parser.set_defaults(fresh=False)
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Re-fetch URLs previously recorded as error in fetch_state",
    )
    args = parser.parse_args()

    counts = run(
        args.start_date,
        args.end_date,
        weekly_root=args.weekly_root,
        sources_path=Path(args.sources) if args.sources else None,
        save_raw=not args.no_raw,
        resume=not args.fresh,
        fresh=args.fresh,
        retry_errors=args.retry_errors,
    )
    print(format_summary(counts))


if __name__ == "__main__":
    main()
