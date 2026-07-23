#!/usr/bin/env python3
"""
给定日期（YYYY-MM-DD），输出收集闭区间 start_date、end_date（空格分隔），
并创建 weekly/<end_date>/ai-trends/ 目录。

起止 weekday 由仓库根 config.json 的 start_day、end_day 决定（缺省 saturday–friday），
经 week_bounds.compute_week_dates 计算，非固定自然周。

用法: python3 setup_week.py [<YYYY-MM-DD>]
不传日期时使用本地当前日期。
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared" / "scripts"))
from week_bounds import (
    SETUP_WEEK_EPILOG,
    SETUP_WEEK_INTERVAL_HELP,
    compute_week_dates,
    ensure_week_dir,
    repo_weekly_root_from_skill_script,
    resolve_anchor_datetime,
)


def setup_week(weekly_root, end_date):
    """创建周目录与 ai-trends 子目录。"""
    week_dir = ensure_week_dir(weekly_root, end_date)
    (week_dir / "ai-trends").mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description=(
            f"计算收集周期并创建 weekly/<end_date>/ai-trends/。"
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
