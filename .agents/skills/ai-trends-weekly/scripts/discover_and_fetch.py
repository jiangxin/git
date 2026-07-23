#!/usr/bin/env python3
"""Discover article URLs from sources.json and fetch bodies into pending.json.

Usage:
  python3 discover_and_fetch.py --start-date YYYY-MM-DD --end-date YYYY-MM-DD

Stdout summary: sources=N pending=M skipped=K errors=E
First version overwrites pending.json each run; no WebSearch fallback.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
# __file__ parents[2] == skills/  →  skills/_shared/scripts
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared" / "scripts"))

from check_cloudflare import is_cloudflare  # noqa: E402
from filter_by_date import extract_date  # noqa: E402
from json_archives import load_json_array, save_json_atomic  # noqa: E402
from repo_config import load_repo_config  # noqa: E402
from url_filter import url_allowed  # noqa: E402

CONTENT_MAX = 12000
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
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

FetchFn = Callable[..., str]


class FetchError(Exception):
    """HTTP or Cloudflare failure while fetching a URL."""

    def __init__(self, url: str, method: str, reason: str):
        super().__init__(reason)
        self.url = url
        self.method = method
        self.reason = reason


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


def proxy_attempts(use_proxy: Any, proxy: str | None) -> list[bool]:
    """Return ordered list of whether to use proxy for each attempt."""
    has_proxy = bool(proxy)
    if use_proxy is True:
        return [True] if has_proxy else [False]
    if use_proxy is False:
        return [False, True] if has_proxy else [False]
    # "auto" or anything else: direct first, then proxy
    return [False, True] if has_proxy else [False]


def method_label(use_proxy_flag: bool) -> str:
    return "curl(proxy)" if use_proxy_flag else "curl(direct)"


def default_fetch(url: str, *, proxy: str | None, use_proxy_flag: bool, timeout: int = 30) -> str:
    """Fetch URL via urllib with browser-like headers. Raises FetchError."""
    method = method_label(use_proxy_flag)
    handlers = []
    if use_proxy_flag and proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    try:
        with opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as e:
        raise FetchError(url, method, f"HTTP {e.code}") from e
    except Exception as e:  # noqa: BLE001 — surface as fetch failure
        raise FetchError(url, method, str(e) or type(e).__name__) from e


def fetch_with_policy(
    url: str,
    *,
    use_proxy: Any,
    proxy: str | None,
    fetch_fn: FetchFn,
) -> tuple[str, str]:
    """Try fetch attempts per use_proxy; return (html, method_label)."""
    last_err: FetchError | None = None
    for flag in proxy_attempts(use_proxy, proxy):
        method = method_label(flag)
        try:
            html = fetch_fn(url, proxy=proxy, use_proxy_flag=flag)
        except FetchError as e:
            last_err = e
            continue
        if is_cloudflare(html):
            last_err = FetchError(url, method, "Cloudflare challenge")
            continue
        return html, method
    if last_err is None:
        last_err = FetchError(url, "curl", "fetch failed")
    raise last_err


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


class TextExtractor(HTMLParser):
    """Strip script/style and collect visible text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript", "svg"):
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript", "svg") and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self._parts.append(data.strip())


def extract_text(html: str, max_chars: int = CONTENT_MAX) -> str:
    parser = TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001
        pass
    text = "\n".join(parser._parts)
    if len(text) > max_chars:
        return text[:max_chars]
    return text


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
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
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
    save_raw: bool,
) -> dict[str, Any] | None:
    """Fetch detail page and build a pending entry, or None on failure."""
    url = item["url"]
    try:
        html, _method = fetch_with_policy(
            url, use_proxy=use_proxy, proxy=proxy, fetch_fn=fetch_fn
        )
    except FetchError as e:
        append_error_log(ai_trends_dir, e.method, e.url, e.reason)
        return None

    content = extract_text(html)
    if save_raw and content:
        write_raw(ai_trends_dir, url, content)

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

    title = item.get("original_title") or url
    return {
        "url": url,
        "original_title": title,
        "publish_date": pub,
        "source": source_name,
        "content": content,
        "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }


def run(
    start_date: str,
    end_date: str,
    *,
    weekly_root=None,
    sources_path: Path | None = None,
    proxy: str | None = None,
    fetch_fn: FetchFn | None = None,
    save_raw: bool = True,
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

    if proxy is None:
        cfg = load_repo_config(Path(__file__))
        raw_proxy = cfg.get("proxy")
        proxy = raw_proxy.strip() if isinstance(raw_proxy, str) and raw_proxy.strip() else None

    fetch_fn = fetch_fn or default_fetch
    sources = load_sources(sources_path)

    archives_path = ai_trends_dir / "archives.json"
    if archives_path.exists():
        archives = load_json_array(archives_path, "archives.json")
    else:
        archives_path.write_text("[]\n", encoding="utf-8")
        archives = []
    known_urls = archive_url_set(archives)

    pending: list[dict[str, Any]] = []
    skipped = 0
    errors = 0

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
        date_attr = source.get("date_attr") if isinstance(source.get("date_attr"), str) else None
        url_include = source.get("url_include")
        url_exclude = source.get("url_exclude")
        allow_undated = bool(source.get("allow_undated", False))
        undated_quota = parse_undated_quota(source, allow_undated=allow_undated)
        undated_used = 0

        try:
            list_html, _method = fetch_with_policy(
                list_url, use_proxy=use_proxy, proxy=proxy, fetch_fn=fetch_fn
            )
        except FetchError as e:
            append_error_log(ai_trends_dir, e.method, e.url, e.reason)
            errors += 1
            continue

        items = extract_links(list_html, list_url, date_attr=date_attr)
        for item in items:
            url = item["url"]
            if url in known_urls:
                skipped += 1
                continue
            # Filter before any detail request
            if not url_allowed(
                url,
                list_url=list_url,
                url_include=url_include,
                url_exclude=url_exclude,
            ):
                skipped += 1
                continue
            pub = item.get("publish_date")
            if not date_allows(
                pub, start_date, end_date, allow_undated=allow_undated
            ):
                skipped += 1
                continue
            if is_undated(pub):
                if undated_used >= undated_quota:
                    skipped += 1
                    continue
                undated_used += 1

            entry = process_candidate(
                item,
                source_name=name,
                use_proxy=use_proxy,
                proxy=proxy,
                fetch_fn=fetch_fn,
                ai_trends_dir=ai_trends_dir,
                save_raw=save_raw,
            )
            if entry is None:
                errors += 1
                continue
            # Re-check date after detail enrichment
            if not date_allows(
                entry.get("publish_date"),
                start_date,
                end_date,
                allow_undated=allow_undated,
            ):
                skipped += 1
                continue
            pending.append(entry)
            known_urls.add(url)

    save_json_atomic(pending, ai_trends_dir / "pending.json")
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
        epilog="Example: python3 discover_and_fetch.py --start-date 2026-07-18 --end-date 2026-07-24",
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
    args = parser.parse_args()

    counts = run(
        args.start_date,
        args.end_date,
        weekly_root=args.weekly_root,
        sources_path=Path(args.sources) if args.sources else None,
        save_raw=not args.no_raw,
    )
    print(format_summary(counts))


if __name__ == "__main__":
    main()
