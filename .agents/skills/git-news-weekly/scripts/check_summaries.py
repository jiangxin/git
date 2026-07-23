#!/usr/bin/env python3
"""Check summary completeness for all fetched articles in git-news.

Thin wrapper around lib/check_helpers.

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
REPO_ROOT = SCRIPT_DIR.parents[3]
sys.path.insert(0, str(REPO_ROOT / "lib"))

from check_helpers import check_summaries, format_result, resolve_skill_dir  # noqa: E402

SKILL_SUBDIR = "git-news"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check summary completeness for fetched articles.",
        epilog="Example: python3 check_summaries.py --end-date 2026-07-24",
    )
    parser.add_argument("--end-date", required=True, help="Week dir YYYY-MM-DD")
    parser.add_argument("--weekly-root", default=None, help="Override weekly/ path")
    args = parser.parse_args()

    skill_dir = resolve_skill_dir(args.end_date, SKILL_SUBDIR, args.weekly_root)
    counts = check_summaries(skill_dir)
    print(format_result(counts))
    if counts["missing"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
