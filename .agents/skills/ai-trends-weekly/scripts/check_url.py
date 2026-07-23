#!/usr/bin/env python3
"""Check whether a URL exists in url_index.jsonl.

Usage:
    python3 check_url.py --end-date YYYY-MM-DD <URL>
    python3 check_url.py --end-date YYYY-MM-DD --file urls.txt

Output: FOUND or NOT_FOUND per URL.
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from site_store import load_url_index, url_index_path  # noqa: E402


def get_url_index(end_date: str, root_override=None) -> dict:
    if not end_date:
        print("ERROR: end_date is required (YYYY-MM-DD)", file=sys.stderr)
        sys.exit(2)
    if root_override is not None:
        weekly_root = Path(root_override)
    else:
        repo_root = SCRIPT_DIR.parents[3]
        weekly_root = repo_root / "weekly"
    idx_path = url_index_path(weekly_root / end_date / "ai-trends")
    if not idx_path.is_file():
        print(f"ERROR: url_index.jsonl not found at {idx_path}", file=sys.stderr)
        print("Run setup_week.py and discover_and_fetch.py first.", file=sys.stderr)
        sys.exit(2)
    return load_url_index(idx_path)


def check_url(url_index: dict, url: str):
    return url_index.get(url)


def main():
    parser = argparse.ArgumentParser(
        description="Check whether a URL exists in url_index.jsonl.",
        epilog="示例:\n"
               "  python3 check_url.py --end-date 2026-07-24 https://example.com/article\n"
               "  python3 check_url.py --end-date 2026-07-24 --file urls.txt\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--end-date", metavar="END_DATE", required=True)
    parser.add_argument("--weekly-root", metavar="PATH", default=None)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("url", nargs="?", help="URL to check")
    group.add_argument("--file", metavar="FILE", help="File with URLs (one per line)")
    args = parser.parse_args()

    url_index = get_url_index(args.end_date, root_override=args.weekly_root)

    if args.file:
        url_file = Path(args.file)
        if not url_file.exists():
            print(f"ERROR: file not found: {url_file}", file=sys.stderr)
            sys.exit(1)
        urls = [
            line.strip()
            for line in url_file.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
    else:
        urls = [args.url]

    for url in urls:
        entry = check_url(url_index, url)
        if entry:
            print(f"FOUND: {url}")
            print(f"  Site: {entry.get('site', 'N/A')}")
        else:
            print(f"NOT_FOUND: {url}")


if __name__ == "__main__":
    main()
