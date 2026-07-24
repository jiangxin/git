#!/usr/bin/env python3
"""Check whether a URL exists in url_index.jsonl for git-news.

Thin wrapper around lib/check_helpers.

Usage:
    python3 check_url.py --end-date YYYY-MM-DD <URL>
    python3 check_url.py --end-date YYYY-MM-DD --file urls.txt

Output: FOUND or NOT_FOUND per URL.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
sys.path.insert(0, str(REPO_ROOT / "lib"))

from check_helpers import check_url, get_url_index  # noqa: E402

SKILL_SUBDIR = "git-news"


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

    url_index = get_url_index(args.end_date, SKILL_SUBDIR, root_override=args.weekly_root)

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
