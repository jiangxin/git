#!/usr/bin/env python3
"""Discover article URLs from sources.json and fetch into per-site article store.

Usage:
  python3 discover_and_fetch.py --start-date YYYY-MM-DD --end-date YYYY-MM-DD
  python3 discover_and_fetch.py ... --fresh          # clear state + articles
  python3 discover_and_fetch.py ... --retry-errors    # retry prior error URLs

Stdout summary: sources=N fetched=M skipped=K errors=E
Default ``--resume`` loads site ``index.jsonl`` + ``url_index.jsonl``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from fetch_backends import (  # noqa: E402
    DEFAULT_RETRY_BASE_DELAY,
    DEFAULT_RETRY_MAX,
    FetchError,
    FetchFn,
    FetchMode,
    fetch_html_with_backoff,
    fetch_http,
    fetch_http_with_headers,
    fetch_last_modified,
    parse_browser_on_cloudflare,
    parse_fetch_mode,
)
from filter_by_date import extract_date  # noqa: E402
from repo_config import load_repo_config  # noqa: E402
from restricted_search import (  # noqa: E402
    SearchFn,
    SearchSkipped,
    resolve_search_config,
    restricted_search,
)
from rss_parse import parse_feed  # noqa: E402
from pagination import (  # noqa: E402
    paginate_feed_discovery,
    paginate_html_discovery,
)
from site_store import (  # noqa: E402
    append_site_index,
    body_path,
    claim_url,
    load_site_index,
    load_url_index,
    meta_path,
    resolve_unique_slug,
    site_index_path,
    url_hash,
    url_index_path,
)
from url_date_cache import (  # noqa: E402
    append_cache as date_cache_append,
    load_cache as date_cache_load,
    lookup_date as date_cache_lookup,
)
from url_filter import url_allowed  # noqa: E402

CONTENT_MAX = 12000
CONTENT_MIN = 400
DEFAULT_BODY_TTL_DAYS = 7
DEFAULT_FETCH_CONCURRENCY = 4
DEFAULT_FETCH_CONCURRENCY_PER_SOURCE = 2
DEFAULT_SOURCE_CONCURRENCY = 4
TERMINAL_SKIP_STATUSES = frozenset(
    {"fetched", "skipped_date", "skipped_filter", "cached"}
)
_TITLE_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_TITLE_WS = re.compile(r"\s+")
COMMON_FEED_PATHS = ("/feed", "/rss", "/feed.xml", "/rss.xml", "/atom.xml")
_ERROR_LOG_LOCK = threading.Lock()
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
    ".css", ".js", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico",
    ".webp", ".pdf", ".zip", ".xml", ".json",
}
_URL_DATE = re.compile(r"/(20\d{2})[/-](\d{1,2})[/-](\d{1,2})(?:/|$)")
_URL_DATE_ISO = re.compile(r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)")

_HTML_DATE_JSONLD = re.compile(
    r'"date(?:Published|Created)"\s*:\s*"([^"]+)"'
)
_HTML_DATE_META_TIME = re.compile(
    r'<time[^>]*\bdatetime=["\']([^"\']+)["\']', re.I
)
_HTML_DATE_META_PUB = re.compile(
    r'<meta[^>]*\bproperty=["\']article:published_time["\'][^>]*\bcontent=["\']([^"\']+)["\']', re.I
)
_HTML_DATE_META_NAME = re.compile(
    r'<meta[^>]*\bname=["\'](?:publish_date|date)["\'][^>]*\bcontent=["\']([^"\']+)["\']', re.I
)
_HTML_DATE_ANTHROPIC = re.compile(
    r'agate[^"]*"[^>]*>'
    r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2},?\s+\d{4})<'
)
_HTML_DATE_META_AMUM = re.compile(
    r'class=["\']_amum["\']>'
    r'((?:January|February|March|April|May|June|July|August|September|October|November|December)'
    r'\s+\d{1,2},?\s+\d{4})<'
)
_HTML_DATE_TEXT = re.compile(
    r'>(?:'
    r'(?:January|February|March|April|May|June|July|August|September|October|November|December)'
    r'|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?'
    r')\s+\d{1,2},?\s+\d{4}<'
)

_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

default_fetch = fetch_http


def default_sources_path() -> Path:
    return SCRIPT_DIR.parent / "references" / "sources.json"


def infer_skill_subdir(sources_path: str | None, weekly_root: Path | None, end_date: str | None = None) -> str | None:
    if sources_path:
        p = str(sources_path)
        if "ai-trends" in p:
            return "ai-trends"
        if "git-news" in p:
            return "git-news"
    wr = Path(weekly_root) if weekly_root else SCRIPT_DIR.parents[0] / "weekly"
    if wr.is_dir() and end_date:
        week_dir = wr / end_date
        if week_dir.is_dir():
            subs = [
                d.name for d in week_dir.iterdir()
                if d.is_dir() and (d / "sites").is_dir()
            ]
            if len(subs) == 1:
                return subs[0]
    return None


def resolve_skill_dir(end_date: str, skill_subdir: str, weekly_root=None) -> Path:
    if not end_date:
        print("ERROR: end_date is required (YYYY-MM-DD)", file=sys.stderr)
        sys.exit(2)
    if weekly_root is None:
        repo_root = SCRIPT_DIR.parents[0]
        weekly_root = repo_root / "weekly"
    else:
        weekly_root = Path(weekly_root)
    skill_dir = Path(weekly_root) / end_date / skill_subdir
    if not skill_dir.is_dir():
        print(f"ERROR: {skill_subdir} directory not found: {skill_dir}", file=sys.stderr)
        print("Run setup_week.py first.", file=sys.stderr)
        sys.exit(2)
    return skill_dir


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
    with _ERROR_LOG_LOCK:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line)


def clear_fetch_artifacts(ai_trends_dir: Path) -> None:
    sites_root = ai_trends_dir / "sites"
    if sites_root.exists():
        shutil.rmtree(sites_root)
    url_idx = ai_trends_dir / "url_index.jsonl"
    if url_idx.exists():
        url_idx.unlink()
    url_lock = ai_trends_dir / "url_index.jsonl.lock"
    if url_lock.exists():
        url_lock.unlink()


def fetch_with_policy(
    url: str,
    *,
    use_proxy: Any,
    proxy: str | None,
    fetch_fn: FetchFn,
    mode: FetchMode = "http",
    browser_on_cloudflare: bool = True,
    browser_fetch_fn: FetchFn | None = None,
    max_retries: int = DEFAULT_RETRY_MAX,
    base_delay: float = DEFAULT_RETRY_BASE_DELAY,
    sleep_fn: Callable[[float], None] | None = None,
) -> tuple[str, str]:
    return fetch_html_with_backoff(
        url,
        mode=mode,
        use_proxy=use_proxy,
        proxy=proxy,
        browser_on_cloudflare=browser_on_cloudflare,
        http_fetch_fn=fetch_fn,
        browser_fetch_fn=browser_fetch_fn,
        max_retries=max_retries,
        base_delay=base_delay,
        sleep_fn=sleep_fn,
    )


def parse_concurrency(cfg: dict[str, Any] | None) -> tuple[int, int]:
    global_n = DEFAULT_FETCH_CONCURRENCY
    per_source = DEFAULT_FETCH_CONCURRENCY_PER_SOURCE
    if not cfg:
        return global_n, per_source
    raw_g = cfg.get("fetch_concurrency")
    if isinstance(raw_g, (int, float)) and not isinstance(raw_g, bool):
        global_n = max(1, int(raw_g))
    elif isinstance(raw_g, str) and raw_g.strip().isdigit():
        global_n = max(1, int(raw_g.strip()))
    raw_p = cfg.get("fetch_concurrency_per_source")
    if isinstance(raw_p, (int, float)) and not isinstance(raw_p, bool):
        per_source = max(1, int(raw_p))
    elif isinstance(raw_p, str) and raw_p.strip().isdigit():
        per_source = max(1, int(raw_p))
    return global_n, per_source


def parse_source_concurrency(cfg: dict[str, Any] | None) -> int:
    n = DEFAULT_SOURCE_CONCURRENCY
    if not cfg:
        return n
    raw = cfg.get("source_concurrency")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        n = max(1, int(raw))
    elif isinstance(raw, str) and raw.strip().isdigit():
        n = max(1, int(raw.strip()))
    return n


def normalize_event_key(title: str | None, url: str | None = None) -> str:
    text = (title or "").strip().lower()
    text = _TITLE_PUNCT.sub("", text)
    text = _TITLE_WS.sub(" ", text).strip()
    if text:
        return f"title:{text}"
    if isinstance(url, str) and url:
        parsed = urlparse(url)
        path = (parsed.path or "/").rstrip("/") or "/"
        return f"path:{parsed.netloc.lower()}{path.lower()}"
    return "empty:"


def _rank_hint_sort_key(entry: dict[str, Any]) -> tuple[float, int]:
    hint = entry.get("rank_hint")
    try:
        rank = float(hint) if hint is not None else float("inf")
    except (TypeError, ValueError):
        rank = float("inf")
    content_len = len(entry.get("content") or "")
    return (rank, -content_len)


def dedupe_pending_events(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("url"):
            continue
        key = normalize_event_key(entry.get("original_title"), entry.get("url"))
        if key not in clusters:
            order.append(key)
            clusters[key] = []
        clusters[key].append(entry)
    result: list[dict[str, Any]] = []
    for key in order:
        group = clusters[key]
        if len(group) == 1:
            result.append(group[0])
            continue
        primary = min(group, key=_rank_hint_sort_key)
        related: list[str] = []
        existing_related = primary.get("related_urls")
        if isinstance(existing_related, list):
            related.extend(u for u in existing_related if isinstance(u, str) and u)
        primary_url = primary.get("url")
        for other in group:
            other_url = other.get("url")
            if (
                isinstance(other_url, str)
                and other_url
                and other_url != primary_url
                and other_url not in related
            ):
                related.append(other_url)
        out = dict(primary)
        if related:
            out["related_urls"] = related
        result.append(out)
    return result


def date_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    m = _URL_DATE.search(parsed.path)
    if not m:
        m = _URL_DATE_ISO.search(f"{parsed.path}?{parsed.query}")
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
    return abs_url.split("#", 1)[0]


class LinkCollector(HTMLParser):
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
        base_norm = self.base_url.rstrip("/")
        if url.rstrip("/") == base_norm:
            return
        title = " ".join("".join(self._parts).split()).strip() or url
        pub = self._attr_date or self._last_time or date_from_url(url)
        self._seen.add(url)
        self.links.append({"url": url, "original_title": title, "publish_date": pub})


def extract_links(
    html: str, base_url: str, *, date_attr: str | None = None,
) -> list[dict[str, Any]]:
    collector = LinkCollector(base_url, date_attr=date_attr)
    try:
        collector.feed(html)
        collector.close()
    except Exception:  # noqa: BLE001
        pass
    return collector.links


def parse_max_links(source: dict[str, Any]) -> int | None:
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
    max_pages: int = 1,
) -> tuple[list[dict[str, Any]], list[tuple[str, str, str]]]:
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
        if max_pages > 1:
            def _fetch_feed(url: str) -> str:
                body, _ = fetch_with_policy(
                    url,
                    use_proxy=use_proxy,
                    proxy=proxy,
                    fetch_fn=fetch_fn,
                    mode=fetch_mode,
                    browser_on_cloudflare=boc,
                    browser_fetch_fn=browser_fetch_fn,
                )
                return body

            def _parse_feed(xml_text: str, base_url: str) -> list[dict[str, Any]]:
                return parse_feed(xml_text, base_url=base_url)

            try:
                items, pag_errors = paginate_feed_discovery(
                    rss_url,
                    fetch_feed_fn=_fetch_feed,
                    parse_feed_fn=_parse_feed,
                    max_pages=max_pages,
                    start_date=start_date,
                )
                errors.extend(pag_errors)
            except Exception as exc:
                errors.append(("pagination", rss_url, str(exc)))
        else:
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
        if max_pages > 1:
            def _fetch_page(url: str) -> str:
                body, _ = fetch_with_policy(
                    url,
                    use_proxy=use_proxy,
                    proxy=proxy,
                    fetch_fn=fetch_fn,
                    mode=fetch_mode,
                    browser_on_cloudflare=boc,
                    browser_fetch_fn=browser_fetch_fn,
                )
                return body

            def _extract(html: str, url: str) -> list[dict[str, Any]]:
                return extract_links(html, url, date_attr=date_attr)

            try:
                items, pag_errors = paginate_html_discovery(
                    list_url,
                    fetch_page_fn=_fetch_page,
                    extract_links_fn=_extract,
                    max_pages=max_pages,
                    start_date=start_date,
                )
                errors.extend(pag_errors)
            except Exception as exc:
                errors.append(("pagination", list_url, str(exc)))
        else:
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


_SKIP_TEXT_TAGS = frozenset({
    "script", "style", "noscript", "svg", "nav", "footer",
    "header", "aside", "form", "iframe",
})


class TextExtractor(HTMLParser):
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
    page_title = extract_title(html)
    if list_title and not is_bad_title(list_title, url):
        return " ".join(list_title.split()).strip()
    if page_title and not is_bad_title(page_title, url):
        return page_title
    if list_title and list_title.strip():
        return " ".join(list_title.split()).strip()
    return page_title or url


def _normalize_date_text(raw: str) -> str | None:
    text = raw.strip().rstrip(".")
    if not text:
        return None
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            return None
    m = re.match(
        r"(January|February|March|April|May|June|July|August|September|October|November|December"
        r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})",
        text, re.I,
    )
    if m:
        month_num = _MONTH_NAMES.get(m.group(1).lower())
        if month_num:
            try:
                return datetime(int(m.group(3)), month_num, int(m.group(2))).strftime("%Y-%m-%d")
            except ValueError:
                return None
    return None


def extract_date_from_html(html: str) -> str | None:
    for pattern in [
        _HTML_DATE_JSONLD, _HTML_DATE_META_TIME, _HTML_DATE_META_PUB,
        _HTML_DATE_META_NAME, _HTML_DATE_ANTHROPIC, _HTML_DATE_META_AMUM,
    ]:
        m = pattern.search(html)
        if m:
            result = _normalize_date_text(m.group(1))
            if result:
                return result
    m = _HTML_DATE_TEXT.search(html)
    if m:
        result = _normalize_date_text(m.group(0).strip("<>"))
        if result:
            return result
    return None


def passes_article_gate(
    *,
    title: str | None,
    content: str | None,
    url: str,
    min_chars: int = CONTENT_MIN,
) -> bool:
    body = (content or "").strip()
    if len(body) < min_chars:
        return False
    if is_bad_title(title, url):
        return False
    return True


def parse_body_ttl_days(cfg: dict[str, Any] | None, override: int | None = None) -> int:
    if override is not None:
        return max(0, int(override))
    if cfg:
        raw = cfg.get("body_ttl_days") or cfg.get("raw_ttl_days")
        if isinstance(raw, bool):
            pass
        elif isinstance(raw, (int, float)):
            return max(0, int(raw))
        elif isinstance(raw, str) and raw.strip().isdigit():
            return max(0, int(raw.strip()))
    return DEFAULT_BODY_TTL_DAYS


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


def body_cache_fresh(
    fetched_at: str, ttl_days: int, *, now: datetime | None = None,
) -> bool:
    ts = parse_iso_timestamp(fetched_at)
    if ts is None:
        return False
    current = now or datetime.now(timezone.utc)
    return (current - ts).total_seconds() <= ttl_days * 86400


def is_undated(publish_date: str | None) -> bool:
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
    day = None if publish_date is None else extract_date(publish_date)
    if day is not None:
        return start_date <= day <= end_date
    return allow_undated


def parse_undated_quota(source: dict[str, Any], *, allow_undated: bool) -> int:
    if not allow_undated:
        return 0
    raw = source.get("undated_quota", 0)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def should_skip_from_site_index(
    url: str,
    site_index: dict[str, dict[str, Any]],
    *,
    retry_errors: bool,
) -> bool:
    record = site_index.get(url)
    if record is None:
        return False
    status = record.get("status")
    if status is None:
        return False
    if status in TERMINAL_SKIP_STATUSES:
        return True
    if status == "error":
        return not retry_errors
    return False


def lookup_body_cache(
    ai_trends_dir: Path, slug: str, url: str,
    site_index: dict[str, dict[str, Any]],
    *, ttl_days: int, now: datetime | None = None,
) -> dict[str, Any] | None:
    record = site_index.get(url)
    if record is None:
        return None
    status = record.get("status")
    if status not in ("fetched", "cached"):
        return None
    h = record.get("hash")
    if not isinstance(h, str) or not h:
        return None
    b_path = body_path(ai_trends_dir, slug, h)
    m_path = meta_path(ai_trends_dir, slug, h)
    if not b_path.is_file() or not m_path.is_file():
        return None
    try:
        meta = json.loads(m_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    fetched_at = meta.get("fetched_at")
    if not isinstance(fetched_at, str) or not body_cache_fresh(fetched_at, ttl_days, now=now):
        return None
    body = b_path.read_text(encoding="utf-8")
    return {
        "url": url,
        "original_title": meta.get("original_title") or url,
        "publish_date": meta.get("publish_date"),
        "source": meta.get("source") or "",
        "content": body,
        "fetched_at": fetched_at,
    }


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
    max_retries: int = DEFAULT_RETRY_MAX,
    base_delay: float = DEFAULT_RETRY_BASE_DELAY,
    sleep_fn: Callable[[float], None] | None = None,
    date_cache: dict[str, dict] | None = None,
    site_slug: str = "",
    head_fn: Callable[..., str | None] | None = None,
    browser_date_fn: Callable[..., str | None] | None = None,
    skip_date_fallbacks: bool = False,
) -> dict[str, Any] | None:
    url = item["url"]

    cached_date, cache_hit = date_cache_lookup(url, date_cache or {})
    if cache_hit and cached_date:
        item = dict(item)
        item["publish_date"] = cached_date

    try:
        html, _method = fetch_with_policy(
            url,
            use_proxy=use_proxy,
            proxy=proxy,
            fetch_fn=fetch_fn,
            mode=mode,
            browser_on_cloudflare=browser_on_cloudflare,
            browser_fetch_fn=browser_fetch_fn,
            max_retries=max_retries,
            base_delay=base_delay,
            sleep_fn=sleep_fn,
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
                html, re.I,
            )
            if m:
                pub = m.group(1)

    date_method = "list_or_url"
    if pub is None or is_undated(pub):
        html_date = extract_date_from_html(html)
        if html_date:
            pub = html_date
            date_method = "html_extract"
        elif not skip_date_fallbacks:
            _head_fn = head_fn if head_fn is not None else (
                lambda u, **kw: fetch_last_modified(u, proxy=kw.get("proxy"), use_proxy_flag=kw.get("use_proxy_flag", False))
            )
            head_date = _head_fn(url, proxy=proxy, use_proxy_flag=bool(use_proxy is True))
            if head_date:
                pub = head_date
                date_method = "last_modified"
            else:
                _browser_date_fn = browser_date_fn if browser_date_fn is not None else _default_browser_date
                browser_date = _browser_date_fn(
                    url, use_proxy=use_proxy, proxy=proxy, browser_fetch_fn=browser_fetch_fn,
                )
                if browser_date:
                    pub = browser_date
                    date_method = "browser_html"

    if date_cache is not None and pub:
        date_cache_append(url, pub, method=date_method)
    elif date_cache is not None and (pub is None or is_undated(pub)):
        date_cache_append(url, None, method="undated")

    title = resolve_title(html, list_title=item.get("original_title"), url=url)
    return {
        "url": url,
        "original_title": title,
        "publish_date": pub,
        "source": source_name,
        "content": content,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _default_browser_date(
    url: str,
    *,
    use_proxy: Any,
    proxy: str | None,
    browser_fetch_fn: FetchFn | None = None,
) -> str | None:
    try:
        browser_html, _bm = fetch_html_with_backoff(
            url, mode="browser", use_proxy=use_proxy, proxy=proxy,
            browser_fetch_fn=browser_fetch_fn, timeout=45,
        )
        return extract_date_from_html(browser_html)
    except FetchError:
        return None


def run(
    start_date: str,
    end_date: str,
    *,
    skill_subdir: str,
    weekly_root=None,
    sources_path: Path | None = None,
    proxy: str | None = None,
    fetch_fn: FetchFn | None = None,
    browser_fetch_fn: FetchFn | None = None,
    resume: bool = True,
    fresh: bool = False,
    retry_errors: bool = False,
    body_ttl_days: int | None = None,
    content_min: int = CONTENT_MIN,
    search_fn: SearchFn | None = None,
    search_cfg: dict[str, Any] | None = None,
    fetch_concurrency: int | None = None,
    fetch_concurrency_per_source: int | None = None,
    source_concurrency: int | None = None,
    max_pages: int | None = None,
    max_retries: int = DEFAULT_RETRY_MAX,
    retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY,
    sleep_fn: Callable[[float], None] | None = None,
) -> dict[str, int]:
    for label, d in (("start_date", start_date), ("end_date", end_date)):
        try:
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            print(f"ERROR: invalid {label} (expected YYYY-MM-DD): {d!r}", file=sys.stderr)
            sys.exit(2)

    ai_trends_dir = resolve_skill_dir(end_date, skill_subdir, weekly_root)
    sources_path = Path(sources_path) if sources_path else default_sources_path()
    if not sources_path.is_file():
        print(f"ERROR: sources.json not found: {sources_path}", file=sys.stderr)
        sys.exit(2)

    cfg = load_repo_config(Path(__file__))
    if proxy is None:
        raw_proxy = cfg.get("proxy")
        proxy = raw_proxy.strip() if isinstance(raw_proxy, str) and raw_proxy.strip() else None
    ttl_days = parse_body_ttl_days(cfg, body_ttl_days)
    if search_cfg is None:
        search_cfg = resolve_search_config(cfg)
    cfg_global, cfg_per_source = parse_concurrency(cfg)
    global_workers = (
        max(1, int(fetch_concurrency))
        if fetch_concurrency is not None
        else cfg_global
    )
    per_source_workers = (
        max(1, int(fetch_concurrency_per_source))
        if fetch_concurrency_per_source is not None
        else cfg_per_source
    )
    cfg_source_conc = parse_source_concurrency(cfg)
    source_workers = min(
        max(1, int(source_concurrency)) if source_concurrency is not None else cfg_source_conc,
        max(1, len([s for s in load_sources(sources_path) if isinstance(s, dict)])),
    )
    default_max_pages = max_pages if max_pages is not None else int(cfg.get("default_max_pages", 1))

    fetch_fn = fetch_fn or default_fetch
    sources = load_sources(sources_path)

    if fresh:
        clear_fetch_artifacts(ai_trends_dir)
        resume = False

    url_index = load_url_index(url_index_path(ai_trends_dir)) if resume else {}
    known_urls: set[str] = set(url_index.keys())
    known_urls_lock = threading.Lock()
    taken_slugs: set[str] = set()
    taken_slugs_lock = threading.Lock()
    counters_lock = threading.Lock()
    counters = {"fetched": 0, "skipped": 0, "errors": 0}
    global_sem = threading.Semaphore(global_workers)

    resolved_slugs: list[tuple[int, str]] = []
    for i, source in enumerate(sources):
        if not isinstance(source, dict):
            resolved_slugs.append((i, ""))
            continue
        with taken_slugs_lock:
            slug_res = resolve_unique_slug(ai_trends_dir, source, taken=taken_slugs)
            slug = slug_res.slug
            taken_slugs.add(slug)
        resolved_slugs.append((i, slug))

    def _process_source(source: dict, slug: str) -> None:
        nonlocal counters
        name = source.get("name") or "unknown"
        list_url = source.get("url")
        if not isinstance(list_url, str) or not list_url.startswith(("http://", "https://")):
            append_error_log(ai_trends_dir, "config", str(list_url), "invalid source url")
            with counters_lock:
                counters["errors"] += 1
            return

        use_proxy = source.get("use_proxy", "auto")
        url_include = source.get("url_include")
        url_exclude = source.get("url_exclude")
        allow_undated = bool(source.get("allow_undated", False))
        undated_quota = parse_undated_quota(source, allow_undated=allow_undated)
        undated_used = 0
        fetch_mode = parse_fetch_mode(source)
        boc = parse_browser_on_cloudflare(source)
        src_max_pages = source.get("max_pages")
        eff_max_pages = int(src_max_pages) if src_max_pages is not None else default_max_pages

        site_idx_path = site_index_path(ai_trends_dir, slug)
        site_index = load_site_index(site_idx_path) if resume else {}

        date_cache = date_cache_load() if fetch_fn is default_fetch else None

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
            max_pages=eff_max_pages,
        )
        for method, err_url, reason in discover_errors:
            append_error_log(ai_trends_dir, method, err_url, reason)
        if not items:
            if discover_errors:
                with counters_lock:
                    counters["errors"] += 1
            return

        # Detect if items are sorted by date descending (for early-stop)
        dated_items = [it for it in items if it.get("publish_date")]
        items_descending = False
        if len(dated_items) >= 2:
            dates = [it["publish_date"] for it in dated_items[:5]]
            items_descending = all(dates[i] >= dates[i + 1] for i in range(len(dates) - 1))

        to_fetch: list[dict[str, Any]] = []
        for item in items:
            url = item["url"]
            with known_urls_lock:
                if url in known_urls:
                    with counters_lock:
                        counters["skipped"] += 1
                    continue
            if should_skip_from_site_index(url, site_index, retry_errors=retry_errors):
                with counters_lock:
                    counters["skipped"] += 1
                continue
            if not url_allowed(
                url,
                list_url=list_url,
                url_include=url_include,
                url_exclude=url_exclude,
            ):
                append_site_index(
                    site_idx_path, url=url, status="skipped_filter", hash=url_hash(url),
                )
                site_index[url] = {"url": url, "status": "skipped_filter"}
                with counters_lock:
                    counters["skipped"] += 1
                continue
            pub = item.get("publish_date")
            if date_cache is not None:
                cached_date, cache_hit = date_cache_lookup(url, date_cache)
                if cache_hit:
                    if cached_date:
                        pub = cached_date
                        item["publish_date"] = pub
                    elif not allow_undated:
                        append_site_index(
                            site_idx_path, url=url, status="skipped_date", hash=url_hash(url),
                        )
                        site_index[url] = {"url": url, "status": "skipped_date"}
                        with counters_lock:
                            counters["skipped"] += 1
                        continue
            if not date_allows(pub, start_date, end_date, allow_undated=allow_undated):
                append_site_index(
                    site_idx_path, url=url, status="skipped_date", hash=url_hash(url),
                )
                site_index[url] = {"url": url, "status": "skipped_date"}
                with counters_lock:
                    counters["skipped"] += 1
                # Early-stop: if items are descending and this one is before
                # start_date, all remaining items will also be out of range
                if items_descending and pub and pub < start_date:
                    break
                continue
            if is_undated(pub):
                if undated_used >= undated_quota:
                    append_site_index(
                        site_idx_path, url=url, status="skipped_date", hash=url_hash(url),
                    )
                    site_index[url] = {"url": url, "status": "skipped_date"}
                    with counters_lock:
                        counters["skipped"] += 1
                    continue
                undated_used += 1

            cached = lookup_body_cache(
                ai_trends_dir, slug, url, site_index, ttl_days=ttl_days,
            )
            if cached is not None:
                list_title = item.get("original_title")
                title = (
                    list_title
                    if list_title and not is_bad_title(list_title, url)
                    else cached.get("original_title") or url
                )
                result = claim_url(
                    ai_trends_dir,
                    url=url,
                    slug=slug,
                    meta={
                        "original_title": title,
                        "publish_date": item.get("publish_date") or cached.get("publish_date"),
                        "source": name,
                        "status": "cached",
                        "fetched_at": cached.get("fetched_at"),
                    },
                    body=cached.get("content") or "",
                )
                if result.won and result.url_index_won:
                    with counters_lock:
                        counters["fetched"] += 1
                    with known_urls_lock:
                        known_urls.add(url)
                    site_index[url] = {"url": url, "status": "cached", "hash": result.hash}
                else:
                    with counters_lock:
                        counters["skipped"] += 1
                continue

            to_fetch.append(item)

        def _fetch_one(item: dict[str, Any]) -> dict[str, Any] | None:
            with global_sem:
                return process_candidate(
                    item,
                    source_name=name,
                    use_proxy=use_proxy,
                    proxy=proxy,
                    fetch_fn=fetch_fn,
                    ai_trends_dir=ai_trends_dir,
                    mode=fetch_mode,
                    browser_on_cloudflare=boc,
                    browser_fetch_fn=browser_fetch_fn,
                    max_retries=max_retries,
                    base_delay=retry_base_delay,
                    sleep_fn=sleep_fn,
                    date_cache=date_cache,
                    site_slug=slug,
                    skip_date_fallbacks=(fetch_fn is not default_fetch),
                )

        if to_fetch:
            workers = min(per_source_workers, len(to_fetch))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_fetch_one, item): item for item in to_fetch}
                for fut in as_completed(futures):
                    item = futures[fut]
                    url = item["url"]
                    try:
                        entry = fut.result()
                    except Exception as e:  # noqa: BLE001
                        append_error_log(
                            ai_trends_dir, "fetch", url, str(e) or type(e).__name__
                        )
                        append_site_index(
                            site_idx_path, url=url, status="error", hash=url_hash(url),
                        )
                        site_index[url] = {"url": url, "status": "error"}
                        with counters_lock:
                            counters["errors"] += 1
                        continue
                    if entry is None:
                        append_site_index(
                            site_idx_path, url=url, status="error", hash=url_hash(url),
                        )
                        site_index[url] = {"url": url, "status": "error"}
                        with counters_lock:
                            counters["errors"] += 1
                        continue
                    if not date_allows(
                        entry.get("publish_date"), start_date, end_date,
                        allow_undated=allow_undated,
                    ):
                        append_site_index(
                            site_idx_path, url=url, status="skipped_date", hash=url_hash(url),
                        )
                        site_index[url] = {"url": url, "status": "skipped_date"}
                        with counters_lock:
                            counters["skipped"] += 1
                        continue
                    if not passes_article_gate(
                        title=entry.get("original_title"),
                        content=entry.get("content"),
                        url=url,
                        min_chars=content_min,
                    ):
                        append_site_index(
                            site_idx_path, url=url, status="skipped_filter", hash=url_hash(url),
                        )
                        site_index[url] = {"url": url, "status": "skipped_filter"}
                        with counters_lock:
                            counters["skipped"] += 1
                        continue
                    result = claim_url(
                        ai_trends_dir,
                        url=url,
                        slug=slug,
                        meta={
                            "original_title": entry.get("original_title"),
                            "publish_date": entry.get("publish_date"),
                            "source": name,
                            "status": "fetched",
                            "fetched_at": entry.get("fetched_at"),
                        },
                        body=entry.get("content") or "",
                    )
                    if result.won and result.url_index_won:
                        with counters_lock:
                            counters["fetched"] += 1
                        with known_urls_lock:
                            known_urls.add(url)
                        site_index[url] = {"url": url, "status": "fetched", "hash": result.hash}
                    else:
                        with counters_lock:
                            counters["skipped"] += 1

    valid_sources = [
        (s, slug) for (i, slug), s in zip(resolved_slugs, sources)
        if isinstance(s, dict) and slug
    ]
    if source_workers <= 1 or len(valid_sources) <= 1:
        for source, slug in valid_sources:
            _process_source(source, slug)
    else:
        with ThreadPoolExecutor(max_workers=source_workers) as pool:
            futs = [
                pool.submit(_process_source, source, slug)
                for source, slug in valid_sources
            ]
            for fut in futs:
                fut.result()

    return {
        "sources": len(sources),
        "fetched": counters["fetched"],
        "skipped": counters["skipped"],
        "errors": counters["errors"],
    }


def format_summary(counts: dict[str, int]) -> str:
    return (
        f"sources={counts['sources']} fetched={counts['fetched']} "
        f"skipped={counts['skipped']} errors={counts['errors']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover links from sources.json and fetch into per-site article store.",
        epilog=(
            "Example: python3 discover_and_fetch.py "
            "--start-date 2026-07-18 --end-date 2026-07-24\n"
            "Default resumes from site indexes; use --fresh for a clean run."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--start-date", required=True, help="Inclusive start YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="Week dir / inclusive end YYYY-MM-DD")
    parser.add_argument("--weekly-root", default=None, help="Override weekly/ directory path")
    parser.add_argument(
        "--skill-subdir", default=None,
        help="Subdirectory under weekly/<end_date>/ (e.g. ai-trends, git-news); "
             "auto-inferred from --sources path or weekly dir when omitted",
    )
    parser.add_argument(
        "--sources", default=None,
        help="Override sources.json path (default: skill references/sources.json)",
    )
    resume_group = parser.add_mutually_exclusive_group()
    resume_group.add_argument(
        "--resume", dest="fresh", action="store_false",
        help="Resume from site indexes and url_index (default)",
    )
    resume_group.add_argument(
        "--fresh", dest="fresh", action="store_true",
        help="Clear sites/ and url_index.jsonl, then full re-run",
    )
    parser.set_defaults(fresh=False)
    parser.add_argument(
        "--retry-errors", action="store_true",
        help="Re-fetch URLs previously recorded as error in site index",
    )
    parser.add_argument(
        "--max-pages", type=int, default=None, metavar="N",
        help="Max pages to fetch per source (default: from config or 1)",
    )
    args = parser.parse_args()

    skill_subdir = args.skill_subdir
    if not skill_subdir:
        skill_subdir = infer_skill_subdir(args.sources, args.weekly_root, args.end_date)
    if not skill_subdir:
        parser.error(
            "Cannot determine --skill-subdir automatically. "
            "Pass --skill-subdir explicitly (e.g. ai-trends, git-news)."
        )

    counts = run(
        args.start_date,
        args.end_date,
        skill_subdir=skill_subdir,
        weekly_root=args.weekly_root,
        sources_path=Path(args.sources) if args.sources else None,
        resume=not args.fresh,
        fresh=args.fresh,
        retry_errors=args.retry_errors,
        max_pages=args.max_pages,
    )
    print(format_summary(counts))


if __name__ == "__main__":
    main()
