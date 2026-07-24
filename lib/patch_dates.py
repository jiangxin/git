#!/usr/bin/env python3
"""Patch missing publish_date in article meta.json files.

Strategy:
  1. Filter known non-article URLs (static/about/contact pages) -> skipped_filter
  2. Try HTTP fetch to extract dates from JSON-LD / <time> / <meta> tags
  3. For SPA sites, fall back to Playwright Chromium
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch_backends import fetch_html, FetchError  # noqa: E402

NON_ARTICLE_PATTERNS = [
    r"/about",
    r"/contact",
    r"/newsroom",
    r"/investor",
    r"/topsales",
    r"/TrueNorth",
    r"/top-down",
    r"/boss-ai",
    r"/en/$",
    r"/en/index",
    r"\?page=\d+",
]

SPA_SITES = {"anthropic-research", "字节跳动-seed-博客", "meta-ai-blog"}

DATE_RE_JSONLD = re.compile(
    r'"date(?:Published|Created)"\s*:\s*"([^"]+)"'
)
DATE_RE_TIME = re.compile(
    r'<time[^>]*datetime="([^"]+)"', re.I
)
DATE_RE_META = re.compile(
    r'<meta[^>]*property="article:published_time"[^>]*content="([^"]+)"', re.I
)
DATE_RE_META2 = re.compile(
    r'<meta[^>]*name="publish_date"[^>]*content="([^"]+)"', re.I
)
DATE_RE_META3 = re.compile(
    r'<meta[^>]*name="date"[^>]*content="([^"]+)"', re.I
)
DATE_RE_ANTHROPIC = re.compile(
    r'agate[^\"]*\"[^>]*>'
    r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2},?\s+\d{4})<'
)
DATE_RE_META_AMUM = re.compile(
    r'class=\"_amum\">'
    r'((?:January|February|March|April|May|June|July|August|September|October|November|December)'
    r'\s+\d{1,2},?\s+\d{4})<'
)


def is_non_article(url: str) -> bool:
    for pat in NON_ARTICLE_PATTERNS:
        if re.search(pat, url, re.I):
            return True
    return False


def extract_date_from_html(html: str) -> str | None:
    for pattern in [
        DATE_RE_JSONLD, DATE_RE_TIME, DATE_RE_META, DATE_RE_META2, DATE_RE_META3,
        DATE_RE_ANTHROPIC, DATE_RE_META_AMUM,
    ]:
        m = pattern.search(html)
        if m:
            raw = m.group(1).strip()
            return normalize_date(raw)
    return None


def normalize_date(raw: str) -> str | None:
    for fmt in [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%B %d, %Y",
        "%b %d, %Y",
        "%Y年%m月%d日",
    ]:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    m = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
    if m:
        return m.group(1)
    return None


def load_config() -> dict:
    cfg_path = REPO_ROOT / "config.json"
    if cfg_path.exists():
        return json.loads(cfg_path.read_text())
    return {}


def fetch_date_http(url: str, proxy: str | None, use_proxy_flag: bool) -> str | None:
    try:
        html, _ = fetch_html(
            url, mode="http", use_proxy=use_proxy_flag, proxy=proxy, timeout=20
        )
        return extract_date_from_html(html)
    except FetchError:
        return None


def fetch_date_browser(url: str, proxy: str | None, use_proxy_flag: bool) -> str | None:
    try:
        html, _ = fetch_html(
            url, mode="browser", use_proxy=use_proxy_flag, proxy=proxy, timeout=45
        )
        return extract_date_from_html(html)
    except FetchError:
        return None


def find_undated(end_date: str, skill_subdir: str, weekly_root: Path | None = None) -> list[Path]:
    if weekly_root is None:
        weekly_root = REPO_ROOT / "weekly"
    else:
        weekly_root = Path(weekly_root)
    weekly_dir = weekly_root / end_date / skill_subdir
    results = []
    for meta_path in sorted(weekly_dir.glob("sites/*/articles/*.meta.json")):
        data = json.loads(meta_path.read_text())
        pd = data.get("publish_date")
        if not pd or pd == "None" or pd is None:
            results.append((meta_path, data))
    return results


import argparse


def _infer_skill_subdir(weekly_root: Path | None) -> str | None:
    wr = Path(weekly_root) if weekly_root else REPO_ROOT / "weekly"
    if wr.is_dir():
        subs = [
            d.name for d in wr.iterdir()
            if d.is_dir() and (d / "sites").is_dir()
        ]
        if len(subs) == 1:
            return subs[0]
    return None


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Patch missing publish_date in article meta.json files.",
    )
    p.add_argument("--end-date", default=datetime.now().strftime("%Y-%m-%d"),
                    help="Week dir YYYY-MM-DD (default: today)")
    p.add_argument("--skill-subdir", default=None,
                    help="Subdirectory under weekly/<end_date>/ (e.g. ai-trends, git-news); "
                         "auto-inferred from weekly dir when omitted")
    p.add_argument("--weekly-root", default=None,
                    help="Override weekly/ directory path")
    return p.parse_args()


def main():
    args = _parse_args()
    end_date = args.end_date
    skill_subdir = args.skill_subdir
    weekly_root = Path(args.weekly_root) if args.weekly_root else None

    if not skill_subdir:
        skill_subdir = _infer_skill_subdir(weekly_root)
    if not skill_subdir:
        print("ERROR: Cannot determine --skill-subdir automatically.", file=sys.stderr)
        print("Pass --skill-subdir explicitly (e.g. ai-trends, git-news).", file=sys.stderr)
        sys.exit(2)

    cfg = load_config()
    proxy = cfg.get("proxy")

    items = find_undated(end_date, skill_subdir=skill_subdir, weekly_root=weekly_root)
    patched = 0
    skipped = 0
    failed = 0

    print(f"Found {len(items)} undated articles")
    print()

    for meta_path, data in items:
        url = data["url"]
        site = data.get("site", "")
        label = f"{site:30s} | {url}"

        if is_non_article(url):
            data["status"] = "skipped_filter"
            data.pop("publish_date", None)
            meta_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            print(f"SKIP_FILTER | {label}")
            skipped += 1
            continue

        use_proxy = site in {"meta-ai-blog"}
        date = fetch_date_http(url, proxy, use_proxy_flag=use_proxy)

        if not date and site in SPA_SITES:
            date = fetch_date_browser(url, proxy, use_proxy_flag=use_proxy)

        if date:
            data["publish_date"] = date
            meta_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            print(f"PATCHED     | {date} | {label}")
            patched += 1
        else:
            print(f"NO_DATE     | {label}")
            failed += 1

    print()
    print(f"Done: patched={patched} skipped_filter={skipped} no_date={failed}")


if __name__ == "__main__":
    main()
