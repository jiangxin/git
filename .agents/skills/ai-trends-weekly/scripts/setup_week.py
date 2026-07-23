#!/usr/bin/env python3
"""Create weekly/<end_date>/ai-trends/ directory for the AI trends skill.

Usage:
    python3 setup_week.py [<YYYY-MM-DD>]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
sys.path.insert(0, str(REPO_ROOT / "lib"))

from week_bounds import (
    SETUP_WEEK_EPILOG,
    SETUP_WEEK_INTERVAL_HELP,
    compute_week_dates,
    ensure_week_dir,
    repo_weekly_root_from_skill_script,
    resolve_anchor_datetime,
)

SKILL_SUBDIR = "ai-trends"


def setup_week(weekly_root, end_date):
    week_dir = ensure_week_dir(weekly_root, end_date)
    (week_dir / SKILL_SUBDIR).mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description=(
            f"计算收集周期并创建 weekly/<end_date>/{SKILL_SUBDIR}/。"
            f"{SETUP_WEEK_INTERVAL_HELP}"
        ),
        epilog=f"{SETUP_WEEK_EPILOG}；省略参数则按今天计算。",
    )
    parser.add_argument(
        "date",
        metavar="DATE",
        nargs="?",
        default=None,
        help="参考日期，格式 YYYY-MM-DD；省略则使用本地当前日期",
    )
    args = parser.parse_args()

    try:
        input_date = resolve_anchor_datetime(args.date)
    except ValueError:
        parser.error(f"日期格式无效: {args.date}，应为 YYYY-MM-DD")

    start_str, end_str = compute_week_dates(input_date)
    weekly_root = repo_weekly_root_from_skill_script(__file__)
    setup_week(weekly_root, end_str)
    print(f"{start_str} {end_str}")


if __name__ == "__main__":
    main()
