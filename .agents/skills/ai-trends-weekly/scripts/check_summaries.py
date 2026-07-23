#!/usr/bin/env python3
"""Check summary completeness for all fetched articles.

Scans ``sites/*/articles/*.meta.json`` and verifies each article with
status ``fetched`` or ``cached`` has a valid ``.summary.md`` sidecar.

Usage:
    python3 check_summaries.py --end-date YYYY-MM-DD [--weekly-root PATH]

Stdout:
    OK: summarized=N missing=0 sites=S

Exit 0 when missing=0, non-zero otherwise.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from site_store import iter_articles  # noqa: E402
from summary_io import is_valid_summary, load_summary, summary_path  # noqa: E402


def resolve_ai_trends_dir(end_date: str, weekly_root=None) -> Path:
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


def check(ai_trends_dir: Path) -> dict[str, int]:
    """Return counts dict: summarized, missing, sites."""
    sites_root = Path(ai_trends_dir) / "sites"
    if not sites_root.is_dir():
        return {"summarized": 0, "missing": 0, "sites": 0}
    summarized = 0
    missing = 0
    site_slugs: set[str] = set()
    for slug_dir in sorted(sites_root.iterdir()):
        if not slug_dir.is_dir():
            continue
        slug = slug_dir.name
        for record in iter_articles(ai_trends_dir, slug):
            status = record.meta.get("status")
            if status not in ("fetched", "cached"):
                continue
            site_slugs.add(slug)
            s_path = summary_path(ai_trends_dir, slug, record.hash)
            data = load_summary(s_path)
            if is_valid_summary(data):
                summarized += 1
            else:
                missing += 1
    return {
        "summarized": summarized,
        "missing": missing,
        "sites": len(site_slugs),
    }


def format_result(counts: dict[str, int]) -> str:
    return (
        f"OK: summarized={counts['summarized']} "
        f"missing={counts['missing']} "
        f"sites={counts['sites']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check summary completeness for fetched articles.",
        epilog="Example: python3 check_summaries.py --end-date 2026-07-24",
    )
    parser.add_argument("--end-date", required=True, help="Week dir YYYY-MM-DD")
    parser.add_argument("--weekly-root", default=None, help="Override weekly/ path")
    args = parser.parse_args()

    ai_trends_dir = resolve_ai_trends_dir(args.end_date, args.weekly_root)
    counts = check(ai_trends_dir)
    print(format_result(counts))
    if counts["missing"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
