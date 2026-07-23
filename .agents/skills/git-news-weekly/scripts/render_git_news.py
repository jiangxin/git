#!/usr/bin/env python3
"""Render weekly/<end_date>/Git-news.md from per-site article sidecars.

Thin wrapper around lib/render_report.run_report().

Usage:
    python3 render_git_news.py --start-date YYYY-MM-DD --end-date YYYY-MM-DD
                               [--weekly-root PATH] [--max-per-day K]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
sys.path.insert(0, str(REPO_ROOT / "lib"))

from render_report import run_report  # noqa: E402

SKILL_SUBDIR = "git-news"
OUTPUT_FILENAME = "Git-news.md"
TITLE = "Git 技术动态周报"
SUBTITLE = "本周 Git 技术动态"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render Git-news.md from per-site article sidecars.",
        epilog="示例: python3 render_git_news.py --start-date 2026-05-03 --end-date 2026-05-10",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--start-date", required=True, help="Start date YYYY-MM-DD (inclusive)")
    parser.add_argument("--end-date", required=True, help="End date YYYY-MM-DD (inclusive)")
    parser.add_argument("--weekly-root", metavar="PATH", default=None)
    parser.add_argument("--max-per-day", type=int, default=None, metavar="K")
    parser.add_argument(
        "--quality-min", type=int, default=5, metavar="M",
        help="Stderr QUALITY_WARNING when in-range count < M (default: 5)",
    )
    args = parser.parse_args()
    for label, d in (("start-date", args.start_date), ("end-date", args.end_date)):
        try:
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            print(f"ERROR: invalid {label} (expected YYYY-MM-DD): {d!r}", file=sys.stderr)
            return 2
    out = run_report(
        args.start_date,
        args.end_date,
        SKILL_SUBDIR,
        OUTPUT_FILENAME,
        TITLE,
        SUBTITLE,
        weekly_root=args.weekly_root,
        max_per_day=args.max_per_day,
        quality_min=args.quality_min,
    )
    print(f"WROTE: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
